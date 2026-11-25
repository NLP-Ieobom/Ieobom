import json
import os
import subprocess
import time
from pathlib import Path
from threading import Event, Thread
from uuid import uuid4

from botocore.exceptions import BotoCoreError, ClientError
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import SQLAlchemyError

from app.db.session import SessionLocal
from app.integrations import s3
from app.integrations.gemini import Gemini
from app.integrations.learning_http import ProviderError
from app.models import curriculum, user  # noqa: F401  # 문서·과목의 외래키 대상을 등록한다.
from app.models.course import Course
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.learning import DocumentLearning
from app.models.question import Question
from app.pipelines.learning import generate_learning
from app.services.usage import usage_sink

WORKER_ID = os.environ.get("WORKER_ID", "worker-1")
POLL_INTERVAL_SEC = int(os.environ.get("WORKER_POLL_INTERVAL_SEC", "3"))
MAX_ATTEMPTS = int(os.environ.get("WORKER_MAX_ATTEMPTS", "3"))
# docker.sock으로 host의 docling 이미지를 그대로 실행하기 때문에, -v 경로는 워커 컨테이너가 아니라
# host 기준이어야 한다. 워커 자신도 같은 host 디렉터리를 /work/input, /work/output에 마운트해 둔다.
DOCLING_HOST_DIR = os.environ["DOCLING_HOST_DIR"]
INPUT_DIR = Path("/work/input")

CLAIM_SQL = text("""
    UPDATE analysis_job
    SET status = 'running', stage = 'downloading',
        locked_by = :worker_id, locked_at = clock_timestamp(), attempt = attempt + 1,
        error_code = NULL, error_message = NULL
    WHERE id = (
        SELECT id FROM analysis_job
        WHERE status = 'pending' AND scheduled_at <= now()
        ORDER BY scheduled_at, id
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING id, document_id, attempt, locked_by
""")


class JobLeaseLost(RuntimeError):
    pass


def recover_jobs(db) -> None:
    db.execute(text("""
        UPDATE analysis_job
        SET status = CASE WHEN attempt < :max_attempts THEN 'pending' ELSE 'failed' END,
            stage = CASE WHEN attempt < :max_attempts THEN 'queued' ELSE stage END,
            scheduled_at = now(), locked_by = NULL, locked_at = NULL,
            error_code = 'WORKER_INTERRUPTED', error_message = :message
        WHERE status = 'running'
          AND (locked_at IS NULL OR locked_at < clock_timestamp() - interval '15 minutes')
    """), {"max_attempts": MAX_ATTEMPTS, "message": "분석 작업이 중단되었습니다. 다시 시도해 주세요."})
    db.commit()


def claim_job(db):
    # 같은 워커가 같은 작업을 다시 맡아도 이전 실행의 저장 권한은 되살아나지 않아야 한다.
    owner = f"{WORKER_ID[:60]}:{uuid4().hex}"
    row = db.execute(CLAIM_SQL, {"worker_id": owner}).first()
    db.commit()
    return row


def heartbeat(job, stop: Event) -> None:
    while not stop.wait(30):
        try:
            with SessionLocal() as db:
                row = db.execute(text("""
                    UPDATE analysis_job SET locked_at = clock_timestamp()
                    WHERE id = :id AND status = 'running' AND locked_by = :owner
                      AND locked_at > clock_timestamp() - interval '15 minutes'
                    RETURNING id
                """), {"id": job.id, "owner": job.locked_by}).first()
                db.commit()
                if row is None:
                    return
        except SQLAlchemyError:
            # 갱신이 끊기면 다른 워커가 회수한다. 만료된 실행은 저장 직전에 다시 차단한다.
            print(f"job {job.id} heartbeat failed", flush=True)
            return


def lock_job(db, job) -> None:
    row = db.execute(text("""
        SELECT id FROM analysis_job
        WHERE id = :id AND status = 'running' AND locked_by = :owner
          AND locked_at > clock_timestamp() - interval '15 minutes'
        FOR UPDATE
    """), {"id": job.id, "owner": job.locked_by}).first()
    if row is None:
        raise JobLeaseLost()


def finish_job(
    db, job, status: str, stage: str | None = None, delay: int = 0,
    *, error_code: str | None = None, error_message: str | None = None,
) -> None:
    lock_job(db, job)
    db.execute(text("""
        UPDATE analysis_job
        SET status = :status, stage = COALESCE(:stage, stage), locked_by = NULL, locked_at = NULL,
            error_code = :error_code, error_message = :error_message,
            scheduled_at = CASE WHEN :delay > 0
                THEN now() + :delay * interval '1 second' ELSE scheduled_at END
        WHERE id = :id
    """), {"status": status, "stage": stage, "id": job.id, "delay": delay,
           "error_code": error_code, "error_message": error_message})
    db.commit()


def set_job_stage(db, job, stage: str, completed_pages=None, total_pages=None) -> None:
    lock_job(db, job)
    db.execute(
        text("""
            UPDATE analysis_job
            SET stage = :stage, completed_pages = :completed_pages, total_pages = :total_pages,
                locked_at = clock_timestamp()
            WHERE id = :id
        """),
        {"stage": stage, "completed_pages": completed_pages, "total_pages": total_pages, "id": job.id},
    )
    # 별도 API 세션의 폴링에서도 현재 단계를 읽을 수 있어야 한다.
    db.commit()


def run_docling(pdf_path: Path, output_path: Path, document_id) -> dict | None:
    container = f"ieobom-docling-{pdf_path.stem}"
    cmd = [
        "docker", "run", "--rm", "--name", container,
        "--cpus", "1.0", "--memory", "4g", "--memory-swap", "4g",
        "-e", "OMP_NUM_THREADS=1", "-e", "MKL_NUM_THREADS=1", "-e", "OPENBLAS_NUM_THREADS=1",
        "-v", f"{DOCLING_HOST_DIR}/input:/work/input:ro",
        "-v", f"{DOCLING_HOST_DIR}/output:/work/output",
        "-v", "ieobom_docling_cache:/root/.cache",
        "ieobom-docling:local",
        "extract", f"/work/input/{pdf_path.name}",
        "--output", str(output_path), "--document-id", str(document_id),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        # docker CLI만 종료하면 실제 추출 컨테이너는 계속 메모리를 사용한다.
        subprocess.run(["docker", "rm", "-f", container], capture_output=True, timeout=30)
        raise
    print(result.stdout, flush=True)
    if result.returncode != 0:
        print(result.stderr, flush=True)
        return None
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    # CLI는 검토용 부분 결과도 남기지만 워커는 완전한 추출만 성공으로 처리한다.
    if any(warning["code"] == "partial_conversion" for warning in payload["warnings"]):
        return None
    return payload


def process(db, job) -> None:
    document_id = job.document_id
    document = db.get(Document, document_id)
    if document is None:
        raise ValueError("Analysis job is missing its document")
    learning = db.get(DocumentLearning, document_id)
    if learning is None:
        # 중단된 Docling 컨테이너가 늦게 끝나도 새 실행의 파일을 덮어쓰지 않는다.
        filename = f"{job.id}-{job.locked_by.rsplit(':', 1)[-1]}"
        pdf_path = INPUT_DIR / f"{filename}.pdf"
        output_path = Path("/work/output") / f"{filename}.json"
        try:
            s3.download_file(document.s3_key, pdf_path)
            set_job_stage(db, job, "extracting")
            extraction = run_docling(pdf_path, output_path, document_id)
        finally:
            pdf_path.unlink(missing_ok=True)
            output_path.unlink(missing_ok=True)
        if extraction is None:
            finish_job(db, job, "failed", error_code="EXTRACTION_FAILED",
                       error_message="PDF 내용을 추출하지 못했습니다. 원본 파일을 확인해 주세요.")
            return
        lock_job(db, job)
        extraction["source"]["filename"] = document.original_filename
        learning = DocumentLearning(document_id=document_id, extraction=extraction)
        db.add(learning)
        # 메모가 먼저 만든 페이지 행을 유지하고, 분석 재시도에서도 같은 ID를 사용한다.
        db.execute(insert(DocumentPage).values([
            {"id": uuid4(), "document_id": document_id, "page_number": page["page_number"]}
            for page in extraction["pages"]
        ]).on_conflict_do_nothing(index_elements=[DocumentPage.document_id, DocumentPage.page_number]))

    total_pages = len(learning.extraction["pages"])
    document.page_count = total_pages
    saved_pages = dict(learning.result["pages"]) if learning.result is not None else {}
    set_job_stage(db, job, "analyzing", completed_pages=len(saved_pages), total_pages=total_pages)
    if len(saved_pages) < total_pages:
        if not os.environ.get("GEMINI_API_KEY", "").strip():
            finish_job(db, job, "succeeded", stage="analysis_skipped", error_code="AI_NOT_CONFIGURED",
                       error_message="질문 생성 설정이 준비되지 않았습니다.")
            return
        course = db.get(Course, document.course_id)

        def save_batch(pages: list[dict]) -> None:
            lock_job(db, job)
            page_ids = dict(db.execute(select(DocumentPage.page_number, DocumentPage.id).where(
                DocumentPage.document_id == document_id,
            )).all())
            for page in pages:
                blocks = {block["block_id"]: block for block in page["evidence_blocks"]}
                for item in page["questions"]:
                    question_id = uuid4()
                    db.add(Question(
                        id=question_id, document_page_id=page_ids[page["page_number"]],
                        question_type=item["type"], content=item["question"],
                        recommended_reason=item["why_recommended"],
                        prerequisite="\n".join(item["prerequisites"]),
                        learning_order="\n".join(item["learning_steps"]), first_activity=item["first_activity"],
                        evidence_block_ids=item["evidence_block_ids"],
                        evidence_blocks=[blocks[block_id] for block_id in item["evidence_block_ids"]],
                        explanation=item["explanation"], related_courses=item["related_courses"], trends=item["trends"],
                    ))
                    item["id"] = str(question_id)
                saved_pages[str(page["page_number"])] = page
            # 질문 행·JSON·진행률을 같이 저장해야 공개된 질문을 재시도 때 다시 만들지 않는다.
            learning.result = {"schema_version": "1.0", "pages": dict(saved_pages)}
            set_job_stage(db, job, "analyzing", completed_pages=len(saved_pages), total_pages=total_pages)

        gemini = Gemini(
            {"document_id": str(document_id), "job_id": str(job.id), "job_attempt": job.attempt},
            sink=usage_sink(document_id),
        )
        generate_learning(db, gemini, course, learning.extraction, saved_pages=saved_pages, on_batch=save_batch)
    finish_job(db, job, "succeeded", stage="completed")


def run_job(db, job) -> None:
    try:
        process(db, job)
    except JobLeaseLost:
        raise
    except ProviderError as error:
        db.rollback()
        retry = error.retryable and job.attempt < MAX_ATTEMPTS
        delay = min(30 * 2 ** (job.attempt - 1), 600) if retry else 0
        print(f"job {job.id} provider failure: {error}", flush=True)
        finish_job(db, job, "pending" if retry else "failed", stage="queued" if retry else None,
                   delay=delay, error_code="AI_TEMPORARY_ERROR" if error.retryable else "AI_REQUEST_FAILED",
                   error_message="질문 생성 서비스에서 응답을 받지 못했습니다. 잠시 후 다시 시도해 주세요."
                   if error.retryable else "질문 생성 요청이 거절되었습니다. 서버 설정을 확인해 주세요.")
    except (ClientError, BotoCoreError):
        db.rollback()
        finish_job(db, job, "failed", error_code="PDF_DOWNLOAD_FAILED",
                   error_message="원본 PDF를 가져오지 못했습니다. 파일 저장 상태를 확인해 주세요.")
    except subprocess.TimeoutExpired:
        db.rollback()
        finish_job(db, job, "failed", error_code="EXTRACTION_TIMEOUT",
                   error_message="PDF 추출 시간이 초과되었습니다. 다시 시도해 주세요.")
    except Exception as error:
        # 작업 하나의 실패가 워커 루프를 멈추지 않도록 하는 최상위 경계다.
        print(f"job {job.id} failed: {error}", flush=True)
        db.rollback()
        finish_job(db, job, "failed", error_code="ANALYSIS_FAILED",
                   error_message="분석 중 오류가 발생했습니다. 다시 시도해 주세요.")


def main() -> None:
    print(f"worker {WORKER_ID} started", flush=True)
    while True:
        with SessionLocal() as db:
            recover_jobs(db)
            claimed = claim_job(db)
            if claimed is None:
                time.sleep(POLL_INTERVAL_SEC)
                continue
            print(f"claimed job {claimed.id} for document {claimed.document_id}", flush=True)
            stop = Event()
            thread = Thread(target=heartbeat, args=(claimed, stop), daemon=True)
            thread.start()
            try:
                run_job(db, claimed)
            except JobLeaseLost:
                db.rollback()
                print(f"job {claimed.id} ownership expired; result discarded", flush=True)
            finally:
                stop.set()
                thread.join(timeout=5)


if __name__ == "__main__":
    main()

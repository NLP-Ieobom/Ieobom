import json
import os
import subprocess
import sys
import time
from copy import deepcopy
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

CLAIM_EXTRACTION_SQL = text("""
    UPDATE analysis_job
    SET status = 'running', stage = 'downloading',
        locked_by = :worker_id, locked_at = clock_timestamp(), attempt = attempt + 1,
        error_code = NULL, error_message = NULL
    WHERE id = (
        SELECT j.id FROM analysis_job j
        WHERE j.status = 'pending' AND j.scheduled_at <= now()
          AND EXISTS (SELECT 1 FROM document d WHERE d.id = j.document_id AND d.user_id = :user_id)
          AND NOT EXISTS (SELECT 1 FROM document_learning l WHERE l.document_id = j.document_id)
        ORDER BY j.created_at, j.id
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING id, document_id, attempt, locked_by
""")


class JobLeaseLost(RuntimeError):
    pass


def recover_jobs(db) -> None:
    db.execute(text("""
        WITH expired AS (
            SELECT j.id, j.consecutive_failures + 1 AS failures,
                COALESCE(j.first_failure_at, clock_timestamp()) AS first_failure,
                CASE WHEN EXISTS (SELECT 1 FROM document_learning l WHERE l.document_id = j.document_id)
                    THEN COALESCE(j.first_failure_at, clock_timestamp()) > clock_timestamp() - interval '1 hour'
                    ELSE j.consecutive_failures + 1 < :max_attempts END AS retry
            FROM analysis_job j
            WHERE j.status = 'running'
              AND (j.locked_at IS NULL OR j.locked_at < clock_timestamp() - interval '15 minutes')
            FOR UPDATE OF j SKIP LOCKED
        )
        UPDATE analysis_job j
        SET status = CASE WHEN expired.retry THEN 'pending' ELSE 'failed' END,
            stage = CASE WHEN expired.retry THEN 'queued' ELSE j.stage END,
            consecutive_failures = expired.failures, first_failure_at = expired.first_failure,
            scheduled_at = LEAST(clock_timestamp() +
                LEAST(30 * power(2, LEAST(expired.failures - 1, 5)), 600) * interval '1 second',
                expired.first_failure + interval '1 hour'),
            locked_by = NULL, locked_at = NULL,
            error_code = 'WORKER_INTERRUPTED', error_message = :message
        FROM expired WHERE j.id = expired.id
    """), {"max_attempts": MAX_ATTEMPTS, "message": "분석 작업이 중단되었습니다. 다시 시도해 주세요."})
    # 차례를 기다리는 동안에도 제한 시간이 끝나면 새 외부 호출을 시작하지 않는다.
    db.execute(text("""
        UPDATE analysis_job SET status = 'failed', error_code = 'AI_RETRY_EXHAUSTED',
            error_message = :message
        WHERE status = 'pending' AND first_failure_at <= clock_timestamp() - interval '1 hour'
          AND EXISTS (SELECT 1 FROM document_learning l WHERE l.document_id = analysis_job.document_id)
    """), {"message": "같은 페이지 묶음의 재시도 시간이 1시간을 넘어 분석을 일시 중단했습니다. 다시 시도할 수 있습니다."})
    db.commit()


def claim_job(db, role: str):
    # 같은 워커가 같은 작업을 다시 맡아도 이전 실행의 저장 권한은 되살아나지 않아야 한다.
    owner = f"{WORKER_ID[:60]}:{uuid4().hex}"
    if role == "extract":
        account = db.execute(text("""
            SELECT u.id FROM "user" u
            WHERE EXISTS (
                SELECT 1 FROM analysis_job j JOIN document d ON d.id = j.document_id
                WHERE d.user_id = u.id AND j.status = 'pending' AND j.scheduled_at <= now()
                  AND NOT EXISTS (SELECT 1 FROM document_learning l WHERE l.document_id = d.id)
            ) AND NOT EXISTS (
                SELECT 1 FROM analysis_job j JOIN document d ON d.id = j.document_id
                WHERE d.user_id = u.id AND j.status = 'running'
                  AND NOT EXISTS (SELECT 1 FROM document_learning l WHERE l.document_id = d.id)
            )
            ORDER BY u.extraction_last_served_at NULLS FIRST, u.created_at, u.id
            FOR UPDATE OF u SKIP LOCKED LIMIT 1
        """)).first()
        if account is None:
            db.commit()
            return None
        row = db.execute(CLAIM_EXTRACTION_SQL, {"worker_id": owner, "user_id": account.id}).first()
        if row is not None:
            db.execute(text("""
                UPDATE "user" SET extraction_last_served_at = clock_timestamp() WHERE id = :id
            """), {"id": account.id})
        db.commit()
        return row

    account = db.execute(text("""
        SELECT u.id, u.analysis_priority_turns FROM "user" u
        WHERE EXISTS (
            SELECT 1 FROM analysis_job j
            JOIN document d ON d.id = j.document_id
            JOIN document_learning l ON l.document_id = d.id
            WHERE d.user_id = u.id AND j.status = 'pending' AND j.scheduled_at <= now()
              AND (j.first_failure_at IS NULL OR j.first_failure_at > clock_timestamp() - interval '1 hour')
        ) AND NOT EXISTS (
            SELECT 1 FROM analysis_job j
            JOIN document d ON d.id = j.document_id
            JOIN document_learning l ON l.document_id = d.id
            WHERE d.user_id = u.id AND j.status = 'running'
        )
        ORDER BY u.analysis_last_served_at NULLS FIRST, u.created_at, u.id
        FOR UPDATE OF u SKIP LOCKED LIMIT 1
    """)).first()
    if account is None:
        db.commit()
        return None
    preferred = db.execute(text("""
        SELECT document_id FROM user_document_progress
        WHERE user_id = :user_id
        ORDER BY last_viewed_at DESC, document_id LIMIT 1
    """), {"user_id": account.id}).scalar()
    # 우선 문서도 두 차례 뒤에는 다른 문서에 양보한다. API를 기다리는 중에는 선점하지 않는다.
    picked = db.execute(text("""
        SELECT j.id, j.document_id FROM analysis_job j
        JOIN document d ON d.id = j.document_id
        JOIN document_learning l ON l.document_id = d.id
        WHERE d.user_id = :user_id AND j.status = 'pending' AND j.scheduled_at <= now()
          AND (j.first_failure_at IS NULL OR j.first_failure_at > clock_timestamp() - interval '1 hour')
        ORDER BY CASE
            WHEN d.id = :preferred THEN CASE WHEN :turns < 2 THEN 0 ELSE 1 END
            ELSE CASE WHEN :turns < 2 THEN 1 ELSE 0 END
        END, j.last_served_at NULLS FIRST, j.created_at, j.id
        FOR UPDATE OF j SKIP LOCKED LIMIT 1
    """), {"user_id": account.id, "preferred": preferred, "turns": account.analysis_priority_turns}).first()
    if picked is None:
        db.commit()
        return None
    row = db.execute(text("""
        UPDATE analysis_job SET status = 'running', stage = 'analyzing',
            locked_by = :worker_id, locked_at = clock_timestamp(), last_served_at = clock_timestamp(),
            attempt = CASE WHEN attempt = 0 OR error_code IS NOT NULL OR first_failure_at IS NOT NULL
                THEN attempt + 1 ELSE attempt END,
            error_code = NULL, error_message = NULL
        WHERE id = :id RETURNING id, document_id, attempt, locked_by
    """), {"worker_id": owner, "id": picked.id}).first()
    db.execute(text("""
        UPDATE "user" SET analysis_last_served_at = clock_timestamp(), analysis_priority_turns = :turns
        WHERE id = :id
    """), {"id": account.id, "turns": min(account.analysis_priority_turns + 1, 2)
            if picked.document_id == preferred else 0})
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


def process(db, job, role: str) -> None:
    document_id = job.document_id
    document = db.get(Document, document_id)
    if document is None:
        raise ValueError("Analysis job is missing its document")
    learning = db.get(DocumentLearning, document_id)
    if role == "extract":
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
        document.page_count = len(extraction["pages"])
        db.execute(text("""
            UPDATE analysis_job SET consecutive_failures = 0, first_failure_at = NULL WHERE id = :id
        """), {"id": job.id})
        set_job_stage(db, job, "queued", completed_pages=0, total_pages=document.page_count)
        finish_job(db, job, "pending", stage="queued")
        return

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

        def save_checkpoint(checkpoint: dict) -> None:
            lock_job(db, job)
            learning.pending_batch = deepcopy(checkpoint)
            db.commit()

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
            learning.pending_batch = None
            db.execute(text("""
                UPDATE analysis_job SET consecutive_failures = 0, first_failure_at = NULL WHERE id = :id
            """), {"id": job.id})
            set_job_stage(db, job, "analyzing", completed_pages=len(saved_pages), total_pages=total_pages)

        log_tags = {"document_id": str(document_id), "job_id": str(job.id), "job_attempt": job.attempt}
        gemini = Gemini(log_tags, sink=usage_sink(document_id))
        generate_learning(
            db, gemini, course, learning.extraction, saved_pages=saved_pages,
            on_batch=save_batch, single_batch=True,
            pending_batch=learning.pending_batch, on_checkpoint=save_checkpoint,
            log_tags=log_tags,
        )
    complete = len(saved_pages) == total_pages
    finish_job(db, job, "succeeded" if complete else "pending", stage="completed" if complete else "queued")


def run_job(db, job, role: str) -> None:
    try:
        process(db, job, role)
    except JobLeaseLost:
        raise
    except ProviderError as error:
        db.rollback()
        lock_job(db, job)
        failure = db.execute(text("""
            UPDATE analysis_job SET consecutive_failures = consecutive_failures + 1,
                first_failure_at = COALESCE(first_failure_at, clock_timestamp())
            WHERE id = :id
            RETURNING consecutive_failures,
                EXTRACT(EPOCH FROM first_failure_at + interval '1 hour' - clock_timestamp()) AS remaining
        """), {"id": job.id}).first()
        retry = error.retryable and (
            failure.remaining > 0 if role == "analyze" else failure.consecutive_failures < MAX_ATTEMPTS
        )
        delay = min(30 * 2 ** min(failure.consecutive_failures - 1, 5), 600) if retry else 0
        code = "AI_TEMPORARY_ERROR" if error.retryable else "AI_REQUEST_FAILED"
        message = ("질문 생성 또는 논문 검색에서 일시적인 오류가 발생했습니다. 잠시 후 자동으로 다시 시도합니다."
                   if error.retryable else "질문 생성 요청이 거절되었습니다. 서버 설정을 확인해 주세요.")
        if error.retryable and role == "analyze":
            if retry:
                delay = min(delay, max(1, int(failure.remaining)))
            else:
                code = "AI_RETRY_EXHAUSTED"
                message = "같은 페이지 묶음의 재시도 시간이 1시간을 넘어 분석을 일시 중단했습니다. 다시 시도할 수 있습니다."
        print(f"job {job.id} provider failure: {error}", flush=True)
        finish_job(db, job, "pending" if retry else "failed", stage="queued" if retry else None,
                   delay=delay, error_code=code, error_message=message)
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
    role = sys.argv[1] if len(sys.argv) > 1 else "analyze"
    if role not in {"extract", "analyze"}:
        raise SystemExit("worker role must be extract or analyze")
    print(f"worker {WORKER_ID} started", flush=True)
    while True:
        # 이전 워커가 종료돼도 Docling 컨테이너는 남을 수 있어 추출을 겹쳐 실행하지 않는다.
        if role == "extract" and subprocess.check_output(
            ["docker", "ps", "-q", "--filter", "name=ieobom-docling-"], text=True,
        ).strip():
            time.sleep(POLL_INTERVAL_SEC)
            continue
        with SessionLocal() as db:
            recover_jobs(db)
            claimed = claim_job(db, role)
            if claimed is None:
                time.sleep(POLL_INTERVAL_SEC)
                continue
            print(f"claimed job {claimed.id} for document {claimed.document_id}", flush=True)
            stop = Event()
            thread = Thread(target=heartbeat, args=(claimed, stop), daemon=True)
            thread.start()
            try:
                run_job(db, claimed, role)
            except JobLeaseLost:
                db.rollback()
                print(f"job {claimed.id} ownership expired; result discarded", flush=True)
            finally:
                stop.set()
                thread.join(timeout=5)


if __name__ == "__main__":
    main()

import json
import os
import subprocess
import time
from pathlib import Path
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert

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

WORKER_ID = os.environ.get("WORKER_ID", "worker-1")
POLL_INTERVAL_SEC = int(os.environ.get("WORKER_POLL_INTERVAL_SEC", "3"))
MAX_ATTEMPTS = int(os.environ.get("WORKER_MAX_ATTEMPTS", "3"))
# docker.sock으로 host의 docling 이미지를 그대로 실행하기 때문에, -v 경로는 워커 컨테이너가 아니라
# host 기준이어야 한다. 워커 자신도 같은 host 디렉터리를 /work/input, /work/output에 마운트해 둔다.
DOCLING_HOST_DIR = os.environ["DOCLING_HOST_DIR"]
INPUT_DIR = Path("/work/input")

CLAIM_SQL = text("""
    UPDATE analysis_job
    SET status = 'running', stage = 'downloading', completed_pages = NULL, total_pages = NULL,
        locked_by = :worker_id, locked_at = now(), attempt = attempt + 1
    WHERE id = (
        SELECT id FROM analysis_job
        WHERE status = 'pending' AND scheduled_at <= now()
        ORDER BY scheduled_at, id
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    )
    RETURNING id, document_id, attempt
""")


def claim_job(db):
    row = db.execute(CLAIM_SQL, {"worker_id": WORKER_ID}).first()
    db.commit()
    return row


def finish_job(db, job_id, status: str, stage: str | None = None, delay: int = 0) -> None:
    db.execute(text("""
        UPDATE analysis_job
        SET status = :status, stage = COALESCE(:stage, stage), locked_by = NULL, locked_at = NULL,
            scheduled_at = CASE WHEN :delay > 0
                THEN now() + :delay * interval '1 second' ELSE scheduled_at END
        WHERE id = :id
    """), {"status": status, "stage": stage, "id": job_id, "delay": delay})
    db.commit()


def set_job_stage(db, job_id, stage: str, completed_pages=None, total_pages=None) -> None:
    db.execute(
        text("""
            UPDATE analysis_job
            SET stage = :stage, completed_pages = :completed_pages, total_pages = :total_pages,
                locked_at = now()
            WHERE id = :id
        """),
        {"stage": stage, "completed_pages": completed_pages, "total_pages": total_pages, "id": job_id},
    )
    # 별도 API 세션의 폴링에서도 현재 단계를 읽을 수 있어야 한다.
    db.commit()


def run_docling(pdf_path: Path, output_path: Path, document_id) -> dict | None:
    cmd = [
        "docker", "run", "--rm",
        "--cpus", "1.0", "--memory", "4g", "--memory-swap", "4g",
        "-e", "OMP_NUM_THREADS=1", "-e", "MKL_NUM_THREADS=1", "-e", "OPENBLAS_NUM_THREADS=1",
        "-v", f"{DOCLING_HOST_DIR}/input:/work/input:ro",
        "-v", f"{DOCLING_HOST_DIR}/output:/work/output",
        "-v", "ieobom_docling_cache:/root/.cache",
        "ieobom-docling:local",
        "extract", f"/work/input/{pdf_path.name}",
        "--output", str(output_path), "--document-id", str(document_id),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    print(result.stdout, flush=True)
    if result.returncode != 0:
        print(result.stderr, flush=True)
        return None
    payload = json.loads(output_path.read_text(encoding="utf-8"))
    # CLI는 검토용 부분 결과도 남기지만 워커는 완전한 추출만 성공으로 처리한다.
    if any(warning["code"] == "partial_conversion" for warning in payload["warnings"]):
        return None
    return payload


def process(db, job_id, document_id) -> None:
    document = db.get(Document, document_id)
    if document is None:
        raise ValueError("Analysis job is missing its document")
    learning = db.get(DocumentLearning, document_id)
    if learning is None:
        pdf_path = INPUT_DIR / f"{job_id}.pdf"
        try:
            s3.download_file(document.s3_key, pdf_path)
            set_job_stage(db, job_id, "extracting")
            output_path = Path("/work/output") / f"{job_id}.json"
            extraction = run_docling(pdf_path, output_path, document_id)
        finally:
            pdf_path.unlink(missing_ok=True)
        if extraction is None:
            finish_job(db, job_id, "failed")
            return
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
    set_job_stage(db, job_id, "analyzing", completed_pages=0, total_pages=total_pages)
    if learning.result is None:
        if not os.environ.get("GEMINI_API_KEY", "").strip():
            finish_job(db, job_id, "succeeded", stage="analysis_skipped")
            return
        course = db.get(Course, document.course_id)

        def on_progress(completed: int) -> None:
            set_job_stage(db, job_id, "analyzing", completed_pages=completed, total_pages=total_pages)

        result = generate_learning(db, Gemini(), course, learning.extraction, on_progress=on_progress)
        page_ids = dict(db.execute(select(DocumentPage.page_number, DocumentPage.id).where(
            DocumentPage.document_id == document_id,
        )).all())
        for page in result["pages"].values():
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
        # JSON의 ID와 실제 질문 행을 함께 커밋해야 저장 버튼이 없는 질문을 참조하지 않는다.
        learning.result = result
    db.execute(text("UPDATE analysis_job SET completed_pages = :total WHERE id = :id"),
               {"total": total_pages, "id": job_id})
    finish_job(db, job_id, "succeeded", stage="completed")


def main() -> None:
    print(f"worker {WORKER_ID} started", flush=True)
    while True:
        db = SessionLocal()
        try:
            claimed = claim_job(db)
            if claimed is None:
                time.sleep(POLL_INTERVAL_SEC)
                continue
            print(f"claimed job {claimed.id} for document {claimed.document_id}", flush=True)
            try:
                process(db, claimed.id, claimed.document_id)
            except ProviderError as error:
                db.rollback()
                if error.retryable and claimed.attempt < MAX_ATTEMPTS:
                    delay = min(30 * 2 ** (claimed.attempt - 1), 600)
                    print(f"job {claimed.id} retrying in {delay}s: {error}", flush=True)
                    finish_job(db, claimed.id, "pending", stage="queued", delay=delay)
                else:
                    print(f"job {claimed.id} failed: {error}", flush=True)
                    finish_job(db, claimed.id, "failed")
            except Exception as error:
                print(f"job {claimed.id} failed: {error}", flush=True)
                db.rollback()
                finish_job(db, claimed.id, "failed")
        finally:
            db.close()


if __name__ == "__main__":
    main()

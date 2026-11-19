import os
import subprocess
import time
from pathlib import Path
from uuid import uuid4

from sqlalchemy import text

from app.db.session import SessionLocal
from app.integrations import s3
from app.integrations.gemini import Gemini
from app.integrations.learning_http import ProviderError
from app.models.course import Course
from app.models.document import Document
from app.models.learning import DocumentLearning
from app.pipelines.docling_output import load_docling_extraction
from app.pipelines.learning import generate_learning

WORKER_ID = os.environ.get("WORKER_ID", "worker-1")
POLL_INTERVAL_SEC = int(os.environ.get("WORKER_POLL_INTERVAL_SEC", "3"))
MAX_ATTEMPTS = int(os.environ.get("WORKER_MAX_ATTEMPTS", "3"))
# Docker bind mounts use the host path. The worker sees the same directories under /work.
DOCLING_HOST_DIR = os.environ["DOCLING_HOST_DIR"]
INPUT_DIR = Path("/work/input")
OUTPUT_DIR = Path("/work/output")

CLAIM_SQL = text("""
    UPDATE analysis_job
    SET status = 'running', locked_by = :worker_id, locked_at = now(), attempt = attempt + 1
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


def finish_job(db, job_id, status: str, delay: int = 0) -> None:
    db.execute(text("""
        UPDATE analysis_job
        SET status = :status, locked_by = NULL, locked_at = NULL,
            scheduled_at = CASE WHEN :delay > 0
                THEN now() + :delay * interval '1 second' ELSE scheduled_at END
        WHERE id = :id
    """), {"status": status, "id": job_id, "delay": delay})
    db.commit()


def run_docling(pdf_path: Path, output_dir: Path) -> bool:
    cmd = [
        "docker", "run", "--rm",
        "--cpus", "1.0", "--memory", "4g", "--memory-swap", "4g",
        "-e", "OMP_NUM_THREADS=1", "-e", "MKL_NUM_THREADS=1", "-e", "OPENBLAS_NUM_THREADS=1",
        "-v", f"{DOCLING_HOST_DIR}/input:/work/input:ro",
        "-v", f"{DOCLING_HOST_DIR}/output:/work/output",
        "-v", "ieobom_docling_cache:/root/.cache",
        "ieobom-docling-check:local",
        f"/work/input/{pdf_path.name}", "--all-pages", "--output-dir", str(output_dir),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=900)
    print(result.stdout, flush=True)
    if result.returncode != 0:
        print(result.stderr, flush=True)
    return result.returncode == 0


def process(db, job_id, document_id) -> None:
    document = db.get(Document, document_id)
    if document is None:
        raise ValueError("Analysis job is missing its document")
    learning = db.get(DocumentLearning, document_id)
    if learning is None:
        attempt_path = f"{job_id}-{uuid4().hex}"
        pdf_path = INPUT_DIR / f"{attempt_path}.pdf"
        output_dir = OUTPUT_DIR / attempt_path
        try:
            s3.download_file(document.s3_key, pdf_path)
            if not run_docling(pdf_path, output_dir):
                finish_job(db, job_id, "failed")
                return
            extraction = load_docling_extraction(
                output_dir, pdf_path, str(document_id), document.original_filename,
            )
        finally:
            pdf_path.unlink(missing_ok=True)
        learning = DocumentLearning(document_id=document_id, extraction=extraction)
        db.add(learning)
        db.commit()

    # Deployments without Gemini retain PDF extraction and can backfill these results later.
    if learning.result is None and os.environ.get("GEMINI_API_KEY", "").strip():
        course = db.get(Course, document.course_id)
        learning.result = generate_learning(db, Gemini(), course, learning.extraction)
    finish_job(db, job_id, "succeeded")


def main() -> None:
    print(f"worker {WORKER_ID} started", flush=True)
    while True:
        with SessionLocal() as db:
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
                    finish_job(db, claimed.id, "pending", delay)
                else:
                    print(f"job {claimed.id} failed: {error}", flush=True)
                    finish_job(db, claimed.id, "failed")
            except Exception as error:
                db.rollback()
                print(f"job {claimed.id} failed: {error}", flush=True)
                finish_job(db, claimed.id, "failed")


if __name__ == "__main__":
    main()

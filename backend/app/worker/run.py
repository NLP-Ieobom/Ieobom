import json
import os
import subprocess
import time
from pathlib import Path

from sqlalchemy import text

from app.db.session import SessionLocal
from app.integrations import s3
from app.pipelines.document_analysis import analyze_document

WORKER_ID = os.environ.get("WORKER_ID", "worker-1")
POLL_INTERVAL_SEC = int(os.environ.get("WORKER_POLL_INTERVAL_SEC", "3"))
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
    RETURNING id, document_id
""")


def claim_job(db):
    row = db.execute(CLAIM_SQL, {"worker_id": WORKER_ID}).first()
    db.commit()
    return row


def finish_job(db, job_id, status: str, stage: str | None = None) -> None:
    db.execute(
        text("UPDATE analysis_job SET status = :status, stage = COALESCE(:stage, stage) WHERE id = :id"),
        {"status": status, "stage": stage, "id": job_id},
    )
    db.commit()


def set_job_stage(db, job_id, stage: str, completed_pages=None, total_pages=None) -> None:
    db.execute(
        text("""
            UPDATE analysis_job
            SET stage = :stage, completed_pages = :completed_pages, total_pages = :total_pages
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
    document = db.execute(text("SELECT s3_key FROM document WHERE id = :id"), {"id": document_id}).first()
    pdf_path = INPUT_DIR / f"{document_id}.pdf"
    s3.download_file(document.s3_key, pdf_path)
    set_job_stage(db, job_id, "extracting")
    output_path = Path("/work/output") / f"{job_id}.json"
    extraction = run_docling(pdf_path, output_path, document_id)
    if extraction is None:
        finish_job(db, job_id, "failed")
        return
    db.execute(
        text("UPDATE document SET page_count = :page_count WHERE id = :id"),
        {"page_count": len(extraction["pages"]), "id": document_id},
    )
    set_job_stage(db, job_id, "analyzing", completed_pages=0, total_pages=len(extraction["pages"]))
    analyze_document(extraction)
    finish_job(db, job_id, "succeeded", stage="analysis_skipped")


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
            except Exception as error:
                print(f"job {claimed.id} failed: {error}", flush=True)
                db.rollback()
                finish_job(db, claimed.id, "failed")
        finally:
            db.close()


if __name__ == "__main__":
    main()

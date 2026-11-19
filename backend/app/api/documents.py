import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.integrations import s3
from app.integrations.gemini import Gemini
from app.integrations.learning_http import ProviderError
from app.models.analysis_job import AnalysisJob
from app.models.course import Course
from app.models.document import Document, DocumentStatus
from app.models.learning import DocumentLearning
from app.models.user import User
from app.pipelines.learning import answer_follow_up
from app.schemas.document import (
    CompleteResponse,
    DocumentListResponse,
    DocumentSummary,
    FileUrlResponse,
    StatusResponse,
    UploadUrlRequest,
    UploadUrlResponse,
)
from app.schemas.learning import AskRequest, FollowUpAnswer, PageLearning

router = APIRouter(prefix="/documents", tags=["documents"])


def _get_owned_document(
    db: Session, document_id: uuid.UUID, user: User, *, lock: bool = False,
) -> Document:
    document = db.get(Document, document_id, with_for_update=lock)
    # 다른 사용자의 문서는 403이 아니라 404로 응답한다. 존재 여부를 노출하지 않는다.
    if document is None or document.user_id != user.id:
        raise HTTPException(status_code=404, detail="document not found")
    return document


@router.get("", response_model=DocumentListResponse)
def list_documents(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentListResponse:
    documents = (
        db.query(Document)
        .filter(Document.course_id == course_id, Document.user_id == current_user.id)
        .order_by(Document.created_at.desc())
        .all()
    )
    return DocumentListResponse(
        documents=[
            DocumentSummary(
                document_id=document.id,
                filename=document.original_filename,
                status=document.status,
                created_at=document.created_at,
            )
            for document in documents
        ]
    )


@router.post("/upload-url", response_model=UploadUrlResponse)
def create_upload_url(
    payload: UploadUrlRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> UploadUrlResponse:
    if payload.content_type != "application/pdf":
        raise HTTPException(status_code=400, detail="PDF만 업로드할 수 있다")
    if payload.size_bytes > int(os.environ["MAX_UPLOAD_SIZE"]):
        raise HTTPException(status_code=400, detail="파일이 허용 크기를 넘었다")
    if db.get(Course, payload.course_id) is None:
        raise HTTPException(status_code=404, detail="course not found")

    document = Document(
        user_id=current_user.id,
        course_id=payload.course_id,
        original_filename=payload.filename,
        content_type=payload.content_type,
        size_bytes=payload.size_bytes,
        s3_key="",
        status=DocumentStatus.PENDING_UPLOAD.value,
    )
    db.add(document)
    db.flush()  # s3_key에 document.id를 쓰려면 먼저 id가 있어야 한다
    document.s3_key = s3.build_object_key(document.id, payload.filename)
    db.commit()

    expires_in = int(os.environ["S3_PRESIGNED_PUT_EXPIRE"])
    upload_url = s3.create_presigned_put_url(document.s3_key, payload.content_type)
    return UploadUrlResponse(
        document_id=document.id,
        upload_url=upload_url,
        s3_key=document.s3_key,
        expires_in=expires_in,
    )


@router.post("/{document_id}/complete", response_model=CompleteResponse)
def complete_upload(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CompleteResponse:
    document = _get_owned_document(db, document_id, current_user, lock=True)
    if document.status != DocumentStatus.PENDING_UPLOAD.value:
        raise HTTPException(status_code=409, detail="already completed")

    # 업로드가 서버를 안 거쳐서, S3에 실제로 있는지와 크기가 맞는지 여기서 재확인한다
    head = s3.head_object(document.s3_key)
    if head is None:
        raise HTTPException(status_code=409, detail="object not found in S3 yet")
    if head["ContentLength"] != document.size_bytes:
        raise HTTPException(status_code=409, detail="uploaded size does not match")

    document.status = DocumentStatus.UPLOADED.value
    job = AnalysisJob(document_id=document.id)
    db.add(job)
    db.commit()

    return CompleteResponse(document_id=document.id, status=document.status, job_id=job.id)


@router.get("/{document_id}/status", response_model=StatusResponse)
def get_status(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StatusResponse:
    document = _get_owned_document(db, document_id, current_user)

    job = (
        db.query(AnalysisJob)
        .filter(AnalysisJob.document_id == document_id)
        .order_by(AnalysisJob.created_at.desc())
        .first()
    )
    return StatusResponse(
        document_id=document.id,
        status=document.status,
        job_status=job.status if job else None,
    )


@router.get("/{document_id}/file-url", response_model=FileUrlResponse)
def get_file_url(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FileUrlResponse:
    document = _get_owned_document(db, document_id, current_user)
    if document.status != DocumentStatus.UPLOADED.value:
        raise HTTPException(status_code=409, detail="document not uploaded yet")

    expires_in = int(os.environ["S3_PRESIGNED_GET_EXPIRE"])
    file_url = s3.create_presigned_get_url(document.s3_key)
    return FileUrlResponse(file_url=file_url, expires_in=expires_in)


@router.get("/{document_id}/pages/{page_number}/learning", response_model=PageLearning)
def get_page_learning(
    document_id: uuid.UUID,
    page_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> PageLearning:
    _get_owned_document(db, document_id, current_user)
    learning = db.get(DocumentLearning, document_id)
    if learning is None or learning.result is None:
        raise HTTPException(status_code=404, detail="learning content not available")
    page = learning.result["pages"].get(str(page_number))
    if page is None:
        raise HTTPException(status_code=404, detail="page not found")
    return PageLearning.model_validate(page)


@router.post("/{document_id}/pages/{page_number}/ask", response_model=FollowUpAnswer)
def ask_about_page(
    document_id: uuid.UUID,
    page_number: int,
    payload: AskRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> FollowUpAnswer:
    _get_owned_document(db, document_id, current_user)
    learning = db.get(DocumentLearning, document_id)
    if learning is None or learning.result is None:
        raise HTTPException(status_code=404, detail="learning content not available")
    result = learning.result["pages"].get(str(page_number))
    if result is None:
        raise HTTPException(status_code=404, detail="page not found")
    if not result["analysis"]["question_eligible"]:
        raise HTTPException(status_code=409, detail="page has no eligible lecture content")
    page = next(page for page in learning.extraction["pages"] if page["page_number"] == page_number)
    db.rollback()  # Release the read transaction before the external call.
    if not os.environ.get("GEMINI_API_KEY", "").strip():
        raise HTTPException(status_code=503, detail="follow-up questions are unavailable")
    try:
        return answer_follow_up(Gemini(), page, payload.question)
    except ProviderError:
        raise HTTPException(status_code=502, detail="could not generate a grounded answer") from None

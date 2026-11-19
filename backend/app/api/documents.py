import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.integrations import s3
from app.models.analysis_job import AnalysisJob
from app.models.course import Course
from app.models.document import Document, DocumentStatus
from app.models.document_page import DocumentPage
from app.models.user import User
from app.models.user_note import UserNote
from app.schemas.document import (
    CompleteResponse,
    DocumentListResponse,
    DocumentSummary,
    FileUrlResponse,
    StatusResponse,
    UploadUrlRequest,
    UploadUrlResponse,
)
from app.schemas.note import NoteResponse, NoteUpdateRequest

router = APIRouter(prefix="/documents", tags=["documents"])


def _get_owned_document(db: Session, document_id: uuid.UUID, user: User) -> Document:
    document = db.get(Document, document_id)
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
    document = _get_owned_document(db, document_id, current_user)
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


@router.get("/{document_id}/pages/{page_number}/note", response_model=NoteResponse)
def get_page_note(
    document_id: uuid.UUID,
    page_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteResponse:
    document = _get_owned_document(db, document_id, current_user)
    page = db.query(DocumentPage).filter_by(document_id=document.id, page_number=page_number).first()
    note = db.query(UserNote).filter_by(document_page_id=page.id).first() if page else None
    return NoteResponse(document_id=document.id, page_number=page_number, content=note.content if note else None)


@router.put("/{document_id}/pages/{page_number}/note", response_model=NoteResponse)
def save_page_note(
    document_id: uuid.UUID,
    page_number: int,
    payload: NoteUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> NoteResponse:
    document = _get_owned_document(db, document_id, current_user)

    page = db.query(DocumentPage).filter_by(document_id=document.id, page_number=page_number).first()
    if page is None:
        page = DocumentPage(document_id=document.id, page_number=page_number)
        db.add(page)
        db.flush()  # note의 document_page_id로 쓰려면 먼저 id가 있어야 한다

    note = db.query(UserNote).filter_by(document_page_id=page.id).first()
    if note is None:
        note = UserNote(document_page_id=page.id, content=payload.content)
        db.add(note)
    else:
        note.content = payload.content
    db.commit()

    return NoteResponse(document_id=document.id, page_number=page_number, content=note.content)

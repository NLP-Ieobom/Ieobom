import os
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.integrations import s3
from app.integrations.gemini import Gemini
from app.integrations.learning_http import ProviderError
from app.models.analysis_job import AnalysisJob
from app.models.course import Course
from app.models.document import Document, DocumentStatus
from app.models.document_page import DocumentPage
from app.models.learning import DocumentLearning
from app.models.question import Question
from app.models.reading_progress import UserDocumentProgress, UserPageView
from app.models.saved_question import SavedQuestion
from app.models.user import User
from app.models.user_note import UserNote
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
from app.schemas.note import NoteResponse, NoteUpdateRequest
from app.schemas.learning import AskRequest, FollowUpAnswer, StoredPageLearning
from app.schemas.question import QuestionListResponse, QuestionResponse
from app.schemas.progress import DocumentProgressResponse, ProgressUpdateRequest
from app.services.reading_progress import get_document_progress
from app.services.learning import add_enrollment_status

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
    progress = get_document_progress(db, current_user.id, documents)
    return DocumentListResponse(
        documents=[
            DocumentSummary(
                document_id=document.id,
                filename=document.original_filename,
                status=document.status,
                created_at=document.created_at,
                reading_progress=progress[document.id],
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
    stage = job.stage if job else None
    if document.status == DocumentStatus.PENDING_UPLOAD.value:
        stage = "uploading"
    progress = None
    if job and stage in {"analyzing", "completed"} and job.completed_pages is not None and job.total_pages:
        progress = job.completed_pages * 100 // job.total_pages
    return StatusResponse(
        document_id=document.id,
        status=document.status,
        job_status=job.status if job else None,
        stage=stage,
        completed_pages=job.completed_pages if job else None,
        total_pages=job.total_pages if job else None,
        stage_progress_percent=progress,
        attempt=job.attempt if job else 0,
        error_code=job.error_code if job else None,
        error_message=job.error_message if job else None,
        next_retry_at=job.scheduled_at if job and job.status == "pending" and job.attempt > 0 else None,
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


@router.get("/{document_id}/progress", response_model=DocumentProgressResponse)
def get_reading_progress(
    document_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentProgressResponse:
    document = _get_owned_document(db, document_id, current_user)
    progress = get_document_progress(db, current_user.id, [document])[document.id]
    return DocumentProgressResponse(document_id=document.id, **progress.model_dump())


@router.put("/{document_id}/progress", response_model=DocumentProgressResponse)
def record_page_view(
    document_id: uuid.UUID,
    payload: ProgressUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> DocumentProgressResponse:
    document = _get_owned_document(db, document_id, current_user)
    if document.status != DocumentStatus.UPLOADED.value:
        raise HTTPException(status_code=409, detail="document not uploaded yet")
    if document.page_count is None:
        raise HTTPException(status_code=409, detail="document page count not available yet")
    if payload.page_number > document.page_count:
        raise HTTPException(status_code=422, detail="page number exceeds document page count")

    db.execute(insert(UserPageView).values(
        user_id=current_user.id, document_id=document.id, page_number=payload.page_number,
    ).on_conflict_do_nothing(
        index_elements=[UserPageView.user_id, UserPageView.document_id, UserPageView.page_number],
    ))
    db.execute(insert(UserDocumentProgress).values(
        user_id=current_user.id, document_id=document.id,
        last_page_number=payload.page_number, last_viewed_at=func.clock_timestamp(),
    ).on_conflict_do_update(
        index_elements=[UserDocumentProgress.user_id, UserDocumentProgress.document_id],
        set_={"last_page_number": payload.page_number, "last_viewed_at": func.clock_timestamp()},
    ))
    db.commit()
    progress = get_document_progress(db, current_user.id, [document])[document.id]
    return DocumentProgressResponse(document_id=document.id, **progress.model_dump())


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

    # 추출 워커도 페이지를 만들기 때문에 동시에 실행돼도 같은 페이지 ID를 쓴다.
    page_id = db.execute(insert(DocumentPage).values(
        document_id=document.id, page_number=page_number,
    ).on_conflict_do_update(
        index_elements=[DocumentPage.document_id, DocumentPage.page_number],
        set_={"page_number": page_number},
    ).returning(DocumentPage.id)).scalar_one()

    note = db.query(UserNote).filter_by(document_page_id=page_id).first()
    if note is None:
        note = UserNote(document_page_id=page_id, content=payload.content)
        db.add(note)
    else:
        note.content = payload.content
    db.commit()

    return NoteResponse(document_id=document.id, page_number=page_number, content=note.content)


@router.get("/{document_id}/pages/{page_number}/questions", response_model=QuestionListResponse)
def list_page_questions(
    document_id: uuid.UUID,
    page_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuestionListResponse:
    document = _get_owned_document(db, document_id, current_user)

    page = db.query(DocumentPage).filter_by(document_id=document.id, page_number=page_number).first()
    questions = db.query(Question).filter_by(document_page_id=page.id).all() if page else []
    saved_ids = (
        {row[0] for row in db.query(SavedQuestion.question_id).filter(
            SavedQuestion.question_id.in_([q.id for q in questions])
        )}
        if questions
        else set()
    )

    response = QuestionListResponse(
        questions=[
            QuestionResponse(
                id=question.id,
                document_id=document.id,
                page_number=page_number,
                question_type=question.question_type,
                content=question.content,
                recommended_reason=question.recommended_reason,
                prerequisite=question.prerequisite,
                learning_order=question.learning_order,
                first_activity=question.first_activity,
                created_at=question.created_at,
                is_saved=question.id in saved_ids,
                evidence_block_ids=question.evidence_block_ids,
                evidence_blocks=question.evidence_blocks,
                explanation=question.explanation,
                related_courses=question.related_courses,
                trends=question.trends,
            )
            for question in questions
        ]
    )
    add_enrollment_status(db, current_user.id, response.questions)
    return response


@router.get("/{document_id}/pages/{page_number}/learning", response_model=StoredPageLearning)
def get_page_learning(
    document_id: uuid.UUID,
    page_number: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> StoredPageLearning:
    _get_owned_document(db, document_id, current_user)
    learning = db.get(DocumentLearning, document_id)
    if learning is None or learning.result is None:
        raise HTTPException(status_code=404, detail="learning content not available")
    page = learning.result["pages"].get(str(page_number))
    if page is None:
        raise HTTPException(status_code=404, detail="page not found")
    response = StoredPageLearning.model_validate(page)
    if response.questions:
        saved_ids = {row[0] for row in db.query(SavedQuestion.question_id).filter(
            SavedQuestion.question_id.in_([question.id for question in response.questions]),
        )}
        for question in response.questions:
            question.is_saved = question.id in saved_ids
    add_enrollment_status(db, current_user.id, response.questions)
    return response


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
    db.rollback()  # 외부 호출을 기다리는 동안 조회 트랜잭션을 열어 두지 않는다.
    if not os.environ.get("GEMINI_API_KEY", "").strip():
        raise HTTPException(status_code=503, detail="follow-up questions are unavailable")
    try:
        return answer_follow_up(Gemini(), page, payload.question)
    except ProviderError:
        raise HTTPException(status_code=502, detail="could not generate a grounded answer") from None

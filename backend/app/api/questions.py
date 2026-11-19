from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.saved_question import SavedQuestion
from app.models.user import User
from app.schemas.question import QuestionListResponse, QuestionResponse

router = APIRouter(prefix="/questions", tags=["questions"])


@router.get("", response_model=QuestionListResponse)
def list_saved_questions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuestionListResponse:
    rows = (
        db.query(SavedQuestion, DocumentPage.document_id, DocumentPage.page_number)
        .join(DocumentPage, SavedQuestion.document_page_id == DocumentPage.id)
        .join(Document, DocumentPage.document_id == Document.id)
        .filter(Document.user_id == current_user.id)
        .order_by(SavedQuestion.created_at.desc())
        .all()
    )
    return QuestionListResponse(
        questions=[
            QuestionResponse(
                id=question.id,
                document_id=document_id,
                page_number=page_number,
                content=question.content,
                created_at=question.created_at,
            )
            for question, document_id, page_number in rows
        ]
    )

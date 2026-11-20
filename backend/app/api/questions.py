import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.document import Document
from app.models.document_page import DocumentPage
from app.models.question import Question
from app.models.saved_question import SavedQuestion
from app.models.user import User
from app.schemas.question import QuestionListResponse, QuestionResponse
from app.services.learning import add_enrollment_status

router = APIRouter(prefix="/questions", tags=["questions"])


def _get_owned_question(db: Session, question_id: uuid.UUID, user: User) -> Question:
    question = db.get(Question, question_id)
    if question is None:
        raise HTTPException(status_code=404, detail="question not found")
    page = db.get(DocumentPage, question.document_page_id)
    document = db.get(Document, page.document_id)
    # 다른 사용자의 문서에 달린 질문은 403이 아니라 404로 응답한다. 존재 여부를 노출하지 않는다.
    if document.user_id != user.id:
        raise HTTPException(status_code=404, detail="question not found")
    return question


@router.get("", response_model=QuestionListResponse)
def list_saved_questions(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> QuestionListResponse:
    rows = (
        db.query(Question, DocumentPage.document_id, DocumentPage.page_number)
        .join(SavedQuestion, SavedQuestion.question_id == Question.id)
        .join(DocumentPage, Question.document_page_id == DocumentPage.id)
        .join(Document, DocumentPage.document_id == Document.id)
        .filter(Document.user_id == current_user.id)
        .order_by(SavedQuestion.created_at.desc())
        .all()
    )
    response = QuestionListResponse(
        questions=[
            QuestionResponse(
                id=question.id,
                document_id=document_id,
                page_number=page_number,
                question_type=question.question_type,
                content=question.content,
                recommended_reason=question.recommended_reason,
                prerequisite=question.prerequisite,
                learning_order=question.learning_order,
                first_activity=question.first_activity,
                created_at=question.created_at,
                is_saved=True,
                evidence_block_ids=question.evidence_block_ids,
                evidence_blocks=question.evidence_blocks,
                explanation=question.explanation,
                related_courses=question.related_courses,
                trends=question.trends,
            )
            for question, document_id, page_number in rows
        ]
    )
    add_enrollment_status(db, current_user.id, response.questions)
    return response


@router.put("/{question_id}/save", status_code=204)
def save_question(
    question_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    question = _get_owned_question(db, question_id, current_user)
    if db.query(SavedQuestion).filter_by(question_id=question.id).first() is None:
        db.add(SavedQuestion(question_id=question.id))
        db.commit()


@router.delete("/{question_id}/save", status_code=204)
def unsave_question(
    question_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> None:
    question = _get_owned_question(db, question_id, current_user)
    db.query(SavedQuestion).filter_by(question_id=question.id).delete()
    db.commit()

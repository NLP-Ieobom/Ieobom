import uuid

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models.document import Document, DocumentStatus
from app.models.reading_progress import UserDocumentProgress, UserPageView
from app.schemas.progress import DocumentReadingProgress, ReadingProgress


def get_document_progress(
    db: Session, user_id: uuid.UUID, documents: list[Document],
) -> dict[uuid.UUID, DocumentReadingProgress]:
    document_ids = [document.id for document in documents]
    counts = dict(
        db.query(UserPageView.document_id, func.count())
        .filter(UserPageView.user_id == user_id, UserPageView.document_id.in_(document_ids))
        .group_by(UserPageView.document_id)
        .all()
    )
    positions = {
        progress.document_id: progress
        for progress in db.query(UserDocumentProgress).filter(
            UserDocumentProgress.user_id == user_id,
            UserDocumentProgress.document_id.in_(document_ids),
        ).all()
    }
    result = {}
    for document in documents:
        viewed = counts.get(document.id, 0)
        position = positions.get(document.id)
        result[document.id] = DocumentReadingProgress(
            viewed_pages=viewed,
            total_pages=document.page_count,
            progress_percent=round(viewed * 100 / document.page_count, 2) if document.page_count else None,
            last_page_number=position.last_page_number if position else None,
            last_viewed_at=position.last_viewed_at if position else None,
        )
    return result


def get_course_progress(
    db: Session, user_id: uuid.UUID, course_ids: list[uuid.UUID],
) -> dict[uuid.UUID, ReadingProgress]:
    documents = db.query(Document).filter(
        Document.user_id == user_id,
        Document.course_id.in_(course_ids),
        Document.status == DocumentStatus.UPLOADED.value,
    ).all()
    document_progress = get_document_progress(db, user_id, documents)
    result = {
        course_id: ReadingProgress(viewed_pages=0, total_pages=0, progress_percent=None)
        for course_id in course_ids
    }
    for document in documents:
        progress = result[document.course_id]
        progress.viewed_pages += document_progress[document.id].viewed_pages
        # 일부 PDF의 페이지 수가 없으면 과목 전체 비율을 아직 계산할 수 없다.
        if document.page_count is None:
            progress.total_pages = None
        elif progress.total_pages is not None:
            progress.total_pages += document.page_count
    for progress in result.values():
        if progress.total_pages:
            progress.progress_percent = round(progress.viewed_pages * 100 / progress.total_pages, 2)
    return result

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.user_course import UserCourse


def add_enrollment_status(db: Session, user_id: UUID, questions) -> None:
    links = [link for question in questions for link in question.related_courses]
    if not links:
        return
    statuses = dict(db.execute(select(UserCourse.course_id, UserCourse.status).where(
        UserCourse.user_id == user_id,
        UserCourse.course_id.in_({UUID(link.course_id) for link in links}),
    )).all())
    # 분석 후 수강 상태를 바꿔도 최신 값이 보이도록 조회할 때 붙인다.
    for link in links:
        link.enrollment_status = statuses.get(UUID(link.course_id), "not_enrolled")

import uuid

from sqlalchemy import CheckConstraint, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class CourseRelation(Base):
    __tablename__ = "course_relation"
    __table_args__ = (
        UniqueConstraint("source_course_id", "target_course_id", "relation_type", "source", name="uq_course_relation"),
        CheckConstraint("source_course_id <> target_course_id", name="ck_course_relation_distinct_courses"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    source_course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course.id"))
    target_course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course.id"))
    relation_type: Mapped[str] = mapped_column(String(30))
    source: Mapped[str] = mapped_column(String(30))
    # 왜 이 순서로 이어지는지. 교육과정표와 강의계획서를 보고 적은 잠정 추천이라 과목마다 근거가 다르다.
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(20), nullable=True)

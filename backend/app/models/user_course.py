import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserCourse(Base):
    __tablename__ = "user_course"
    __table_args__ = (
        UniqueConstraint("user_id", "course_id"),
        CheckConstraint("status IN ('in_progress', 'completed')", name="ck_user_course_status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course.id"))
    status: Mapped[str] = mapped_column(String(20), default="in_progress", server_default="in_progress")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

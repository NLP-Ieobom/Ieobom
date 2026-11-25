import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Course(Base):
    __tablename__ = "course"
    __table_args__ = (UniqueConstraint("curriculum_id", "course_code", name="uq_course_curriculum_code"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    curriculum_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("curriculum.id"), nullable=True, index=True)
    course_code: Mapped[str | None] = mapped_column(String(50), nullable=True)
    name: Mapped[str] = mapped_column(String(255))
    curriculum_year: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 교육과정표에 배치된 학년. 두 학년에 걸친 과목은 없다.
    year_level: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # 같은 학년의 1학기와 2학기 양쪽에 열리는 과목이 있어서 학기는 목록으로 둔다.
    semesters: Mapped[list[int]] = mapped_column(JSONB, default=list, server_default="[]")
    # 교육과정표의 영역. 두 영역에 걸친 과목과 어느 영역에도 없는 과목이 있어서 목록으로 둔다.
    areas: Mapped[list[str]] = mapped_column(JSONB, default=list, server_default="[]")
    # 과목별 연구 동향 기능 on/off
    is_trend_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

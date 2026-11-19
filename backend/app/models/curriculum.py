import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Integer, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Curriculum(Base):
    __tablename__ = "curriculum"
    __table_args__ = (UniqueConstraint("institution", "department", "entry_year", name="uq_curriculum_identity"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    institution: Mapped[str] = mapped_column(String(255))
    department: Mapped[str] = mapped_column(String(255))
    entry_year: Mapped[int] = mapped_column(Integer)
    is_demo: Mapped[bool] = mapped_column(Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

import uuid
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserDocumentProgress(Base):
    __tablename__ = "user_document_progress"
    __table_args__ = (CheckConstraint("last_page_number > 0", name="ck_document_progress_page_number"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"), primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document.id"), primary_key=True)
    last_page_number: Mapped[int] = mapped_column(Integer)
    last_viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class UserPageView(Base):
    __tablename__ = "user_page_view"
    __table_args__ = (CheckConstraint("page_number > 0", name="ck_page_view_page_number"),)

    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"), primary_key=True)
    document_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document.id"), primary_key=True)
    page_number: Mapped[int] = mapped_column(Integer, primary_key=True)
    first_viewed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

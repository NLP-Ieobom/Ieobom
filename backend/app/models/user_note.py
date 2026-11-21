import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserNote(Base):
    __tablename__ = "user_note"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # 페이지 하나에 메모는 하나다. document_page.id가 소유자(document.user_id)를 결정한다.
    document_page_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_page.id", ondelete="CASCADE"), unique=True)
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

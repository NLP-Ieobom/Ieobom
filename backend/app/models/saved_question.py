import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class SavedQuestion(Base):
    __tablename__ = "saved_question"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # course/document는 document_page -> document를 통해 구한다. 따로 들고 있지 않는다.
    document_page_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("document_page.id"))
    content: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

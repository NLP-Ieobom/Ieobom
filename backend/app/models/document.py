import enum
import uuid
from datetime import datetime

from sqlalchemy import BigInteger, DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class DocumentStatus(str, enum.Enum):
    PENDING_UPLOAD = "pending_upload"
    UPLOADED = "uploaded"


class Document(Base):
    __tablename__ = "document"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("user.id"))
    # 업로드 흐름상 과목 선택이 먼저라 필수다 (architecture.md 업로드 흐름 1번)
    course_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("course.id"))
    original_filename: Mapped[str] = mapped_column(String(255))
    content_type: Mapped[str] = mapped_column(String(100))
    size_bytes: Mapped[int] = mapped_column(BigInteger)
    s3_key: Mapped[str] = mapped_column(String(512), unique=True)
    status: Mapped[str] = mapped_column(String(20), default=DocumentStatus.PENDING_UPLOAD.value)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

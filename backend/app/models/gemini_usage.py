import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class GeminiUsage(Base):
    __tablename__ = "gemini_usage"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    # 문서를 지워도 비용 기록은 남긴다. 과목 임베딩과 연구 동향은 문서 없이도 발생해서 NULL이다.
    document_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("document.id", ondelete="SET NULL"))
    call: Mapped[str] = mapped_column(String(30))
    model: Mapped[str] = mapped_column(String(60))
    attempt: Mapped[int]
    # 응답에 usageMetadata가 없으면 0이 아니라 NULL이어야 평균이 오염되지 않는다
    prompt_tokens: Mapped[int | None]
    output_tokens: Mapped[int | None]
    thought_tokens: Mapped[int | None]
    cached_tokens: Mapped[int | None]
    elapsed_ms: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

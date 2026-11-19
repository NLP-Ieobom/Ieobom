import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, String, Uuid
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.integrations.gemini import EMBEDDING_DIM


class DocumentLearning(Base):
    __tablename__ = "document_learning"

    document_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("document.id", ondelete="CASCADE"), primary_key=True
    )
    extraction: Mapped[dict] = mapped_column(JSONB)
    result: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class CourseLearningProfile(Base):
    __tablename__ = "course_learning_profile"

    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course.id", ondelete="CASCADE"), primary_key=True
    )
    corpus_id: Mapped[str] = mapped_column(String(255), unique=True)
    topics: Mapped[list[str]] = mapped_column(JSONB)
    embedding_model: Mapped[str] = mapped_column(String(100))
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))


class CourseResearchCache(Base):
    __tablename__ = "course_research_cache"

    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("course.id", ondelete="CASCADE"), primary_key=True
    )
    searched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    papers: Mapped[list[dict]] = mapped_column(JSONB)

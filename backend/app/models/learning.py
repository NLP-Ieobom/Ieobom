import uuid
from datetime import datetime

from pgvector.sqlalchemy import Vector
from sqlalchemy import DateTime, ForeignKey, Integer, String, Uuid
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
    pending_batch: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    research_topics: Mapped[list[dict]] = mapped_column(JSONB, default=list)


class CourseLearningProfile(Base):
    __tablename__ = "course_learning_profile"

    course_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("course.id", ondelete="CASCADE"), primary_key=True
    )
    corpus_id: Mapped[str] = mapped_column(String(255), unique=True)
    topics: Mapped[list[str]] = mapped_column(JSONB)
    # 교육과정에서 가장 이른 학년·학기를 학년 * 10 + 학기로 저장한다. 3학년 2학기는 32다.
    # 이전에 들은 과목과 이후에 들을 과목을 나눠 검색할 때 쓴다. 편성 정보가 없으면 비어 있다.
    semester_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    embedding_model: Mapped[str] = mapped_column(String(100))
    embedding: Mapped[list[float]] = mapped_column(Vector(EMBEDDING_DIM))


class CourseResearchCache(Base):
    __tablename__ = "course_research_cache"

    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("course.id", ondelete="CASCADE"), primary_key=True
    )
    searched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    papers: Mapped[list[dict]] = mapped_column(JSONB)


class ResearchQueryCache(Base):
    __tablename__ = "research_query_cache"

    course_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(), ForeignKey("course.id", ondelete="CASCADE"), primary_key=True
    )
    query: Mapped[str] = mapped_column(String(200), primary_key=True)
    searched_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    papers: Mapped[list[dict]] = mapped_column(JSONB)

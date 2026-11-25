import uuid

from pydantic import BaseModel

from app.schemas.course import CourseWithEnrollment


class CurriculumSummary(BaseModel):
    id: uuid.UUID
    institution: str
    department: str
    entry_year: int
    is_demo: bool


class CurriculumListResponse(BaseModel):
    curricula: list[CurriculumSummary]


class CourseRelationResponse(BaseModel):
    id: uuid.UUID
    source_course_id: uuid.UUID
    target_course_id: uuid.UUID
    relation_type: str
    source: str
    reason: str | None
    confidence: str | None


class CurriculumMapResponse(BaseModel):
    curriculum: CurriculumSummary
    courses: list[CourseWithEnrollment]
    relations: list[CourseRelationResponse]

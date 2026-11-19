import uuid
from typing import Literal

from pydantic import BaseModel

from app.schemas.progress import ReadingProgress


class CourseSummary(BaseModel):
    id: uuid.UUID
    curriculum_id: uuid.UUID | None
    name: str
    course_code: str | None
    curriculum_year: int | None


class CourseListResponse(BaseModel):
    courses: list[CourseSummary]


class CourseWithEnrollment(CourseSummary):
    enrollment_status: Literal["not_enrolled", "in_progress", "completed"]
    reading_progress: ReadingProgress


class MyCourseListResponse(BaseModel):
    courses: list[CourseWithEnrollment]


class EnrollmentUpdateRequest(BaseModel):
    status: Literal["in_progress", "completed"]


class EnrollmentResponse(BaseModel):
    course_id: uuid.UUID
    status: Literal["in_progress", "completed"]

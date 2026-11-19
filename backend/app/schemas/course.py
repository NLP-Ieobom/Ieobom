import uuid

from pydantic import BaseModel


class CourseSummary(BaseModel):
    id: uuid.UUID
    name: str
    course_code: str | None
    curriculum_year: int | None


class CourseListResponse(BaseModel):
    courses: list[CourseSummary]

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.course import Course
from app.schemas.course import CourseListResponse, CourseSummary

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", response_model=CourseListResponse, dependencies=[Depends(get_current_user)])
def list_courses(db: Session = Depends(get_db)) -> CourseListResponse:
    # DB 기본 로케일에서는 한글 과목명이 가나다순으로 나오지 않을 수 있다.
    courses = db.query(Course).order_by(Course.name.collate("C"), Course.id).all()
    return CourseListResponse(
        courses=[
            CourseSummary(
                id=course.id,
                name=course.name,
                course_code=course.course_code,
                curriculum_year=course.curriculum_year,
            )
            for course in courses
        ]
    )

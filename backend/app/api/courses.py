from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.course import Course
from app.models.user import User
from app.models.user_course import UserCourse
from app.schemas.course import CourseListResponse, CourseSummary, MyCourseListResponse

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


@router.get("/me", response_model=MyCourseListResponse)
def list_my_courses(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MyCourseListResponse:
    courses = (
        db.query(Course)
        .join(UserCourse, UserCourse.course_id == Course.id)
        .filter(UserCourse.user_id == current_user.id)
        .order_by(Course.name.collate("C"), Course.id)
        .all()
    )
    return MyCourseListResponse(
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

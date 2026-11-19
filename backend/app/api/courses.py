import uuid

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.course import Course
from app.models.curriculum import Curriculum
from app.models.user import User
from app.models.user_course import UserCourse
from app.schemas.course import (
    CourseListResponse,
    CourseSummary,
    CourseWithEnrollment,
    EnrollmentResponse,
    EnrollmentUpdateRequest,
    MyCourseListResponse,
)
from app.services.reading_progress import get_course_progress

router = APIRouter(prefix="/courses", tags=["courses"])


@router.get("", response_model=CourseListResponse, dependencies=[Depends(get_current_user)])
def list_courses(
    curriculum_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
) -> CourseListResponse:
    query = db.query(Course)
    if curriculum_id is not None:
        if db.get(Curriculum, curriculum_id) is None:
            raise HTTPException(status_code=404, detail="curriculum not found")
        query = query.filter(Course.curriculum_id == curriculum_id)
    # DB 기본 로케일에서는 한글 과목명이 가나다순으로 나오지 않을 수 있다.
    courses = query.order_by(Course.name.collate("C"), Course.id).all()
    return CourseListResponse(
        courses=[
            CourseSummary(
                id=course.id,
                curriculum_id=course.curriculum_id,
                name=course.name,
                course_code=course.course_code,
                curriculum_year=course.curriculum_year,
            )
            for course in courses
        ]
    )


@router.get("/me", response_model=MyCourseListResponse)
def list_my_courses(
    curriculum_id: uuid.UUID | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> MyCourseListResponse:
    query = (
        db.query(Course, UserCourse.status)
        .join(UserCourse, UserCourse.course_id == Course.id)
        .filter(UserCourse.user_id == current_user.id)
    )
    if curriculum_id is not None:
        if db.get(Curriculum, curriculum_id) is None:
            raise HTTPException(status_code=404, detail="curriculum not found")
        query = query.filter(Course.curriculum_id == curriculum_id)
    courses = query.order_by(Course.name.collate("C"), Course.id).all()
    progress = get_course_progress(db, current_user.id, [course.id for course, _ in courses])
    return MyCourseListResponse(
        courses=[
            CourseWithEnrollment(
                id=course.id,
                curriculum_id=course.curriculum_id,
                name=course.name,
                course_code=course.course_code,
                curriculum_year=course.curriculum_year,
                enrollment_status=status,
                reading_progress=progress[course.id],
            )
            for course, status in courses
        ]
    )


@router.put("/{course_id}/enrollment", response_model=EnrollmentResponse)
def set_enrollment(
    course_id: uuid.UUID,
    payload: EnrollmentUpdateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> EnrollmentResponse:
    if db.get(Course, course_id) is None:
        raise HTTPException(status_code=404, detail="course not found")
    statement = insert(UserCourse).values(user_id=current_user.id, course_id=course_id, status=payload.status)
    db.execute(statement.on_conflict_do_update(
        index_elements=[UserCourse.user_id, UserCourse.course_id],
        set_={"status": payload.status},
    ))
    db.commit()
    return EnrollmentResponse(course_id=course_id, status=payload.status)


@router.delete("/{course_id}/enrollment", status_code=204)
def remove_enrollment(
    course_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> Response:
    if db.get(Course, course_id) is None:
        raise HTTPException(status_code=404, detail="course not found")
    db.query(UserCourse).filter_by(user_id=current_user.id, course_id=course_id).delete()
    db.commit()
    return Response(status_code=204)

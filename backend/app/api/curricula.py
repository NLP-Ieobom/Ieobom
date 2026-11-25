import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import and_
from sqlalchemy.orm import Session

from app.core.deps import get_current_user
from app.db.session import get_db
from app.models.course import Course
from app.models.course_relation import CourseRelation
from app.models.curriculum import Curriculum
from app.models.user import User
from app.models.user_course import UserCourse
from app.schemas.course import CourseWithEnrollment
from app.schemas.curriculum import (
    CourseRelationResponse,
    CurriculumListResponse,
    CurriculumMapResponse,
    CurriculumSummary,
)
from app.services.reading_progress import get_course_progress

router = APIRouter(prefix="/curricula", tags=["curricula"])


@router.get("", response_model=CurriculumListResponse, dependencies=[Depends(get_current_user)])
def list_curricula(db: Session = Depends(get_db)) -> CurriculumListResponse:
    curricula = db.query(Curriculum).order_by(
        Curriculum.is_demo,
        Curriculum.institution.collate("C"),
        Curriculum.department.collate("C"),
        Curriculum.entry_year.desc(),
        Curriculum.id,
    ).all()
    return CurriculumListResponse(
        curricula=[
            CurriculumSummary(
                id=curriculum.id,
                institution=curriculum.institution,
                department=curriculum.department,
                entry_year=curriculum.entry_year,
                is_demo=curriculum.is_demo,
            )
            for curriculum in curricula
        ]
    )


@router.get("/{curriculum_id}/map", response_model=CurriculumMapResponse)
def get_curriculum_map(
    curriculum_id: uuid.UUID,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
) -> CurriculumMapResponse:
    curriculum = db.get(Curriculum, curriculum_id)
    if curriculum is None:
        raise HTTPException(status_code=404, detail="curriculum not found")
    courses = (
        db.query(Course, UserCourse.status)
        .outerjoin(UserCourse, and_(UserCourse.course_id == Course.id, UserCourse.user_id == current_user.id))
        .filter(Course.curriculum_id == curriculum.id)
        .order_by(Course.name.collate("C"), Course.id)
        .all()
    )
    course_ids = [course.id for course, _ in courses]
    progress = get_course_progress(db, current_user.id, course_ids)
    relations = (
        db.query(CourseRelation)
        .filter(
            CourseRelation.source_course_id.in_(course_ids),
            CourseRelation.target_course_id.in_(course_ids),
        )
        .order_by(CourseRelation.source_course_id, CourseRelation.target_course_id, CourseRelation.id)
        .all()
    )
    return CurriculumMapResponse(
        curriculum=CurriculumSummary(
            id=curriculum.id,
            institution=curriculum.institution,
            department=curriculum.department,
            entry_year=curriculum.entry_year,
            is_demo=curriculum.is_demo,
        ),
        courses=[
            CourseWithEnrollment(
                id=course.id,
                curriculum_id=course.curriculum_id,
                name=course.name,
                course_code=course.course_code,
                curriculum_year=course.curriculum_year,
                year_level=course.year_level,
                semesters=course.semesters,
                areas=course.areas,
                enrollment_status=status if status is not None else "not_enrolled",
                reading_progress=progress[course.id],
            )
            for course, status in courses
        ],
        relations=[
            CourseRelationResponse(
                id=relation.id,
                source_course_id=relation.source_course_id,
                target_course_id=relation.target_course_id,
                relation_type=relation.relation_type,
                source=relation.source,
                reason=relation.reason,
                confidence=relation.confidence,
            )
            for relation in relations
        ],
    )

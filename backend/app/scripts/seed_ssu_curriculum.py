import json
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.course import Course
from app.models.course_relation import CourseRelation
from app.models.curriculum import Curriculum


GRAPH_PATH = Path(__file__).resolve().parents[1] / "data" / "ssu_ai_software_2026.json"
RELATION_TYPE = "recommended"
RELATION_SOURCE = "ssu_2026_provisional"


def seed_curriculum(db: Session, graph: dict) -> uuid.UUID:
    identity = {
        "institution": graph["institution"],
        "department": graph["department"],
        "entry_year": graph["curriculum_entry_year"],
    }
    curriculum = db.scalars(select(Curriculum).filter_by(**identity).with_for_update()).one_or_none()
    if curriculum is None:
        curriculum = Curriculum(
            id=uuid.uuid5(uuid.NAMESPACE_URL, f"ieobom:curriculum:{graph['graph_id']}"),
            **identity,
            is_demo=False,
        )
        db.add(curriculum)
        db.flush()

    courses = db.scalars(select(Course).filter_by(curriculum_id=curriculum.id)).all()
    courses_by_id = {course.id: course for course in courses}
    courses_by_code = {course.course_code: course for course in courses if course.course_code}
    course_ids = {}
    for node in graph["nodes"]:
        stable_id = uuid.uuid5(curriculum.id, node["curriculum_id"])
        course_code = node["course_code"]
        course = courses_by_id.get(stable_id) or courses_by_code.get(course_code)
        if course is None and course_code is None:
            # 기존 코퍼스 임포터는 코드가 없는 과목을 과목명으로 연결한다.
            matches = [row for row in courses if row.course_code is None and row.name == node["name"]]
            if len(matches) > 1:
                raise ValueError(f"Ambiguous course mapping: {node['course_id']}")
            course = next(iter(matches), None)
        if course is None:
            course = Course(id=stable_id, curriculum_id=curriculum.id)
            db.add(course)
        course.name = node["name"]
        course.course_code = course_code
        course.curriculum_year = curriculum.entry_year
        course.year_level = min(placement["year"] for placement in node["placements"])
        course.semesters = sorted({placement["semester"] for placement in node["placements"]})
        course.areas = node["official_areas"]
        course_ids[node["course_id"]] = course.id
    db.flush()

    edges = {
        (course_ids[edge["from_course_id"]], course_ids[edge["to_course_id"]]): edge
        for edge in graph["edges"]
    }
    curriculum_course_ids = select(Course.id).where(Course.curriculum_id == curriculum.id)
    existing = db.scalars(
        select(CourseRelation).filter_by(relation_type=RELATION_TYPE, source=RELATION_SOURCE).where(
            CourseRelation.source_course_id.in_(curriculum_course_ids),
            CourseRelation.target_course_id.in_(curriculum_course_ids),
        )
    ).all()
    for relation in existing:
        edge = edges.pop((relation.source_course_id, relation.target_course_id), None)
        if edge is None:
            db.delete(relation)
            continue
        relation.reason = edge["reason"]
        relation.confidence = edge["confidence"]
    for (source_id, target_id), edge in sorted(edges.items()):
        db.add(CourseRelation(
            id=uuid.uuid5(curriculum.id, f"{RELATION_SOURCE}:{source_id}:{target_id}"),
            source_course_id=source_id,
            target_course_id=target_id,
            relation_type=RELATION_TYPE,
            source=RELATION_SOURCE,
            reason=edge["reason"],
            confidence=edge["confidence"],
        ))
    return curriculum.id


def main() -> None:
    from app.db.session import SessionLocal

    graph = json.loads(GRAPH_PATH.read_text(encoding="utf-8"))
    with SessionLocal.begin() as db:
        curriculum_id = seed_curriculum(db, graph)
    print(f"{graph['title']} ({curriculum_id}): {len(graph['nodes'])}과목, 추천 연결 {len(graph['edges'])}개")


if __name__ == "__main__":
    main()

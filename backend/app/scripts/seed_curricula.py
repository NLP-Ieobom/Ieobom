import uuid

from app.db.session import SessionLocal
from app.models.course import Course
from app.models.course_relation import CourseRelation
from app.models.curriculum import Curriculum


COURSES = [
    ("demo:business:management", "DEMO-BUS-001", "경영학원론"),
    ("demo:business:accounting", "DEMO-BUS-002", "회계원리"),
    ("demo:business:marketing", "DEMO-BUS-003", "마케팅원론"),
    ("demo:business:finance", "DEMO-BUS-004", "재무관리"),
    ("demo:business:organization", "DEMO-BUS-005", "조직행동론"),
]

# 화면 연결을 확인하기 위한 임의 관계이며 실제 선수과목 자료가 아니다.
RELATIONS = [
    ("DEMO-BUS-001", "DEMO-BUS-003"),
    ("DEMO-BUS-001", "DEMO-BUS-005"),
    ("DEMO-BUS-002", "DEMO-BUS-004"),
]


def main() -> None:
    with SessionLocal.begin() as db:
        curriculum = db.query(Curriculum).filter_by(
            institution="데모대학교", department="경영학부", entry_year=2026,
        ).one_or_none()
        if curriculum is None:
            curriculum = Curriculum(
                id=uuid.uuid5(uuid.NAMESPACE_URL, "ieobom:curriculum:데모대학교:경영학부:2026"),
                institution="데모대학교", department="경영학부", entry_year=2026, is_demo=True,
            )
            db.add(curriculum)
            db.flush()

        course_ids = {}
        for key, code, name in COURSES:
            course_id = uuid.uuid5(curriculum.id, key)
            course_ids[code] = course_id
            course = db.get(Course, course_id)
            if course is None:
                course = Course(id=course_id)
                db.add(course)
            course.curriculum_id = curriculum.id
            course.course_code = code
            course.name = name
            course.curriculum_year = curriculum.entry_year
        db.flush()

        for source_code, target_code in RELATIONS:
            relation_id = uuid.uuid5(curriculum.id, f"demo:relation:{source_code}:{target_code}")
            if db.get(CourseRelation, relation_id) is None:
                db.add(CourseRelation(
                    id=relation_id,
                    source_course_id=course_ids[source_code],
                    target_course_id=course_ids[target_code],
                    relation_type="recommended",
                    source="demo",
                ))

    print(f"데모대학교 경영학부 2026: {len(COURSES)}과목, 데모 연결 {len(RELATIONS)}개")


if __name__ == "__main__":
    main()

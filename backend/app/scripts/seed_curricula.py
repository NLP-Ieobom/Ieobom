import uuid

from app.db.session import SessionLocal
from app.models.course import Course
from app.models.course_relation import CourseRelation
from app.models.curriculum import Curriculum


# 학년·학기·세부전공은 학습 흐름을 보여 주기 위한 시연용 편성이다.
COURSES = [
    ("demo:business:management", "DEMO-BUS-001", "경영학원론", 1, [1], ["경영공통"]),
    ("demo:business:accounting", "DEMO-BUS-002", "회계원리", 1, [2], ["회계·재무"]),
    ("demo:business:marketing", "DEMO-BUS-003", "마케팅원론", 2, [1], ["마케팅"]),
    ("demo:business:finance", "DEMO-BUS-004", "재무관리", 2, [2], ["회계·재무"]),
    ("demo:business:organization", "DEMO-BUS-005", "조직행동론", 2, [1], ["인사·조직"]),
    ("demo:business:statistics", "DEMO-BUS-006", "경영통계학", 1, [2], ["경영데이터분석"]),
    ("demo:business:consumer", "DEMO-BUS-007", "소비자행동론", 3, [1], ["마케팅"]),
    ("demo:business:strategy", "DEMO-BUS-008", "경영전략", 4, [1], ["경영전략", "인사·조직"]),
]

# 연결은 개념을 먼저 익히면 도움이 되는 방향이며 공식 선수과목 관계가 아니다.
RELATIONS = [
    ("DEMO-BUS-001", "DEMO-BUS-002",
     "기업의 활동과 이해관계자를 먼저 이해하면 거래를 기록하고 재무제표로 경영 성과를 설명하는 목적을 파악하기 쉽다."),
    ("DEMO-BUS-001", "DEMO-BUS-006",
     "경영 의사결정과 성과 지표를 배운 뒤 매출·고객 데이터를 요약하고 불확실성을 수치로 해석한다."),
    ("DEMO-BUS-001", "DEMO-BUS-003",
     "기업의 가치 창출과 경영 환경을 바탕으로 고객 요구, 시장 세분화, 표적시장과 마케팅 믹스를 구체화한다."),
    ("DEMO-BUS-001", "DEMO-BUS-005",
     "계획·조직·지휘·통제라는 경영 기능을 익힌 뒤 구성원의 동기부여, 리더십과 팀 의사결정을 살펴본다."),
    ("DEMO-BUS-002", "DEMO-BUS-004",
     "재무제표의 자산·부채·이익과 현금흐름을 읽는 능력을 투자안 평가, 자금 조달과 기업가치 판단에 사용한다."),
    ("DEMO-BUS-006", "DEMO-BUS-004",
     "확률, 기댓값, 분산과 상관관계를 바탕으로 투자 수익률의 불확실성과 포트폴리오 분산투자 효과를 해석한다."),
    ("DEMO-BUS-006", "DEMO-BUS-003",
     "표본 추출과 기술통계를 알면 시장조사 결과를 읽고 고객 집단의 차이와 마케팅 성과를 비교할 수 있다."),
    ("DEMO-BUS-003", "DEMO-BUS-007",
     "시장 세분화와 포지셔닝에서 사용한 고객 구분을 소비자의 지각, 태도, 구매 의사결정 과정으로 설명한다."),
    ("DEMO-BUS-005", "DEMO-BUS-007",
     "개인의 동기와 집단 영향에 대한 이해를 소비자 맥락에 옮겨 준거집단, 구전과 사회적 영향이 구매에 미치는 효과를 비교한다."),
    ("DEMO-BUS-006", "DEMO-BUS-007",
     "가설검정과 상관·회귀분석을 바탕으로 소비자 설문과 구매 데이터를 읽고 태도와 구매 행동의 관계를 검토한다."),
    ("DEMO-BUS-003", "DEMO-BUS-008",
     "시장·경쟁사 분석과 포지셔닝을 연결해 어떤 고객에게 어떤 차별적 가치를 제공할지 경쟁전략을 세운다."),
    ("DEMO-BUS-004", "DEMO-BUS-008",
     "투자안의 수익성, 자본비용과 현금흐름을 비교해 신규 사업 진출과 사업 간 자원 배분의 타당성을 판단한다."),
    ("DEMO-BUS-005", "DEMO-BUS-008",
     "조직 구조, 리더십과 조직문화를 바탕으로 선택한 전략을 실행할 때 필요한 역할 조정과 변화관리를 설계한다."),
    ("DEMO-BUS-007", "DEMO-BUS-008",
     "고객의 선택 기준, 브랜드 태도와 전환 행동을 근거로 차별화 방향과 고객 유지 중심의 성장전략을 검토한다."),
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
        for key, code, name, year_level, semesters, areas in COURSES:
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
            course.year_level = year_level
            course.semesters = semesters
            course.areas = areas
        db.flush()

        for source_code, target_code, reason in RELATIONS:
            relation_id = uuid.uuid5(curriculum.id, f"demo:relation:{source_code}:{target_code}")
            relation = db.get(CourseRelation, relation_id)
            if relation is None:
                relation = CourseRelation(
                    id=relation_id,
                    source_course_id=course_ids[source_code],
                    target_course_id=course_ids[target_code],
                    relation_type="recommended",
                    source="demo",
                )
                db.add(relation)
            relation.reason = reason
            relation.confidence = "medium"

    print(f"데모대학교 경영학부 2026: {len(COURSES)}과목, 데모 연결 {len(RELATIONS)}개")


if __name__ == "__main__":
    main()

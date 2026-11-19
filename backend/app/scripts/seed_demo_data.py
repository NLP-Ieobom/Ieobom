import os
import sys

from app.db.session import SessionLocal
from app.models import course  # noqa: F401  # Document/UserCourse의 course_id FK가 가리키는 테이블을 등록하려고 import
from app.models.document import Document, DocumentStatus
from app.models.document_page import DocumentPage
from app.models.question import Question
from app.models.saved_question import SavedQuestion
from app.models.user import User
from app.models.user_course import UserCourse
from app.models.user_note import UserNote

USER_EMAIL = os.environ.get("SEED_USER_EMAIL", "test@ssu.ac.kr")

# (page_number, 유형, 본문, 추천 이유, 사전 지식, 학습 순서, 첫 활동, 저장 여부)
QUESTIONS = [
    (3, "이전 내용과 연결하기",
     "이 슬라이드에서 다룬 개념은 이전 수업에서 배운 내용과 어떤 관계가 있을까?",
     "직전 차시 내용과 비교하면 이해가 더 쉬워지는 슬라이드라서 골랐다.",
     "지난 시간에 배운 핵심 개념을 떠올려 본다.",
     "이전 슬라이드를 먼저 복습한 뒤 접근한다.",
     "관련된 이전 개념을 한 문장으로 요약해 본다.",
     True),
    (3, "당연한 내용 의심하기",
     "여기서 제시된 방법이 항상 맞다고 할 수 있을까?",
     "당연하게 받아들이기 쉬운 주장이 있어서 골랐다.",
     "슬라이드에 나온 전제 조건을 확인한다.",
     "주장을 그대로 받아들이기 전에 반례를 먼저 생각해 본다.",
     "이 주장이 성립하지 않는 상황을 하나 떠올려 본다.",
     False),
    (7, "전체 흐름에서 이해하기",
     "이 내용은 전체 강의 흐름에서 왜 이 시점에 등장할까?",
     "단원 전체 구성을 봐야 이해되는 슬라이드라서 골랐다.",
     "이번 단원의 목차를 한 번 훑어본다.",
     "전체 흐름을 먼저 파악한 뒤 세부 내용으로 들어간다.",
     "이 슬라이드가 단원에서 맡은 역할을 한 줄로 적어본다.",
     True),
    (7, "실제 상황에 적용하기",
     "이 개념을 실제 문제에 적용한다면 어떤 상황에 쓰일까?",
     "이론을 실전에 옮겨 보기 좋은 슬라이드라서 골랐다.",
     "슬라이드에서 설명한 핵심 조건을 정리해 둔다.",
     "개념을 이해한 다음 적용 사례를 찾아본다.",
     "비슷한 문제를 하나 찾아서 이 개념으로 풀어본다.",
     False),
    (12, "강의 밖으로 확장하기",
     "이 주제와 관련해서 최근에는 어떤 연구나 기술이 나와 있을까?",
     "강의 범위를 넘어서는 확장 질문으로 골랐다.",
     "슬라이드에서 설명하는 범위까지는 이해하고 있어야 한다.",
     "강의 내용을 다 이해한 뒤에 찾아본다.",
     "관련 키워드로 최근 자료를 하나 검색해 본다.",
     False),
    (12, "실제 상황에 적용하기",
     "이 내용을 실무에서 쓴다면 어떤 제약을 가장 먼저 고려해야 할까?",
     "이론과 현실의 차이를 짚어보기 좋은 슬라이드라서 골랐다.",
     "슬라이드에 나온 가정 조건을 정리해 둔다.",
     "이론을 이해한 다음 현실적인 제약을 찾아본다.",
     "실무에서 이 내용이 깨지는 사례를 하나 떠올려 본다.",
     False),
]

NOTE_PAGE = 3
NOTE_CONTENT = "여기 설명이 빨리 지나갔다. 다음에 다시 읽어보기."


def main() -> None:
    db = SessionLocal()

    user = db.query(User).filter(User.email == USER_EMAIL).first()
    if user is None:
        print(f"사용자를 찾지 못했다: {USER_EMAIL}")
        sys.exit(1)

    document = (
        db.query(Document)
        .filter(Document.user_id == user.id, Document.status == DocumentStatus.UPLOADED.value)
        .order_by(Document.created_at.desc())
        .first()
    )
    if document is None:
        print(f"{USER_EMAIL} 명의로 업로드 완료된 문서가 없다.")
        sys.exit(1)

    if db.query(Question).join(DocumentPage).filter(DocumentPage.document_id == document.id).first() is not None:
        print(f"이미 시딩된 문서다 (document_id={document.id}). 건너뛴다.")
        return

    if db.query(UserCourse).filter_by(user_id=user.id, course_id=document.course_id).first() is None:
        db.add(UserCourse(user_id=user.id, course_id=document.course_id))

    pages = {}
    for page_number in {q[0] for q in QUESTIONS} | {NOTE_PAGE}:
        page = db.query(DocumentPage).filter_by(document_id=document.id, page_number=page_number).first()
        if page is None:
            page = DocumentPage(document_id=document.id, page_number=page_number)
            db.add(page)
            db.flush()  # question/note의 document_page_id로 쓰려면 먼저 id가 있어야 한다
        pages[page_number] = page

    db.add(UserNote(document_page_id=pages[NOTE_PAGE].id, content=NOTE_CONTENT))

    saved_count = 0
    for page_number, q_type, content, reason, prerequisite, order, activity, saved in QUESTIONS:
        question = Question(
            document_page_id=pages[page_number].id,
            question_type=q_type,
            content=content,
            recommended_reason=reason,
            prerequisite=prerequisite,
            learning_order=order,
            first_activity=activity,
        )
        db.add(question)
        db.flush()  # saved_question의 question_id로 쓰려면 먼저 id가 있어야 한다
        if saved:
            db.add(SavedQuestion(question_id=question.id))
            saved_count += 1

    db.commit()

    print(f"user={user.email} document={document.id} ({document.original_filename})")
    print(f"page {sorted(pages)} / question {len(QUESTIONS)}건 / saved {saved_count}건 / note 1건 생성")


if __name__ == "__main__":
    main()

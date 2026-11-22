from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints, model_validator


def nonblank(value: str) -> str:
    if not value:
        raise ValueError("Expected non-empty text")
    return value


Text = Annotated[str, StringConstraints(strip_whitespace=True), AfterValidator(nonblank)]
QuestionType = Literal["connect_prior", "understand_flow", "challenge", "apply", "extend"]
ChatQuestion = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]


class StructuredOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Concept(StructuredOutput):
    name: Text
    evidence_block_ids: list[Text] = Field(min_length=1)


class PageAnalysis(StructuredOutput):
    summary: Text
    concepts: list[Concept]
    coverage: Text
    question_eligible: bool
    exclusion_reason: Text | None


class FollowUpAnswer(StructuredOutput):
    answer_status: Literal["answered", "conversation", "insufficient_evidence"] = "answered"
    explanation: Text
    evidence_block_ids: list[Text]

    @model_validator(mode="after")
    def check_evidence(self) -> Self:
        if (self.answer_status == "answered") != bool(self.evidence_block_ids):
            raise ValueError("Only grounded answers must include evidence")
        return self


class Explanation(StructuredOutput):
    # 더 알아보기의 해설: 한 줄 핵심, 강의 근거와 이유를 담은 설명, 개념이 이어지는 흐름
    headline: Text
    body: Text
    flow: list[Text] = Field(min_length=2, max_length=4)


class Question(StructuredOutput):
    type: QuestionType
    question: Text
    why_recommended: Text
    explanation: Explanation
    evidence_block_ids: list[Text] = Field(min_length=1)
    prerequisites: list[Text]
    learning_steps: list[Text] = Field(min_length=1, max_length=3)
    first_activity: Text


class PageDraft(StructuredOutput):
    page_number: int
    analysis: PageAnalysis
    questions: list[Question] = Field(max_length=2)


class PageDrafts(StructuredOutput):
    pages: list[PageDraft]


class CourseChoice(StructuredOutput):
    course_id: Text
    reason: Text
    next_topic: Text


class CourseLink(CourseChoice):
    name: str
    # previous: 이 과목보다 앞 학기에 듣는 관련 과목, next: 뒤 학기에 들을 과목, related: 학기 정보가 없는 후보
    relation: Literal["previous", "next", "related"] = "related"
    source: Literal["ai_recommendation"] = "ai_recommendation"
    enrollment_status: Literal["not_enrolled", "in_progress", "completed"] | None = None


class QuestionSelection(StructuredOutput):
    # 쪽 안에서 질문의 순서(1부터)
    question_number: int
    # 이전에 들은 관련 과목과 이후에 들을 과목을 각각 두 개까지
    related_courses: list[CourseChoice] = Field(max_length=4)
    paper_ids: list[Text] = Field(max_length=2)


class PageSelection(StructuredOutput):
    page_number: int
    questions: list[QuestionSelection]


class PageSelections(StructuredOutput):
    pages: list[PageSelection]


class ResearchQueries(StructuredOutput):
    queries: list[Text] = Field(min_length=1, max_length=3)


class PaperSummary(StructuredOutput):
    paper_id: Text
    summary: Text


class PaperSummaries(StructuredOutput):
    papers: list[PaperSummary]


class ResearchDirection(StructuredOutput):
    title: Text
    summary: Text
    search_query: Text


class ResearchDirections(StructuredOutput):
    directions: list[ResearchDirection] = Field(min_length=1, max_length=5)


class ResearchTrend(PaperSummary):
    title: str
    # Gemini가 정리한 연구 방향은 특정 논문이 아니라서 연도가 없다
    year: int | None
    url: str
    searched_at: datetime
    source: Literal["semantic_scholar", "gemini"] = "semantic_scholar"


class EvidenceBlock(BaseModel):
    block_id: str
    bbox: tuple[float, float, float, float]


class QuestionLearning(Question):
    # 더 알아보기의 이어서 볼 과목과 연구 동향은 질문마다 고른다
    related_courses: list[CourseLink]
    trends: list[ResearchTrend]


class PageLearning(PageDraft):
    questions: list[QuestionLearning] = Field(max_length=2)
    width_pt: float
    height_pt: float
    evidence_blocks: list[EvidenceBlock]
    research_status: Literal["disabled", "ready", "unavailable"]


class StoredQuestionLearning(QuestionLearning):
    id: UUID
    is_saved: bool = False


class StoredPageLearning(PageLearning):
    questions: list[StoredQuestionLearning] = Field(max_length=2)


class ChatExchange(StructuredOutput):
    question: ChatQuestion
    answer: Text


class AskRequest(BaseModel):
    question: ChatQuestion


class StoredChatExchange(FollowUpAnswer):
    id: UUID
    question: str
    created_at: datetime


class ChatHistoryResponse(BaseModel):
    document_id: UUID
    page_number: int
    exchanges: list[StoredChatExchange]

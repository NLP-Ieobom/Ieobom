from datetime import datetime
from typing import Annotated, Literal

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, StringConstraints


def nonblank(value: str) -> str:
    if not value:
        raise ValueError("Expected non-empty text")
    return value


Text = Annotated[str, StringConstraints(strip_whitespace=True), AfterValidator(nonblank)]
QuestionType = Literal["connect_prior", "understand_flow", "challenge", "apply", "extend"]


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
    explanation: Text
    evidence_block_ids: list[Text] = Field(min_length=1)


class Question(FollowUpAnswer):
    type: QuestionType
    question: Text
    why_recommended: Text
    prerequisites: list[Text]
    learning_steps: list[Text] = Field(min_length=1, max_length=3)
    first_activity: Text


class PageDraft(StructuredOutput):
    page_number: int
    analysis: PageAnalysis
    questions: list[Question] = Field(max_length=3)


class PageDrafts(StructuredOutput):
    pages: list[PageDraft]


class CourseChoice(StructuredOutput):
    course_id: Text
    reason: Text
    next_topic: Text


class CourseLink(CourseChoice):
    name: str
    source: Literal["ai_recommendation"] = "ai_recommendation"


class PageSelection(StructuredOutput):
    page_number: int
    related_courses: list[CourseChoice] = Field(max_length=3)
    paper_ids: list[Text] = Field(max_length=3)


class PageSelections(StructuredOutput):
    pages: list[PageSelection]


class ResearchQuery(StructuredOutput):
    query: Text


class PaperSummary(StructuredOutput):
    paper_id: Text
    summary: Text


class PaperSummaries(StructuredOutput):
    papers: list[PaperSummary]


class ResearchTrend(PaperSummary):
    title: str
    year: int
    url: str
    searched_at: datetime


class EvidenceBlock(BaseModel):
    block_id: str
    bbox: tuple[float, float, float, float]


class PageLearning(PageDraft):
    width_pt: float
    height_pt: float
    evidence_blocks: list[EvidenceBlock]
    related_courses: list[CourseLink]
    trends: list[ResearchTrend]
    research_status: Literal["disabled", "ready", "unavailable"]


class AskRequest(BaseModel):
    question: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=1000)]

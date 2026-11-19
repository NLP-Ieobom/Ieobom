from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from app.integrations.learning_http import ProviderError
from app.pipelines.docling_output import _pages
from app.models.learning import CourseLearningProfile, CourseResearchCache
from app.pipelines.learning import answer_follow_up, generate_learning
from app.schemas.learning import FollowUpAnswer, PageDrafts, PageSelections, PaperSummaries, ResearchQuery


def make_question(text, evidence="p2-b1"):
    return {
        "type": "challenge",
        "question": text,
        "explanation": "함수 종속성과 질의 비용을 구분합니다.",
        "evidence_block_ids": [evidence],
        "why_recommended": "분해의 효과를 비교해 볼 수 있습니다.",
        "prerequisites": ["함수 종속성"],
        "learning_steps": ["분해 전후 질의를 비교합니다."],
        "first_activity": "두 스키마를 종이에 그립니다.",
    }


class LearningContractTest(TestCase):
    def setUp(self):
        self.db = Mock()
        self.db.scalar.return_value = None
        self.db.get.return_value = None
        self.gemini = Mock(embedding_model="gemini-embedding-001")
        self.course = SimpleNamespace(
            id="database", name="데이터베이스", is_trend_enabled=False
        )
        self.analysis = {
            "summary": "함수 종속성에 따른 분해",
            "coverage": "갱신 이상과 분해 예를 보여줍니다.",
            "concepts": [{"name": "함수 종속성", "evidence_block_ids": ["p2-b1"]}],
            "question_eligible": True,
            "exclusion_reason": None,
        }
        self.extraction = {
            "schema_version": "1.0",
            "coordinate_system": "normalized_top_left",
            "pages": [
                {"page_number": 1, "width_pt": 720, "height_pt": 405, "blocks": [],
                 "analysis": {"summary": "표지", "coverage": "제목", "concepts": [],
                              "question_eligible": False, "exclusion_reason": "cover"}},
                {"page_number": 2, "width_pt": 720, "height_pt": 405, "analysis": self.analysis,
                 "blocks": [{"block_id": "p2-b1", "kind": "text", "bbox": [0.1, 0.2, 0.3, 0.4],
                             "text": "함수 종속성을 고려해 분해하면 갱신 이상을 줄일 수 있다."}]},
            ],
        }

    def set_questions(self, questions):
        self.gemini.generate.return_value = PageDrafts.model_validate({
            "pages": [{"page_number": 2, "analysis": self.analysis, "questions": questions}],
        })

    def test_preserves_original_page_and_team_block_ids(self):
        self.set_questions([make_question("조인 비용은?"), make_question("어떤 이상이 줄어드나요?")])
        result = generate_learning(self.db, self.gemini, self.course, self.extraction)["pages"]
        self.assertEqual(result["1"]["analysis"]["exclusion_reason"], "cover")
        self.assertEqual(result["1"]["questions"], [])
        self.assertEqual(result["2"]["questions"][0]["evidence_block_ids"], ["p2-b1"])
        self.assertEqual(result["2"]["evidence_blocks"][0]["bbox"], [0.1, 0.2, 0.3, 0.4])
        self.assertEqual(result["2"]["research_status"], "disabled")
        self.gemini.generate.assert_called_once()
        self.gemini.embed.assert_not_called()
        sent_pages = self.gemini.generate.call_args.args[1]["pages"]
        self.assertEqual([page["page_number"] for page in sent_pages], [2])

    def test_rejects_invented_evidence_and_duplicate_questions(self):
        for questions in (
            [make_question("조인 비용은?", "invented"), make_question("어떤 이상이 줄어드나요?")],
            [make_question("조인 비용은?"), make_question("조인 비용은!")],
        ):
            with self.subTest(questions=questions):
                self.set_questions(questions)
                with self.assertRaises(ProviderError):
                    generate_learning(self.db, self.gemini, self.course, self.extraction)

    def test_course_recommendation_uses_indexed_syllabus_and_candidate_ids(self):
        topics = ["함수 종속성", "관계형 모델"]
        self.db.get.return_value = SimpleNamespace(topics=topics)
        self.db.scalar.return_value = "advanced-db"
        self.db.execute.return_value = [SimpleNamespace(
            id="advanced-db", name="데이터베이스응용", topics=["질의 최적화"],
        )]
        vector = [1.0] + [0.0] * 1535
        self.gemini.embed.return_value = [vector]
        self.set_questions([make_question("조인 비용은?"), make_question("어떤 이상이 줄어드나요?")])
        draft = self.gemini.generate.return_value
        for course_id in ("advanced-db", "invented-course"):
            with self.subTest(course_id=course_id):
                selection = PageSelections.model_validate({
                    "pages": [{"page_number": 2, "paper_ids": [], "related_courses": [{
                        "course_id": course_id, "reason": "조인 비용을 더 살펴볼 수 있습니다.",
                        "next_topic": "질의 최적화",
                    }]}],
                })
                self.gemini.generate.side_effect = [draft, selection]
                if course_id == "invented-course":
                    with self.assertRaisesRegex(ProviderError, "Invalid or duplicate course"):
                        generate_learning(self.db, self.gemini, self.course, self.extraction)
                    continue
                page = generate_learning(self.db, self.gemini, self.course, self.extraction)["pages"]["2"]
                self.assertEqual(page["related_courses"][0]["course_id"], "advanced-db")
                self.assertEqual(page["related_courses"][0]["source"], "ai_recommendation")
                self.assertEqual(page["related_courses"][0]["next_topic"], "질의 최적화")
                analysis_request = self.gemini.generate.call_args_list[0].args[1]
                self.assertEqual(analysis_request["course"]["topics"], topics)
                search_request = self.gemini.generate.call_args_list[1].args[1]
                self.assertEqual(search_request["pages"][0]["course_candidates"][0]["topics"], ["질의 최적화"])
                self.gemini.embed.assert_called_once_with(
                    ["함수 종속성에 따른 분해\n함수 종속성"], "RETRIEVAL_QUERY"
                )

    def test_research_summary_uses_search_result_and_cached_metadata(self):
        self.course.is_trend_enabled = True
        self.set_questions([make_question("조인 비용은?"), make_question("어떤 이상이 줄어드나요?")])
        draft = self.gemini.generate.return_value
        paper_id = "a" * 40
        selection = PageSelections.model_validate({
            "pages": [{"page_number": 2, "paper_ids": [paper_id], "related_courses": []}],
        })
        self.gemini.generate.side_effect = [
            ResearchQuery(query="database normalization"),
            PaperSummaries(papers=[{"paper_id": paper_id, "summary": "정규화의 비용을 비교합니다."}]),
            draft, selection,
            draft, selection,
        ]
        now = datetime.now(timezone.utc)
        with patch("app.integrations.semantic_scholar.request_json", return_value={"data": [
            {"paperId": paper_id, "title": "Normalization costs", "abstract": "We compare schemas.",
             "year": now.year},
            {"paperId": "b" * 40, "title": "Old paper", "abstract": "Outside range.",
             "year": now.year - 10},
        ]}) as search:
            page = generate_learning(self.db, self.gemini, self.course, self.extraction)["pages"]["2"]
            self.assertEqual(page["research_status"], "ready")
            self.assertEqual(len(page["trends"]), 1)
            self.assertEqual(page["trends"][0]["url"], f"https://www.semanticscholar.org/paper/{paper_id}")
            self.assertEqual(page["trends"][0]["summary"], "정규화의 비용을 비교합니다.")
            self.db.commit.assert_called_once()

            def get_cached(model, course_id):
                self.assertEqual(course_id, self.course.id)
                if model is CourseResearchCache:
                    return SimpleNamespace(searched_at=now, papers=page["trends"])
                self.assertIs(model, CourseLearningProfile)
                return None

            self.db.get.side_effect = get_cached
            cached = generate_learning(self.db, self.gemini, self.course, self.extraction)["pages"]["2"]
            self.assertEqual(cached["trends"], page["trends"])
            search.assert_called_once()
            self.db.commit.assert_called_once()

    def test_research_failure_keeps_questions_available(self):
        self.course.is_trend_enabled = True
        self.set_questions([make_question("조인 비용은?"), make_question("어떤 이상이 줄어드나요?")])
        self.gemini.generate.side_effect = [
            ResearchQuery(query="database normalization"), self.gemini.generate.return_value,
        ]
        with patch("app.integrations.semantic_scholar.request_json", side_effect=ProviderError("test 403")):
            with redirect_stdout(StringIO()):
                page = generate_learning(self.db, self.gemini, self.course, self.extraction)["pages"]["2"]
        self.assertEqual(page["research_status"], "unavailable")
        self.assertEqual(page["trends"], [])
        self.assertEqual(len(page["questions"]), 2)

    def test_follow_up_uses_same_page_evidence(self):
        page = self.extraction["pages"][1]
        question = "갱신 이상이 무엇인가요?"
        self.gemini.generate.return_value = FollowUpAnswer(
            explanation="같은 정보를 여러 곳에서 수정할 때 불일치가 생길 수 있습니다.",
            evidence_block_ids=["p2-b1"],
        )
        answer = answer_follow_up(self.gemini, page, question)
        self.assertEqual(answer.evidence_block_ids, ["p2-b1"])
        payload = self.gemini.generate.call_args.args[1]
        self.assertEqual(payload["question"], question)
        self.assertEqual(payload["page"]["page_number"], 2)
        self.gemini.generate.return_value.evidence_block_ids = ["p1-b1"]
        with self.assertRaisesRegex(ProviderError, "Invalid or duplicate answer evidence"):
            answer_follow_up(self.gemini, page, question)

    def test_converts_docling_bottom_left_coordinates_and_charspan(self):
        batch = {
            "pages": {"2": {"page_no": 2, "size": {"width": 200, "height": 100}}},
            "body": {"children": [{"$ref": "#/texts/0"}]}, "furniture": {"children": []},
            "texts": [{
                "label": "text", "text": "prefix lecture",
                "prov": [{"page_no": 2, "charspan": [7, 14], "bbox": {
                    "coord_origin": "BOTTOMLEFT", "l": 20, "t": 90, "r": 100, "b": 70,
                }}],
            }],
        }
        for reference_key in ("$ref", "cref"):
            with self.subTest(reference_key=reference_key):
                batch["body"]["children"] = [{reference_key: "#/texts/0"}]
                block = _pages(batch)[2]["blocks"][0]
                self.assertEqual(block["block_id"], "p0002-b0001")
                self.assertEqual(block["text"], "lecture")
                self.assertEqual(block["bbox"], [0.1, 0.1, 0.5, 0.3])

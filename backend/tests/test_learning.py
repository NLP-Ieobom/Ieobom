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
from app.schemas.learning import (
    FollowUpAnswer, PageDrafts, PageSelections, PaperSummaries, ResearchDirections, ResearchQueries,
)


def make_question(text, evidence="p2-b1"):
    return {
        "type": "challenge",
        "question": text,
        "explanation": {
            "headline": "분해는 갱신 이상을 줄이지만 조인 비용이 생깁니다.",
            "body": "함수 종속성과 질의 비용을 구분합니다.",
            "flow": ["함수 종속성", "테이블 분해", "조인 비용"],
        },
        "evidence_block_ids": [evidence],
        "why_recommended": "분해의 효과를 비교해 볼 수 있습니다.",
        "prerequisites": ["함수 종속성"],
        "learning_steps": ["분해 전후 질의를 비교합니다."],
        "first_activity": "두 스키마를 종이에 그립니다.",
    }


def make_selection(courses=(), papers=()):
    # 2쪽의 두 질문 중 첫 질문에만 과목과 논문을 고른 응답
    return PageSelections.model_validate({"pages": [{"page_number": 2, "questions": [
        {"question_number": 1, "related_courses": [
            {"course_id": course_id, "reason": "조인 비용을 더 살펴볼 수 있습니다.", "next_topic": "질의 최적화"}
            for course_id in courses
        ], "paper_ids": list(papers)},
        {"question_number": 2, "related_courses": [], "paper_ids": []},
    ]}]})


class LearningContractTest(TestCase):
    def setUp(self):
        self.db = Mock()
        self.db.scalar.return_value = None
        self.db.get.return_value = None
        self.gemini = Mock(embedding_model="gemini-embedding-001")
        self.course = SimpleNamespace(
            id="database", name="데이터베이스", is_trend_enabled=False, curriculum_id=None,
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
                self.gemini.generate.reset_mock()
                self.set_questions(questions)
                with self.assertRaises(ProviderError), redirect_stdout(StringIO()):
                    generate_learning(self.db, self.gemini, self.course, self.extraction)
                self.assertEqual(self.gemini.generate.call_count, 3)

    def test_regenerates_only_the_batch_with_invalid_output(self):
        self.set_questions([make_question("조인 비용은?")])
        single = self.gemini.generate.return_value
        self.set_questions([make_question("조인 비용은?"), make_question("어떤 이상이 줄어드나요?")])
        self.gemini.generate.side_effect = [single, self.gemini.generate.return_value]
        with redirect_stdout(StringIO()):
            page = generate_learning(self.db, self.gemini, self.course, self.extraction)["pages"]["2"]
        self.assertEqual(len(page["questions"]), 2)
        self.assertEqual(self.gemini.generate.call_count, 2)

    def test_course_recommendation_splits_previous_and_next_semesters(self):
        topics = ["함수 종속성", "관계형 모델"]
        # 이 과목은 3학년 2학기(32)로 인덱싱되어 있다
        self.db.get.return_value = SimpleNamespace(topics=topics, semester_order=32)
        self.db.scalar.return_value = "advanced-db"
        previous = SimpleNamespace(id="intro-db", name="데이터베이스", topics=["관계형 모델"])
        later = SimpleNamespace(id="big-data", name="빅데이터컴퓨팅", topics=["분산 질의 처리"])
        vector = [1.0] + [0.0] * 1535
        self.gemini.embed.return_value = [vector]
        self.set_questions([make_question("조인 비용은?"), make_question("어떤 이상이 줄어드나요?")])
        draft = self.gemini.generate.return_value
        selections = {
            "aliases": make_selection(courses=["p2-c1", "p2-c2"]),
            "raw": make_selection(courses=["intro-db"]),
        }
        # 모델에는 별칭만 보이므로 원래 ID를 그대로 적어도 후보 밖 참조다.
        # 세 번까지 다시 요청하고, 그 사이 올바른 응답이 오면 그것을 쓴다.
        for responses in (
            [selections["raw"]] * 3,
            [selections["raw"], selections["aliases"]],
        ):
            with self.subTest(responses=len(responses)):
                self.gemini.embed.reset_mock()
                self.gemini.generate.reset_mock()
                self.db.execute.reset_mock()
                self.db.execute.side_effect = [[previous], [later]]
                self.gemini.generate.side_effect = [draft, *responses]
                if len(responses) == 3:
                    with self.assertRaisesRegex(ProviderError, "Invalid or duplicate course"), redirect_stdout(StringIO()):
                        generate_learning(self.db, self.gemini, self.course, self.extraction)
                    continue
                with redirect_stdout(StringIO()):
                    page = generate_learning(self.db, self.gemini, self.course, self.extraction)["pages"]["2"]
                first, second = page["questions"]
                self.assertEqual(
                    [(link["course_id"], link["relation"]) for link in first["related_courses"]],
                    [("intro-db", "previous"), ("big-data", "next")],
                )
                self.assertEqual(first["related_courses"][0]["source"], "ai_recommendation")
                self.assertEqual(second["related_courses"], [])
                analysis_request = self.gemini.generate.call_args_list[0].args[1]
                self.assertEqual(analysis_request["course"]["topics"], topics)
                search_request = self.gemini.generate.call_args_list[1].args[1]["pages"][0]
                self.assertEqual(
                    [(item["course_id"], item["relation"]) for item in search_request["course_candidates"]],
                    [("p2-c1", "previous"), ("p2-c2", "next")],
                )
                self.assertEqual([item["question_number"] for item in search_request["questions"]], [1, 2])
                self.gemini.embed.assert_called_once_with(
                    ["함수 종속성에 따른 분해\n함수 종속성"], "RETRIEVAL_QUERY"
                )
                # pgvector 검색 쿼리에 학기 조건이 들어갔는지 확인한다
                queries = [str(call.args[0].compile()) for call in self.db.execute.call_args_list]
                self.assertIn("course_learning_profile.semester_order <", queries[0])
                self.assertIn("course_learning_profile.semester_order >", queries[1])
                self.assertTrue(all("ORDER BY course_learning_profile.embedding <=>" in query for query in queries))

    def test_research_summary_uses_search_result_and_cached_metadata(self):
        self.course.is_trend_enabled = True
        self.set_questions([make_question("조인 비용은?"), make_question("어떤 이상이 줄어드나요?")])
        draft = self.gemini.generate.return_value
        paper_id = "a" * 40
        selection = make_selection(papers=["r1"])
        self.gemini.generate.side_effect = [
            ResearchQueries(queries=["database normalization"]),
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
            trends = page["questions"][0]["trends"]
            self.assertEqual(len(trends), 1)
            self.assertEqual(trends[0]["url"], f"https://www.semanticscholar.org/paper/{paper_id}")
            self.assertEqual(trends[0]["summary"], "정규화의 비용을 비교합니다.")
            self.assertEqual(page["questions"][1]["trends"], [])
            self.db.commit.assert_called_once()

            def get_cached(model, course_id):
                self.assertEqual(course_id, self.course.id)
                if model is CourseResearchCache:
                    return SimpleNamespace(searched_at=now, papers=trends)
                self.assertIs(model, CourseLearningProfile)
                return None

            self.db.get.side_effect = get_cached
            cached = generate_learning(self.db, self.gemini, self.course, self.extraction)["pages"]["2"]
            self.assertEqual(cached["questions"][0]["trends"], trends)
            search.assert_called_once()
            self.db.commit.assert_called_once()

    def test_research_merges_queries_and_keeps_results_when_one_search_fails(self):
        self.course.is_trend_enabled = True
        self.set_questions([make_question("조인 비용은?"), make_question("어떤 이상이 줄어드나요?")])
        draft = self.gemini.generate.return_value
        paper_id = "a" * 40
        now = datetime.now(timezone.utc)
        self.gemini.generate.side_effect = [
            ResearchQueries(queries=["database normalization", "query optimization"]),
            PaperSummaries(papers=[{"paper_id": paper_id, "summary": "정규화의 비용을 비교합니다."}]),
            draft, make_selection(papers=["r1"]),
        ]
        hit = {"data": [{"paperId": paper_id, "title": "Normalization costs", "abstract": "We compare schemas.",
                         "year": now.year}]}
        with (
            patch("app.integrations.semantic_scholar.request_json",
                  side_effect=[hit, *[ProviderError("test 429")] * 4]) as search,
            patch("app.services.research.time.sleep"),
            redirect_stdout(StringIO()),
        ):
            page = generate_learning(self.db, self.gemini, self.course, self.extraction)["pages"]["2"]
        # 두 번째 검색어는 네 번 모두 429지만 첫 검색어의 논문으로 계속한다
        self.assertEqual(search.call_count, 5)
        self.assertEqual(page["questions"][0]["trends"][0]["paper_id"], paper_id)
        self.assertEqual(page["questions"][0]["trends"][0]["source"], "semantic_scholar")
        self.db.commit.assert_called_once()

    def test_search_failure_falls_back_to_uncached_gemini_directions(self):
        self.course.is_trend_enabled = True
        self.set_questions([make_question("조인 비용은?"), make_question("어떤 이상이 줄어드나요?")])
        draft = self.gemini.generate.return_value
        selection = make_selection(papers=["r1"])
        self.gemini.generate.side_effect = [
            ResearchQueries(queries=["database normalization"]),
            ResearchDirections(directions=[{
                "title": "정규화와 조회 성능의 균형", "summary": "분해 이후의 조인 비용을 다룹니다.",
                "search_query": "denormalization query performance",
            }]),
            draft, selection,
        ]
        with (
            patch("app.integrations.semantic_scholar.request_json", side_effect=ProviderError("test 429")) as search,
            patch("app.services.research.time.sleep"),
            redirect_stdout(StringIO()),
        ):
            page = generate_learning(self.db, self.gemini, self.course, self.extraction)["pages"]["2"]
        self.assertEqual(search.call_count, 4)
        self.assertEqual(page["research_status"], "ready")
        trend = page["questions"][0]["trends"][0]
        self.assertEqual((trend["source"], trend["year"]), ("gemini", None))
        self.assertTrue(trend["url"].startswith("https://scholar.google.com/scholar?q=denormalization"))
        self.db.execute.assert_not_called()
        self.db.commit.assert_not_called()

    def test_research_failure_keeps_questions_available(self):
        self.course.is_trend_enabled = True
        self.set_questions([make_question("조인 비용은?"), make_question("어떤 이상이 줄어드나요?")])
        self.gemini.generate.side_effect = [
            ResearchQueries(queries=["database normalization"]), ProviderError("test 503"),
            self.gemini.generate.return_value,
        ]
        with patch(
            "app.integrations.semantic_scholar.request_json",
            side_effect=ProviderError("test 403", retryable=False),
        ) as search:
            with redirect_stdout(StringIO()):
                page = generate_learning(self.db, self.gemini, self.course, self.extraction)["pages"]["2"]
        search.assert_called_once()
        self.assertEqual(page["research_status"], "unavailable")
        self.assertEqual([question["trends"] for question in page["questions"]], [[], []])

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

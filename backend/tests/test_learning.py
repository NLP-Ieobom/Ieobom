from contextlib import redirect_stdout
from datetime import datetime, timezone
from io import StringIO
from types import SimpleNamespace
from unittest import TestCase
from unittest.mock import Mock, patch

from pydantic import ValidationError

from app.integrations.learning_http import ProviderError
from app.pipelines.docling_output import _pages
from app.models.learning import CourseLearningProfile
from app.pipelines.learning import answer_follow_up, generate_learning
from app.schemas.learning import (
    AskRequest, ChatExchange, FollowUpAnswer, PageDrafts, PageSelections, PaperSummaries,
    ResearchTopicPlan,
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


def make_topic_plan(*groups, new_topics=()):
    return ResearchTopicPlan.model_validate({
        "new_topics": [
            {"topic_id": topic_id, "name": name, "query": query}
            for topic_id, name, query in new_topics
        ],
        "pages": [{"page_number": 2, "groups": [
            {
                "question_numbers": question_numbers,
                "topic_id": topic_id,
                "supplemental_query": supplemental_query,
            }
            for question_numbers, topic_id, supplemental_query in groups
        ]}],
    })


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
                    with redirect_stdout(StringIO()):
                        page = generate_learning(self.db, self.gemini, self.course, self.extraction)["pages"]["2"]
                    self.assertEqual([question["related_courses"] for question in page["questions"]], [[], []])
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
                    ["함수 종속성에 따른 분해\n함수 종속성"], "RETRIEVAL_QUERY", call="SLIDE_EMBED"
                )
                # pgvector 검색 쿼리에 학기 조건이 들어갔는지 확인한다
                queries = [str(call.args[0].compile()) for call in self.db.execute.call_args_list]
                self.assertIn("course_learning_profile.semester_order <", queries[0])
                self.assertIn("course_learning_profile.semester_order >", queries[1])
                self.assertTrue(all("ORDER BY course_learning_profile.embedding <=>" in query for query in queries))

    def test_research_topic_candidates_are_saved_and_reused_without_another_search(self):
        self.course.is_trend_enabled = True
        self.set_questions([make_question("조인 비용은?"), make_question("정규화의 비용은?")])
        draft = self.gemini.generate.return_value
        paper_id = "a" * 40
        topics = []
        new_plan = make_topic_plan(
            ([1, 2], "new-1", None),
            new_topics=[("new-1", "데이터베이스 정규화 비용", "database normalization join cost")],
        )
        selection = PageSelections.model_validate({"pages": [{"page_number": 2, "questions": [
            {"question_number": 1, "related_courses": [], "paper_ids": ["p2-q1-r1"]},
            {"question_number": 2, "related_courses": [], "paper_ids": ["p2-q2-r1"]},
        ]}]})
        self.gemini.generate.side_effect = [
            draft, new_plan,
            PaperSummaries(papers=[{"paper_id": paper_id, "summary": "정규화 비용을 비교합니다."}]),
            selection,
        ]
        now = datetime.now(timezone.utc)
        hit = {"data": [{"paperId": paper_id, "title": "Normalization costs",
                          "abstract": "We compare schemas.", "year": now.year}]}
        with patch("app.integrations.semantic_scholar.request_json", return_value=hit) as search:
            page = generate_learning(
                self.db, self.gemini, self.course, self.extraction, research_topics=topics,
            )["pages"]["2"]
            topic_id = topics[0]["topic_id"]
            existing_plan = make_topic_plan(([1, 2], topic_id, None))
            self.gemini.generate.side_effect = [draft, existing_plan, selection]
            cached = generate_learning(
                self.db, self.gemini, self.course, self.extraction, research_topics=topics,
            )["pages"]["2"]

        search.assert_called_once()
        self.assertEqual(page["research_status"], "ready")
        self.assertEqual([question["trends"][0]["paper_id"] for question in page["questions"]],
                         [paper_id, paper_id])
        self.assertEqual(cached["questions"][0]["trends"], page["questions"][0]["trends"])
        self.assertEqual(topics[0]["queries"], ["database normalization join cost"])
        self.assertEqual(topics[0]["papers"][0]["paper_id"], paper_id)

    def test_partial_rate_limit_publishes_questions_and_saves_successful_topic(self):
        self.course.is_trend_enabled = True
        self.set_questions([make_question("조인 비용은?"), make_question("어떤 이상이 줄어드나요?")])
        draft = self.gemini.generate.return_value
        paper_id = "a" * 40
        topics = []
        plan = make_topic_plan(
            ([1], "new-1", None), ([2], "new-2", None),
            new_topics=[
                ("new-1", "정규화 비용", "database normalization"),
                ("new-2", "갱신 이상 평가", "update anomaly evaluation"),
            ],
        )
        self.gemini.generate.side_effect = [
            draft, plan,
            PaperSummaries(papers=[{"paper_id": paper_id, "summary": "정규화 비용을 비교합니다."}]),
            make_selection(papers=["p2-q1-r1"]),
        ]
        now = datetime.now(timezone.utc)
        hit = {"data": [{"paperId": paper_id, "title": "Normalization costs",
                          "abstract": "We compare schemas.", "year": now.year}]}
        with (
            patch("app.integrations.semantic_scholar.request_json",
                  side_effect=[hit, ProviderError("test 429", http_status=429)]) as search,
            patch("app.services.research.time.sleep"),
            redirect_stdout(StringIO()),
        ):
            page = generate_learning(
                self.db, self.gemini, self.course, self.extraction, research_topics=topics,
            )["pages"]["2"]

        self.assertEqual(search.call_count, 2)
        self.assertEqual(len(page["questions"]), 2)
        self.assertEqual(page["research_status"], "unavailable")
        self.assertEqual(page["questions"][0]["trends"][0]["paper_id"], paper_id)
        self.assertEqual(page["questions"][1]["trends"], [])
        self.assertEqual(topics[0]["papers"][0]["paper_id"], paper_id)
        self.assertIn("update anomaly evaluation", topics[1]["failed_queries"])

    def test_rate_limit_calls_once_then_cooldown_still_publishes_questions(self):
        self.course.is_trend_enabled = True
        self.set_questions([make_question("조인 비용은?"), make_question("어떤 이상이 줄어드나요?")])
        draft = self.gemini.generate.return_value
        topics = []
        new_plan = make_topic_plan(
            ([1, 2], "new-1", None),
            new_topics=[("new-1", "데이터베이스 정규화", "database normalization")],
        )
        self.gemini.generate.side_effect = [draft, new_plan]
        with (
            patch("app.integrations.semantic_scholar.request_json",
                  side_effect=ProviderError("test 429", http_status=429)) as search,
            redirect_stdout(StringIO()),
        ):
            first = generate_learning(
                self.db, self.gemini, self.course, self.extraction, research_topics=topics,
            )["pages"]["2"]
            topic_id = topics[0]["topic_id"]
            self.gemini.generate.side_effect = [draft, make_topic_plan(([1, 2], topic_id, None))]
            second = generate_learning(
                self.db, self.gemini, self.course, self.extraction, research_topics=topics,
            )["pages"]["2"]

        search.assert_called_once()
        self.assertEqual(first["research_status"], "unavailable")
        self.assertEqual(second["research_status"], "unavailable")
        self.assertEqual(len(first["questions"]), 2)
        self.assertEqual(len(second["questions"]), 2)

    def test_successful_search_is_reused_after_summary_failure(self):
        self.course.is_trend_enabled = True
        self.set_questions([make_question("조인 비용은?"), make_question("정규화의 비용은?")])
        draft = self.gemini.generate.return_value
        paper_id = "a" * 40
        topics = []
        plan = make_topic_plan(
            ([1, 2], "new-1", None),
            new_topics=[("new-1", "정규화 비용", "database normalization join cost")],
        )
        self.gemini.generate.side_effect = [draft, plan, ProviderError("Gemini 503")]
        now = datetime.now(timezone.utc)
        hit = {"data": [{"paperId": paper_id, "title": "Normalization costs",
                          "abstract": "We compare schemas.", "year": now.year}]}
        with patch("app.integrations.semantic_scholar.request_json", return_value=hit) as search:
            with redirect_stdout(StringIO()):
                first = generate_learning(
                    self.db, self.gemini, self.course, self.extraction, research_topics=topics,
                )["pages"]["2"]
            topic_id = topics[0]["topic_id"]
            self.gemini.generate.side_effect = [
                draft,
                make_topic_plan(([1, 2], topic_id, None)),
                PaperSummaries(papers=[{"paper_id": paper_id, "summary": "정규화 비용을 비교합니다."}]),
                make_selection(papers=["p2-q1-r1"]),
            ]
            second = generate_learning(
                self.db, self.gemini, self.course, self.extraction, research_topics=topics,
            )["pages"]["2"]

        search.assert_called_once()
        self.assertEqual(first["research_status"], "unavailable")
        self.assertEqual(len(first["questions"]), 2)
        self.assertEqual(second["questions"][0]["trends"][0]["paper_id"], paper_id)
        self.assertEqual(topics[0]["raw_results"], {})

    def test_selection_failure_publishes_questions_without_recommendations(self):
        self.course.is_trend_enabled = True
        self.set_questions([make_question("조인 비용은?"), make_question("정규화의 비용은?")])
        draft = self.gemini.generate.return_value
        now = datetime.now(timezone.utc)
        paper_id = "a" * 40
        topic_id = "topic-normalization"
        topics = [{
            "topic_id": topic_id, "name": "데이터베이스 정규화",
            "queries": ["database normalization"],
            "papers": [{
                "paper_id": paper_id, "title": "Normalization costs", "summary": "비용을 비교합니다.",
                "year": now.year, "url": f"https://www.semanticscholar.org/paper/{paper_id}",
                "searched_at": now.isoformat(), "source": "semantic_scholar",
            }],
            "raw_results": {}, "failed_queries": {}, "completed_queries": ["database normalization"],
        }]
        self.gemini.generate.side_effect = [
            draft, make_topic_plan(([1, 2], topic_id, None)), ProviderError("Gemini 503"),
        ]
        with redirect_stdout(StringIO()):
            page = generate_learning(
                self.db, self.gemini, self.course, self.extraction, research_topics=topics,
            )["pages"]["2"]
        self.assertEqual(len(page["questions"]), 2)
        self.assertEqual(page["research_status"], "unavailable")
        self.assertEqual([question["trends"] for question in page["questions"]], [[], []])
        self.assertEqual([question["related_courses"] for question in page["questions"]], [[], []])

    def test_existing_topic_gets_one_supplemental_search_when_candidates_do_not_fit(self):
        self.course.is_trend_enabled = True
        self.set_questions([make_question("조인 비용은?"), make_question("어떤 이상이 줄어드나요?")])
        draft = self.gemini.generate.return_value
        now = datetime.now(timezone.utc)
        old_id, new_id = "a" * 40, "b" * 40
        topic_id = "topic-normalization"
        topics = [{
            "topic_id": topic_id, "name": "데이터베이스 정규화",
            "queries": ["database normalization"],
            "papers": [{
                "paper_id": old_id, "title": "Schema decomposition", "summary": "분해 규칙을 다룹니다.",
                "year": now.year, "url": f"https://www.semanticscholar.org/paper/{old_id}",
                "searched_at": now.isoformat(), "source": "semantic_scholar",
            }],
            "raw_results": {}, "failed_queries": {}, "completed_queries": ["database normalization"],
        }]
        plan = make_topic_plan(
            ([1, 2], topic_id, "normalization join performance cost"),
        )
        selection = make_selection(papers=["p2-q1-r1"])
        self.gemini.generate.side_effect = [
            draft, plan,
            PaperSummaries(papers=[{"paper_id": new_id, "summary": "조인 비용을 비교합니다."}]),
            selection,
        ]
        hit = {"data": [{"paperId": new_id, "title": "Join performance after normalization",
                          "abstract": "We measure join cost.", "year": now.year}]}
        with patch("app.integrations.semantic_scholar.request_json", return_value=hit) as search:
            page = generate_learning(
                self.db, self.gemini, self.course, self.extraction, research_topics=topics,
            )["pages"]["2"]

        search.assert_called_once()
        self.assertEqual(topics[0]["queries"], ["database normalization", "normalization join performance cost"])
        self.assertEqual(topics[0]["papers"][0]["paper_id"], new_id)
        self.assertEqual(page["questions"][0]["trends"][0]["paper_id"], new_id)

    def test_invalid_topic_plan_does_not_hide_questions(self):
        self.course.is_trend_enabled = True
        self.set_questions([make_question("조인 비용은?"), make_question("어떤 이상이 줄어드나요?")])
        draft = self.gemini.generate.return_value
        invalid = make_topic_plan(
            ([1], "new-1", None),
            new_topics=[("new-1", "정규화", "database normalization")],
        )
        self.gemini.generate.side_effect = [draft, invalid, invalid, invalid]
        with redirect_stdout(StringIO()):
            page = generate_learning(self.db, self.gemini, self.course, self.extraction)["pages"]["2"]
        self.assertEqual(len(page["questions"]), 2)
        self.assertEqual(page["research_status"], "unavailable")

    def test_follow_up_uses_same_page_evidence(self):
        page = self.extraction["pages"][1]
        question = "갱신 이상이 무엇인가요?"
        self.gemini.generate.return_value = FollowUpAnswer(
            explanation="같은 정보를 여러 곳에서 수정할 때 불일치가 생길 수 있습니다.",
            evidence_block_ids=["p2-b1"],
        )
        answer = answer_follow_up(self.gemini, page, question)
        self.assertEqual(answer.answer_status, "answered")
        self.assertEqual(answer.evidence_block_ids, ["p2-b1"])
        payload = self.gemini.generate.call_args.args[1]
        self.assertEqual(payload["question"], question)
        self.assertEqual(payload["page"]["page_number"], 2)
        self.gemini.generate.return_value.evidence_block_ids = ["p1-b1"]
        with self.assertRaisesRegex(ProviderError, "Invalid or duplicate answer evidence"):
            answer_follow_up(self.gemini, page, question)

    def test_chat_request_trims_question_and_ignores_client_history(self):
        request = AskRequest(
            question="  그럼 어떻게 비교하나요?  ",
            history=[
                {"question": f"  질문 {number}  ", "answer": f"  답변 {number}  "}
                for number in range(1, 4)
            ],
        )
        self.assertEqual(request.question, "그럼 어떻게 비교하나요?")
        self.assertEqual(request.model_dump(), {"question": "그럼 어떻게 비교하나요?"})
        for invalid in (
            {"question": " "},
            {"question": "q" * 1001},
        ):
            with self.subTest(invalid=invalid):
                with self.assertRaises(ValidationError):
                    AskRequest.model_validate(invalid)

    def test_follow_up_passes_history_without_expanding_page_evidence(self):
        request = AskRequest(question="그 내용이 여기에도 있나요?")
        history = [ChatExchange(question="이전 페이지의 근거는?", answer="p1-b1을 살펴보세요.")]
        page = self.extraction["pages"][1]
        self.gemini.generate.return_value = FollowUpAnswer(
            explanation="현재 페이지는 함수 종속성과 분해를 다룹니다.",
            evidence_block_ids=["p2-b1"],
        )
        answer_follow_up(self.gemini, page, request.question, history)
        payload = self.gemini.generate.call_args.args[1]
        self.assertEqual(payload["question"], request.question)
        self.assertEqual(payload["history"], [
            {"question": "이전 페이지의 근거는?", "answer": "p1-b1을 살펴보세요."},
        ])
        self.assertEqual(payload["page"]["page_number"], 2)
        self.gemini.generate.return_value.evidence_block_ids = ["p1-b1"]
        with self.assertRaisesRegex(ProviderError, "Invalid or duplicate answer evidence"):
            answer_follow_up(self.gemini, page, request.question, history)

    def test_follow_up_accepts_conversation_and_insufficient_evidence_without_citations(self):
        for status, question, explanation in (
            ("conversation", "안녕", "안녕하세요. 함께 살펴볼 내용이 있나요?"),
            ("insufficient_evidence", "교수님 연구실은 어디인가요?", "현재 페이지에서 확인할 수 없습니다."),
        ):
            with self.subTest(status=status):
                self.gemini.generate.return_value = FollowUpAnswer(
                    answer_status=status, explanation=explanation, evidence_block_ids=[],
                )
                answer = answer_follow_up(self.gemini, self.extraction["pages"][1], question)
                self.assertEqual(answer.answer_status, status)
                self.assertEqual(answer.explanation, explanation)
                self.assertEqual(answer.evidence_block_ids, [])
                self.assertEqual(self.gemini.generate.call_args.args[1]["history"], [])

    def test_follow_up_status_requires_corresponding_evidence(self):
        for status, evidence in (
            ("answered", []),
            ("conversation", ["p2-b1"]),
            ("insufficient_evidence", ["p2-b1"]),
            ("unknown", []),
        ):
            with self.subTest(status=status, evidence=evidence):
                with self.assertRaises(ValidationError):
                    FollowUpAnswer(
                        answer_status=status, explanation="응답", evidence_block_ids=evidence,
                    )

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

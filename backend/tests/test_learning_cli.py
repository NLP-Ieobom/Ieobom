import json
import tempfile
import zipfile
from pathlib import Path
from unittest import TestCase
from unittest.mock import Mock

from app.models.learning import CourseLearningProfile
from app.pipelines.learning_cli import OfflineCatalog, offline_session


def write_corpus(directory: Path) -> Path:
    # 이 과목(32)과 앞 학기(21), 같은 학기(32), 뒤 학기(41) 과목이 하나씩 있는 교육과정 ZIP
    courses = [("own", "소프트웨어분석 및 설계", 3, 2), ("before", "고급프로그래밍", 2, 1),
               ("same", "데이터베이스응용", 3, 2), ("after", "클라우드컴퓨팅", 4, 1)]
    path = directory / "corpus.zip"
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr("manifest.json", json.dumps({"course_index": "data/courses.json"}))
        archive.writestr("data/courses.json", json.dumps({"curriculum_entry_year": 2026, "courses": [
            {"course_id": f"ssu:{code}", "name": name, "course_code": code,
             "placements": [{"year": year, "semester": semester}], "syllabus": {"path": f"s/{code}.json"}}
            for code, name, year, semester in courses
        ]}, ensure_ascii=False))
        for code, name, _, _ in courses:
            archive.writestr(f"s/{code}.json", json.dumps({
                "course": {"course_id": f"ssu:{code}"},
                "weekly_topics": [{"week": 1, "topics": [{"text": f"{name} 1주차"}]}],
            }, ensure_ascii=False))
    vectors = [[1.0, 0.0], [1.0, 0.1], [1.0, 0.0], [0.9, 0.1]]
    path.with_name("corpus.test-model.vectors.json").write_text(json.dumps({
        "ids": [f"ssu:{code}" for code, *_ in courses], "vectors": vectors,
    }))
    return path


class OfflineCatalogTest(TestCase):
    def test_reuses_saved_vectors_and_splits_semesters_like_pgvector_search(self):
        with tempfile.TemporaryDirectory() as directory:
            gemini = Mock(embedding_model="test-model")
            catalog = OfflineCatalog(write_corpus(Path(directory)), gemini, "own")
        gemini.embed.assert_not_called()
        db, course = offline_session("", trends=False, catalog=catalog)
        self.assertEqual(course.name, "소프트웨어분석 및 설계")
        profile = db.get(CourseLearningProfile, course.id)
        self.assertEqual(profile.semester_order, 32)

        def names(relation):
            return [item["name"] for item in catalog.search(
                db, course.id, "test-model", [1.0, 0.0], relation=relation, semester_order=32,
            )]

        self.assertEqual(names("previous"), ["고급프로그래밍"])
        self.assertEqual(names("next"), ["클라우드컴퓨팅"])
        # 학기를 따지지 않으면 자기 과목만 빼고 가까운 순서로 모두 나온다
        self.assertEqual(names("related"), ["데이터베이스응용", "고급프로그래밍", "클라우드컴퓨팅"])

    def test_rejects_course_code_missing_from_corpus(self):
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "not in the corpus"):
                OfflineCatalog(write_corpus(Path(directory)), Mock(embedding_model="test-model"), "unknown")

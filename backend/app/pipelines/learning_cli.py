"""Write the learning JSON for a Docling extraction without a database, S3, or the worker.

    cd backend
    python -m app.pipelines.learning_cli extraction.json -o learning.json --env-file ../.env
    python -m app.pipelines.learning_cli extraction.json -o learning.json --env-file ../.env
        --corpus ieobom-ssu-corpus.zip --course-code 21501666 --trends    (with course links and research)

The output is what generate_learning returns and the worker stores, so the page objects are the
same ones GET /documents/{document_id}/pages/{page_number}/learning serves. docs/learning-output.md
describes every field.
"""

import argparse
import json
import math
import os
import sys
import time
import uuid
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import Mock

from app.integrations.gemini import Gemini
from app.integrations.learning_http import ProviderError
from app.models.course import Course
from app.models.learning import CourseLearningProfile
from app.pipelines.learning import answer_follow_up, generate_learning
from app.services.curriculum_search import read_catalog


class RetryingGemini(Gemini):
    """Retry each call on transient errors so one overloaded batch doesn't restart every page.

    GEMINI_FALLBACK_MODELS (comma separated) lists models to rotate through while the main one is overloaded.
    """

    def __init__(self):
        super().__init__()
        fallbacks = os.environ.get("GEMINI_FALLBACK_MODELS", "")
        self.models = [self.text_model, *(model.strip() for model in fallbacks.split(",") if model.strip())]

    def _retry(self, call, *args):
        for attempt, delay in enumerate((10, 30, 60, 120, None)):
            self.text_model = self.models[attempt % len(self.models)]
            try:
                return call(*args)
            except ProviderError as error:
                if not error.retryable or delay is None:
                    raise
                print(f"Gemini call ({self.text_model}) retrying in {delay}s: {error}", file=sys.stderr, flush=True)
                time.sleep(delay)

    def generate(self, *args):
        return self._retry(super().generate, *args)

    def embed(self, *args):
        return self._retry(super().embed, *args)


def load_env_file(path: Path) -> None:
    # Compose env_file와 같이 따옴표 없는 값의 " #" 뒤는 주석으로 본다. 이미 설정된 변수는 덮어쓰지 않는다.
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = (part.strip() for part in line.split("=", 1))
        if value[:1] in {'"', "'"} and value[-1:] == value[:1]:
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].strip()
        os.environ.setdefault(key, value)


def _cosine(left: list[float], right: list[float]) -> float:
    dot = sum(a * b for a, b in zip(left, right, strict=True))
    return dot / (math.hypot(*left) * math.hypot(*right))


class OfflineCatalog:
    """The team curriculum ZIP embedded in memory, searched like curriculum_search.find_candidates searches pgvector.

    Vectors are saved next to the ZIP and reused, the way the service indexes the catalog once.
    """

    def __init__(self, corpus: Path, gemini: Gemini, course_code: str | None):
        _, catalog = read_catalog(corpus)
        cache = corpus.with_name(f"{corpus.stem}.{gemini.embedding_model}.vectors.json")
        ids = [entry["corpus_id"] for entry in catalog]
        cached = json.loads(cache.read_text(encoding="utf-8")) if cache.exists() else None
        if cached is not None and cached["ids"] == ids:
            vectors = cached["vectors"]
        else:
            vectors = []
            for offset in range(0, len(catalog), 20):
                vectors.extend(gemini.embed(
                    ["\n".join([entry["name"], *entry["topics"]])[:8000] for entry in catalog[offset:offset + 20]],
                    "RETRIEVAL_DOCUMENT",
                ))
            cache.write_text(json.dumps({"ids": ids, "vectors": vectors}), encoding="utf-8")

        self.own_id, self.own_name = None, None
        self.profiles, self.names = {}, {}
        for entry, vector in zip(catalog, vectors, strict=True):
            course_id = uuid.uuid4()
            if course_code is not None and entry["code"] == course_code:
                self.own_id, self.own_name = course_id, entry["name"]
            self.profiles[course_id] = CourseLearningProfile(
                course_id=course_id, corpus_id=entry["corpus_id"], topics=entry["topics"],
                semester_order=entry["semester_order"], embedding_model=gemini.embedding_model, embedding=vector,
            )
            self.names[course_id] = entry["name"]
        if course_code is not None and self.own_id is None:
            raise ValueError(f"Course code {course_code} is not in the corpus")

    def search(self, db, course_id, embedding_model, vector, *, curriculum_id=None, relation="related", semester_order=None, limit=5):
        # find_candidates와 같은 학기 조건이다. 같은 학기는 이전·이후 어디에도 넣지 않는다.
        def keep(key):
            order = self.profiles[key].semester_order
            if relation == "previous":
                return order is not None and order < semester_order
            if relation == "next":
                return order is not None and order > semester_order
            return True

        ranked = sorted(
            (key for key in self.profiles if key != course_id and keep(key)),
            key=lambda key: (-_cosine(self.profiles[key].embedding, vector), str(key)),
        )
        return [
            {"course_id": str(key), "name": self.names[key], "topics": self.profiles[key].topics, "relation": relation}
            for key in ranked[:limit]
        ]


def offline_session(course_name: str, *, trends: bool, catalog: OfflineCatalog | None = None) -> tuple[Mock, Course]:
    """Stand in for the database session generate_learning reads course profiles and the research cache from."""
    db = Mock()
    db.scalar.return_value = None
    db.get.return_value = None
    course = Course(id=uuid.uuid4(), name=course_name, is_trend_enabled=trends)
    if catalog is not None:
        if catalog.own_id is not None:
            course.id, course.name = catalog.own_id, catalog.own_name
        db.scalar.return_value = course.id
        db.get.side_effect = lambda model, key: catalog.profiles.get(key) if model is CourseLearningProfile else None
    return db, course


def generate(extraction: dict, gemini: Gemini, db, course, *, search=None, attempts: int = 3) -> dict:
    """Run generate_learning, restarting on transient errors the way the worker retries a job."""
    options = {} if search is None else {"search": search}
    for attempt in range(1, attempts + 1):
        try:
            result = generate_learning(db, gemini, course, extraction, **options)
            break
        except ProviderError as error:
            if not error.retryable or attempt == attempts:
                raise
            delay = min(30 * 2 ** (attempt - 1), 600)
            print(f"generation retrying in {delay}s: {error}", file=sys.stderr, flush=True)
            time.sleep(delay)
    return {"schema_version": result["schema_version"], "document_id": extraction.get("document_id"),
            "pages": result["pages"]}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("extraction", type=Path, help="Team extraction v1 JSON from Docling")
    parser.add_argument("--output", "-o", type=Path, help="Write the learning JSON here instead of stdout")
    parser.add_argument("--env-file", type=Path, help="Read GEMINI_API_KEY and other settings from this file")
    parser.add_argument("--course-name", default="", help="Course name when --corpus is not given")
    parser.add_argument("--corpus", type=Path, help="Team curriculum ZIP (ieobom-ssu-corpus.zip) for course links")
    parser.add_argument("--course-code", help="This lecture's course code in --corpus, for its semester and topics")
    parser.add_argument("--trends", action="store_true", help="Search Semantic Scholar for research trends")
    parser.add_argument("--attempts", type=int, default=3, help="Whole-run attempts, like WORKER_MAX_ATTEMPTS")
    parser.add_argument("--ask", help="Also answer this follow-up question about --page")
    parser.add_argument("--page", type=int, default=2, help="Original PDF page number for --ask")
    args = parser.parse_args(argv)

    try:
        if args.env_file:
            load_env_file(args.env_file)
        extraction = json.loads(args.extraction.read_text(encoding="utf-8"))
        gemini = RetryingGemini()
        # 진행 메시지가 표준 출력의 JSON에 섞이지 않도록 한다
        with redirect_stdout(sys.stderr):
            catalog = OfflineCatalog(args.corpus, gemini, args.course_code) if args.corpus else None
            db, course = offline_session(args.course_name, trends=args.trends, catalog=catalog)
            result = generate(
                extraction, gemini, db, course,
                search=catalog.search if catalog else None, attempts=args.attempts,
            )
            if args.ask:
                page = result["pages"].get(str(args.page))
                if page is None or not page["analysis"]["question_eligible"]:
                    raise ValueError(f"Page {args.page} has no eligible lecture content")
                source = next(page for page in extraction["pages"] if page["page_number"] == args.page)
                answer = answer_follow_up(gemini, source, args.ask)
                result["follow_up"] = {"page_number": args.page, "question": args.ask, **answer.model_dump(mode="json")}
    except (ProviderError, OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")

    text = json.dumps(result, ensure_ascii=False, indent=2)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
        print(f"Wrote {args.output} ({len(result['pages'])} pages)", file=sys.stderr)
    else:
        print(text)


if __name__ == "__main__":
    main()

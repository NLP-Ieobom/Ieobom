"""Run the learning pipeline on extraction JSON without an upload or a worker."""

import argparse
from contextlib import redirect_stdout
import json
import os
from pathlib import Path
import sys
from unittest.mock import Mock

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.gemini import Gemini
from app.integrations.learning_http import ProviderError
from app.models.course import Course
from app.pipelines.learning import answer_follow_up, generate_learning


def check_sample(db, gemini, course, extraction, question, page_number):
    result = generate_learning(db, gemini, course, extraction)
    if question is not None:
        page = result["pages"].get(str(page_number))
        if page is None or not page["analysis"]["question_eligible"]:
            raise ValueError(f"Page {page_number} has no eligible lecture content")
        source = next(page for page in extraction["pages"] if page["page_number"] == page_number)
        answer = answer_follow_up(gemini, source, question)
        result["follow_up"] = {
            "page_number": page_number,
            "question": question,
            **answer.model_dump(mode="json"),
        }
    return result


def check_with_catalog(gemini, args, extraction):
    from app.db.session import engine

    # Keep any research cache written during the check inside a rolled-back transaction.
    with engine.connect() as connection:
        connection.begin()
        with Session(bind=connection, join_transaction_mode="create_savepoint") as db:
            query = select(Course).where(Course.course_code == args.course_code)
            if args.curriculum_year is not None:
                query = query.where(Course.curriculum_year == args.curriculum_year)
            courses = db.scalars(query).all()
            if len(courses) != 1:
                raise ValueError("Expected one indexed course. Check --course-code and --curriculum-year.")
            return check_sample(db, gemini, courses[0], extraction, args.ask, args.page)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("extraction", type=Path, help="Team extraction v1 JSON")
    parser.add_argument("--course-name", default="데이터베이스", help="Course name for the no-database check")
    parser.add_argument("--course-code", help="Use an existing course and its index in DATABASE_URL")
    parser.add_argument("--curriculum-year", type=int, help="Disambiguate an indexed course by year")
    parser.add_argument("--page", type=int, default=2, help="Original PDF page number for --ask")
    parser.add_argument("--ask", help="Also generate an answer to a follow-up question")
    args = parser.parse_args(argv)
    if args.course_code is not None and not os.environ.get("DATABASE_URL"):
        parser.error("--course-code requires DATABASE_URL")

    try:
        extraction = json.loads(args.extraction.read_text(encoding="utf-8"))
        gemini = Gemini()
        with redirect_stdout(sys.stderr):
            if args.course_code is not None:
                result = check_with_catalog(gemini, args, extraction)
            else:
                db = Mock()
                db.scalar.return_value = None
                db.get.return_value = None
                course = Course(name=args.course_name, is_trend_enabled=False)
                result = check_sample(db, gemini, course, extraction, args.ask, args.page)
    except (ProviderError, OSError, ValueError) as error:
        parser.exit(1, f"{error}\n")

    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

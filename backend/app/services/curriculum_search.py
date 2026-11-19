import argparse
import json
from pathlib import Path
from zipfile import ZipFile

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.gemini import Gemini
from app.models.course import Course
from app.models.learning import CourseLearningProfile


def read_catalog(path: Path) -> tuple[int, list[dict]]:
    with ZipFile(path) as archive:
        manifest = json.loads(archive.read("manifest.json"))
        index = json.loads(archive.read(manifest["course_index"]))
        catalog = []
        for entry in index["courses"]:
            syllabus_ref = entry.get("syllabus")
            topics = []
            if syllabus_ref:
                syllabus = json.loads(archive.read(syllabus_ref["path"]))
                if syllabus["course"]["course_id"] != entry["course_id"]:
                    raise ValueError("Syllabus and catalog course IDs disagree")
                topics = list(dict.fromkeys(
                    topic["text"].strip()
                    for week in syllabus["weekly_topics"]
                    for topic in week["topics"]
                    if topic["text"].strip()
                ))
            catalog.append({
                "corpus_id": entry["course_id"], "name": entry["name"],
                "code": entry["course_code"], "topics": topics,
            })
    if len({entry["corpus_id"] for entry in catalog}) != len(catalog):
        raise ValueError("The catalog contains duplicate course IDs")
    return index["curriculum_entry_year"], catalog


def import_catalog(db: Session, gemini: Gemini, path: Path) -> int:
    year, catalog = read_catalog(path)
    vectors = []
    # The Gemini batch embedding endpoint accepts up to 100 requests.
    for offset in range(0, len(catalog), 20):
        entries = catalog[offset:offset + 20]
        vectors.extend(gemini.embed(
            ["\n".join([entry["name"], *entry["topics"]])[:8000] for entry in entries],
            "RETRIEVAL_DOCUMENT",
        ))

    for entry, vector in zip(catalog, vectors, strict=True):
        profile = db.scalar(select(CourseLearningProfile).where(
            CourseLearningProfile.corpus_id == entry["corpus_id"]
        ))
        if profile is None:
            # Reuse an existing Course row so uploaded documents keep their course ID.
            identity = Course.course_code == entry["code"] if entry["code"] else Course.name == entry["name"]
            existing = db.scalars(select(Course).where(identity)).all()
            matches = [course for course in existing if course.curriculum_year in (None, year)]
            if len(matches) > 1:
                raise ValueError(f"Ambiguous course mapping: {entry['corpus_id']}")
            course = matches[0] if matches else Course(
                name=entry["name"], course_code=entry["code"], curriculum_year=year,
            )
            db.add(course)
            db.flush()
            if db.get(CourseLearningProfile, course.id) is not None:
                raise ValueError(f"Course already mapped to a different corpus ID: {entry['corpus_id']}")
            profile = CourseLearningProfile(course_id=course.id, corpus_id=entry["corpus_id"])
            db.add(profile)
        profile.topics = entry["topics"]
        profile.embedding_model = gemini.embedding_model
        profile.embedding = vector
    db.commit()
    return len(catalog)


def find_candidates(db: Session, course_id, embedding_model: str, vector: list[float]) -> list[dict]:
    query = (
        select(Course.id, Course.name, CourseLearningProfile.topics)
        .join(CourseLearningProfile, CourseLearningProfile.course_id == Course.id)
        .where(Course.id != course_id, CourseLearningProfile.embedding_model == embedding_model)
        .order_by(CourseLearningProfile.embedding.cosine_distance(vector), Course.id)
        .limit(5)
    )
    return [
        {"course_id": str(course.id), "name": course.name, "topics": course.topics}
        for course in db.execute(query)
    ]


def main():
    parser = argparse.ArgumentParser(description="Index the pdf_extraction curriculum demo ZIP")
    parser.add_argument("corpus", type=Path)
    args = parser.parse_args()
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        print(f"Indexed {import_catalog(db, Gemini(), args.corpus)} courses")


if __name__ == "__main__":
    main()

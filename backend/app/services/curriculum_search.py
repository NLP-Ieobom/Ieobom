import argparse
import json
from pathlib import Path
from uuid import UUID
from zipfile import ZipFile

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.integrations.gemini import Gemini
from app.models.course import Course
from app.models.curriculum import Curriculum
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
            orders = [
                placement["year"] * 10 + placement["semester"]
                for placement in entry.get("placements", [])
                if isinstance(placement.get("year"), int) and isinstance(placement.get("semester"), int)
            ]
            catalog.append({
                "corpus_id": entry["course_id"], "name": entry["name"],
                "code": entry["course_code"], "topics": topics,
                # 트랙마다 편성 학기가 다르면 가장 이른 학기를 쓴다
                "semester_order": min(orders) if orders else None,
            })
    if len({entry["corpus_id"] for entry in catalog}) != len(catalog):
        raise ValueError("The catalog contains duplicate course IDs")
    return index["curriculum_entry_year"], catalog


def import_catalog(db: Session, gemini: Gemini, path: Path, curriculum_id: UUID) -> int:
    year, catalog = read_catalog(path)
    curriculum = db.get(Curriculum, curriculum_id)
    if curriculum is None or curriculum.entry_year != year:
        raise ValueError("Choose a curriculum matching the catalog entry year")
    vectors = []
    for offset in range(0, len(catalog), 20):
        entries = catalog[offset:offset + 20]
        vectors.extend(gemini.embed(
            ["\n".join([entry["name"], *entry["topics"]])[:8000] for entry in entries],
            "RETRIEVAL_DOCUMENT", call="COURSE_EMBED",
        ))

    for entry, vector in zip(catalog, vectors, strict=True):
        profile = db.scalar(select(CourseLearningProfile).where(
            CourseLearningProfile.corpus_id == entry["corpus_id"]
        ))
        if profile is not None and db.get(Course, profile.course_id).curriculum_id != curriculum_id:
            raise ValueError(f"Catalog course belongs to another curriculum: {entry['corpus_id']}")
        if profile is None:
            # 같은 커리큘럼의 기존 과목 ID를 유지해야 업로드한 문서 연결이 끊기지 않는다.
            identity = Course.course_code == entry["code"] if entry["code"] else Course.name == entry["name"]
            existing = db.scalars(select(Course).where(identity, Course.curriculum_id == curriculum_id)).all()
            matches = [course for course in existing if course.curriculum_year in (None, year)]
            if len(matches) > 1:
                raise ValueError(f"Ambiguous course mapping: {entry['corpus_id']}")
            course = matches[0] if matches else Course(
                name=entry["name"], course_code=entry["code"], curriculum_year=year, curriculum_id=curriculum_id,
            )
            db.add(course)
            db.flush()
            if db.get(CourseLearningProfile, course.id) is not None:
                raise ValueError(f"Course already mapped to a different corpus ID: {entry['corpus_id']}")
            profile = CourseLearningProfile(course_id=course.id, corpus_id=entry["corpus_id"])
            db.add(profile)
        profile.topics = entry["topics"]
        profile.semester_order = entry["semester_order"]
        profile.embedding_model = gemini.embedding_model
        profile.embedding = vector
    db.commit()
    return len(catalog)


def find_candidates(
    db: Session, course_id, embedding_model: str, vector: list[float], *,
    curriculum_id: UUID | None = None,
    relation: str = "related", semester_order: int | None = None, limit: int = 5,
) -> list[dict]:
    """Return the courses nearest to the slide vector.

    relation="previous" keeps courses placed before semester_order and "next" keeps those after it.
    Courses in the same semester belong to neither. "related" ignores semesters.
    """
    query = (
        select(Course.id, Course.name, CourseLearningProfile.topics)
        .join(CourseLearningProfile, CourseLearningProfile.course_id == Course.id)
        .where(Course.id != course_id, CourseLearningProfile.embedding_model == embedding_model)
        .where(Course.curriculum_id == curriculum_id)
    )
    if relation == "previous":
        query = query.where(CourseLearningProfile.semester_order < semester_order)
    elif relation == "next":
        query = query.where(CourseLearningProfile.semester_order > semester_order)
    query = query.order_by(CourseLearningProfile.embedding.cosine_distance(vector), Course.id).limit(limit)
    return [
        {"course_id": str(course.id), "name": course.name, "topics": course.topics, "relation": relation}
        for course in db.execute(query)
    ]


def main():
    parser = argparse.ArgumentParser(description="Index the pdf_extraction curriculum demo ZIP")
    parser.add_argument("corpus", type=Path)
    parser.add_argument("--curriculum-id", type=UUID, required=True)
    args = parser.parse_args()
    from app.db.session import SessionLocal

    with SessionLocal() as db:
        print(f"Indexed {import_catalog(db, Gemini(), args.corpus, args.curriculum_id)} courses")


if __name__ == "__main__":
    main()

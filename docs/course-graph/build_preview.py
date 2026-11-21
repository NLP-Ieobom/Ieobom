"""Build a portable course-graph preview from the complete curriculum JSON."""

import argparse
import json
from pathlib import Path


def build_preview(source: Path, output: Path) -> None:
    data = json.loads(source.read_text(encoding="utf-8"))
    for key in ("nodes", "edges", "tracks"):
        if not isinstance(data.get(key), list):
            raise ValueError(f"Expected a '{key}' array in {source}.")
    node_ids = [node["course_id"] for node in data["nodes"]]
    if len(set(node_ids)) != len(node_ids):
        raise ValueError("Course IDs must be unique.")
    known_ids = set(node_ids)
    for edge in data["edges"]:
        if edge["from_course_id"] not in known_ids or edge["to_course_id"] not in known_ids:
            raise ValueError(f"An edge references a missing course: {edge}.")

    template = Path(__file__).with_name("preview.template.html").read_text(encoding="utf-8")
    marker = "__COURSE_GRAPH_JSON__"
    if template.count(marker) != 1:
        raise ValueError("The HTML template must contain one JSON placeholder.")
    payload = json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    payload = payload.replace("<", "\\u003c").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(template.replace(marker, payload), encoding="utf-8")
    print(f"{output}: {len(data['nodes'])} courses, {len(data['edges'])} connections")


def main() -> None:
    repo = Path(__file__).resolve().parents[2]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source", nargs="?", type=Path,
        default=repo / "backend/app/data/ssu_ai_software_2026.json",
    )
    parser.add_argument(
        "--output", "-o", type=Path,
        default=Path(__file__).with_name("preview.html"),
    )
    args = parser.parse_args()
    build_preview(args.source, args.output)


if __name__ == "__main__":
    main()

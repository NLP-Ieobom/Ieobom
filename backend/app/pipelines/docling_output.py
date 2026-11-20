"""Read the current worker's Docling exports as page/block extraction v1."""

import hashlib
import json
import math
from pathlib import Path

LABEL_KINDS = {
    "title": "title",
    "section_header": "title",
    "text": "text",
    "paragraph": "text",
    "list_item": "list_item",
    "table": "table",
    "document_index": "table",
    "picture": "figure",
    "formula": "formula",
    "code": "code",
    "caption": "caption",
    "page_header": "header",
    "page_footer": "footer",
    "footnote": "footer",
}


def _items(document: dict, node: dict):
    if node.get("content_layer", "body") in {"body", "furniture"} and node.get("prov"):
        yield node
    for child in node.get("children", []):
        ref = child.get("$ref") or child["cref"]
        _, collection, offset = ref.split("/")
        yield from _items(document, document[collection][int(offset)])


def _make_block(item: dict, provenance: dict, page: dict) -> dict | None:
    bbox = provenance["bbox"]
    width, height = page["width_pt"], page["height_pt"]
    top, bottom = bbox["t"], bbox["b"]
    if bbox["coord_origin"] == "BOTTOMLEFT":
        top, bottom = height - top, height - bottom
    box = [bbox["l"] / width, top / height, bbox["r"] / width, bottom / height]
    if not all(math.isfinite(value) for value in box):
        return None
    left, top, right, bottom = [max(0.0, min(1.0, value)) for value in box]
    if left >= right or top >= bottom:
        return None

    text = item.get("text")
    if text is not None:
        start, end = provenance["charspan"]
        if 0 <= start < end <= len(text):
            text = text[start:end]
        elif len(item["prov"]) > 1:
            text = None
    label = item["label"]
    block = {
        "block_id": f"p{page['page_number']:04d}-b{len(page['blocks']) + 1:04d}",
        "kind": LABEL_KINDS.get(label, "other"),
        "docling_label": label,
        "text": text,
        "bbox": [left, top, right, bottom],
    }
    if label in {"table", "document_index"}:
        table = item["data"]
        block["table"] = {
            "row_count": table["num_rows"],
            "column_count": table["num_cols"],
            "cells": [
                {
                    "row_start": cell["start_row_offset_idx"],
                    "row_end": cell["end_row_offset_idx"],
                    "column_start": cell["start_col_offset_idx"],
                    "column_end": cell["end_col_offset_idx"],
                    "text": cell["text"],
                    "column_header": cell["column_header"],
                    "row_header": cell["row_header"],
                }
                for cell in table["table_cells"]
            ],
        }
    return block


def _pages(batch: dict) -> dict[int, dict]:
    pages = {
        item["page_no"]: {
            "page_number": item["page_no"],
            "width_pt": item["size"]["width"],
            "height_pt": item["size"]["height"],
            "blocks": [],
        }
        for item in batch["pages"].values()
    }
    if any(
        not math.isfinite(size) or size <= 0
        for page in pages.values() for size in (page["width_pt"], page["height_pt"])
    ):
        raise ValueError("Docling returned invalid page dimensions")
    for root in ("body", "furniture"):
        for item in _items(batch, batch[root]):
            for provenance in item.get("prov", []):
                page = pages[provenance["page_no"]]
                block = _make_block(item, provenance, page)
                if block is not None:
                    page["blocks"].append(block)
    return pages


def load_docling_extraction(output_dir: Path, pdf: Path, document_id: str, filename: str) -> dict:
    manifests = list(output_dir.glob("*/manifest.json"))
    if len(manifests) != 1:
        raise ValueError("Expected one Docling manifest for this job attempt")
    manifest_path = manifests[0]
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest["status"] != "success" or manifest["selection"] != "all_pages":
        raise ValueError("Docling did not finish converting the full document")
    pages = {}
    for batch_name in dict.fromkeys(page["docling_json"] for page in manifest["pages"]):
        if Path(batch_name).name != batch_name:
            raise ValueError("Invalid Docling batch file name")
        path = manifest_path.with_name(batch_name)
        batch = _pages(json.loads(path.read_text(encoding="utf-8")))
        if pages.keys() & batch.keys():
            raise ValueError("Docling repeated an original page number")
        pages.update(batch)
    if set(pages) != set(range(1, manifest["total_pdf_pages"] + 1)):
        raise ValueError("Docling exports do not cover every original page")
    with pdf.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()
    return {
        "schema_version": "1.0",
        "document_id": document_id,
        "source": {"filename": filename, "sha256": digest},
        "coordinate_system": "normalized_top_left",
        "pages": [pages[number] for number in sorted(pages)],
        "warnings": [],
    }

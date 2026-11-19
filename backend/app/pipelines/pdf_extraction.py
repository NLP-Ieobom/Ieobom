"""Convert lecture PDFs to the Ieobom page/block JSON contract."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
from pathlib import Path
from typing import Any


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


def _normalized_bbox(bbox: Any, width: float, height: float) -> list[float] | None:
    rect = bbox.to_top_left_origin(height)
    values = [rect.l / width, rect.t / height, rect.r / width, rect.b / height]
    if not all(math.isfinite(value) for value in values):
        return None
    left, top, right, bottom = [min(1.0, max(0.0, value)) for value in values]
    if left >= right or top >= bottom:
        return None
    return [left, top, right, bottom]


def _table_data(item: Any) -> dict:
    return {
        "row_count": item.data.num_rows,
        "column_count": item.data.num_cols,
        "cells": [
            {
                "row_start": cell.start_row_offset_idx,
                "row_end": cell.end_row_offset_idx,
                "column_start": cell.start_col_offset_idx,
                "column_end": cell.end_col_offset_idx,
                "text": cell.text,
                "column_header": cell.column_header,
                "row_header": cell.row_header,
            }
            for cell in item.data.table_cells
        ],
    }


def _normalize_document(
    document: Any, document_id: str, filename: str, sha256: str, warnings: list[dict]
) -> dict:
    from docling_core.types.doc import ContentLayer, DocItem, TableItem, TextItem

    pages = {}
    for page_number, page in sorted(document.pages.items()):
        width, height = float(page.size.width), float(page.size.height)
        if not all(math.isfinite(value) and value > 0 for value in (width, height)):
            raise ValueError(f"Invalid page dimensions on page {page_number}.")
        pages[page_number] = {
            "page_number": page_number,
            "width_pt": width,
            "height_pt": height,
            "blocks": [],
        }

    for item, _ in document.iterate_items(
        traverse_pictures=True,
        included_content_layers={ContentLayer.BODY, ContentLayer.FURNITURE},
    ):
        if not isinstance(item, DocItem):
            continue
        if not item.prov:
            warnings.append({
                "code": "missing_provenance",
                "message": f"{item.self_ref} has no page or bounding box.",
            })
            continue

        label = item.label.value
        kind = LABEL_KINDS.get(label, "other")
        table = _table_data(item) if isinstance(item, TableItem) else None
        for provenance in item.prov:
            page = pages.get(provenance.page_no)
            if page is None:
                warnings.append({
                    "code": "missing_page",
                    "message": f"{item.self_ref} references a missing page.",
                    "page_number": provenance.page_no,
                })
                continue

            bbox = _normalized_bbox(provenance.bbox, page["width_pt"], page["height_pt"])
            if bbox is None:
                warnings.append({
                    "code": "invalid_bbox",
                    "message": f"{item.self_ref} has no drawable area on this page.",
                    "page_number": provenance.page_no,
                })
                continue

            block_text = None
            if isinstance(item, TextItem):
                start, end = provenance.charspan
                if 0 <= start < end <= len(item.text):
                    block_text = item.text[start:end]
                elif len(item.prov) == 1:
                    block_text = item.text
                else:
                    warnings.append({
                        "code": "invalid_text_span",
                        "message": f"{item.self_ref} has no valid text span for this area.",
                        "page_number": provenance.page_no,
                    })

            blocks = page["blocks"]
            block = {
                "block_id": f"p{provenance.page_no:04d}-b{len(blocks) + 1:04d}",
                "kind": kind,
                "docling_label": label,
                "text": block_text,
                "bbox": bbox,
            }
            if table is not None:
                block["table"] = table
            blocks.append(block)

    for page in pages.values():
        if not any(block["text"] or block.get("table") for block in page["blocks"]):
            warnings.append({
                "code": "no_text",
                "message": "No text or table extracted. Inspect the page and try OCR if it is a scan.",
                "page_number": page["page_number"],
            })
    return {
        "schema_version": "1.0",
        "document_id": document_id,
        "source": {"filename": filename, "sha256": sha256},
        "coordinate_system": "normalized_top_left",
        "pages": list(pages.values()),
        "warnings": warnings,
    }


def extract_pdf(
    pdf_path: Path,
    *,
    document_id: str | None = None,
    ocr: bool = False,
    page: int | None = None,
    pdf_backend: str = "default",
    table_structure: bool = True,
) -> dict:
    """Run Docling on a local PDF, optionally retaining only one original page."""
    if not pdf_path.is_file() or pdf_path.suffix.lower() != ".pdf":
        raise ValueError(f"Expected a local .pdf file: {pdf_path}")
    if document_id is not None and not document_id.strip():
        raise ValueError("Document ID must not be blank.")
    if page is not None and (type(page) is not int or page < 1):
        raise ValueError("Page number must be a positive integer.")
    if pdf_backend not in {"default", "pdfium"}:
        raise ValueError(f"Unknown Docling PDF backend: {pdf_backend}.")

    from docling.datamodel.base_models import ConversionStatus, InputFormat
    from docling.datamodel.pipeline_options import PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    with pdf_path.open("rb") as source:
        digest = hashlib.file_digest(source, "sha256").hexdigest()

    options = PdfPipelineOptions(do_ocr=ocr, do_table_structure=table_structure)
    if pdf_backend == "pdfium":
        from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend

        format_option = PdfFormatOption(
            pipeline_options=options, backend=PyPdfiumDocumentBackend
        )
    else:
        format_option = PdfFormatOption(pipeline_options=options)

    converter = DocumentConverter(
        allowed_formats=[InputFormat.PDF],
        format_options={InputFormat.PDF: format_option},
    )
    if page is None:
        result = converter.convert(pdf_path, raises_on_error=False)
    else:
        result = converter.convert(pdf_path, page_range=(page, page), raises_on_error=False)
    warnings = [
        {"code": "docling_conversion", "message": error.error_message}
        for error in result.errors
    ]
    if result.status not in {ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS}:
        details = "; ".join(warning["message"] for warning in warnings)
        raise ValueError(f"Docling conversion failed ({result.status.value}). {details}".strip())
    if result.status == ConversionStatus.PARTIAL_SUCCESS:
        warnings.append({
            "code": "partial_conversion",
            "message": "Docling reported a partial conversion. Check the page coverage.",
        })
    if not result.document.pages:
        raise ValueError("Docling returned no pages.")

    expected_pages = (
        {page} if page is not None else set(range(1, result.input.page_count + 1))
    )
    if set(result.document.pages) != expected_pages:
        raise ValueError("Docling did not return geometry for every requested PDF page.")

    return _normalize_document(
        result.document, document_id or digest, pdf_path.name, digest, warnings
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    extract = commands.add_parser("extract", help="Run Docling and save the extracted JSON.")
    extract.add_argument("pdf", type=Path)
    extract.add_argument("--output", "-o", type=Path, required=True, help="Output JSON path.")
    extract.add_argument("--document-id", help="Use the database document ID when available.")
    extract.add_argument("--ocr", action="store_true", help="Enable Docling OCR for scanned PDFs.")
    extract.add_argument("--page", type=int, help="Extract only this 1-based original PDF page.")
    extract.add_argument(
        "--no-table-structure", action="store_true",
        help="Skip table cell analysis when testing a page without tables.",
    )
    extract.add_argument(
        "--pdf-backend", choices=["default", "pdfium"], default="default",
        help="PDF backend used with Docling's standard layout pipeline.",
    )

    overlay = commands.add_parser("overlay", help="Draw saved JSON boxes on PDF page images.")
    overlay.add_argument("pdf", type=Path)
    overlay.add_argument("json", type=Path)
    overlay.add_argument("--output-dir", "-o", type=Path, required=True)
    overlay.add_argument("--page", type=int, action="append", help="1-based page, repeat as needed.")
    overlay.add_argument("--block-id", action="append", help="Render only this block, repeat as needed.")
    overlay.add_argument("--dpi", type=int, default=144)

    args = parser.parse_args(argv)
    try:
        if args.command == "extract":
            if args.output.suffix.lower() != ".json" or args.output.resolve() == args.pdf.resolve():
                raise ValueError("--output must be a separate .json file.")
            payload = extract_pdf(
                args.pdf, document_id=args.document_id, ocr=args.ocr,
                page=args.page, pdf_backend=args.pdf_backend,
                table_structure=not args.no_table_structure,
            )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(payload, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                encoding="utf-8",
            )
            block_count = sum(len(page["blocks"]) for page in payload["pages"])
            print(
                f"{args.output}: {len(payload['pages'])} pages, {block_count} blocks, "
                f"{len(payload['warnings'])} warnings"
            )
        else:
            from .pdf_overlay import render_overlays

            payload = json.loads(args.json.read_text(encoding="utf-8"))
            try:
                paths = render_overlays(
                    args.pdf,
                    payload,
                    args.output_dir,
                    page_numbers=set(args.page) if args.page else None,
                    block_ids=args.block_id,
                    dpi=args.dpi,
                )
            except (KeyError, TypeError) as exc:
                raise ValueError(f"Invalid extraction JSON ({exc}).") from exc
            for path in paths:
                print(path)
    except (ImportError, OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())

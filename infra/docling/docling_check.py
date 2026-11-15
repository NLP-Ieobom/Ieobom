#!/usr/bin/env python3
"""One-shot CPU Docling check; this is not a persistent job worker.

The default converts only the FIRST 5 pages. Use --all-pages for the whole PDF.
Each invocation creates its own output subdirectory and never overwrites a run.
"""
import argparse
import gc
import importlib.metadata
import json
import os
from pathlib import Path
import resource
import sys
import time
from datetime import datetime, timezone
from uuid import uuid4


def positive_int(value):
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be at least 1")
    return number


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


def peak_rss_mib():
    # Linux reports ru_maxrss in KiB. This is one process, not container memory.
    return round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024, 2)


def make_converter(ocr):
    for name in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "OPENBLAS_NUM_THREADS"):
        os.environ[name] = "1"
    from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
    from docling.datamodel.backend_options import ThreadedDoclingParseBackendOptions
    from docling.datamodel.base_models import InputFormat
    from docling.datamodel.pipeline_options import EasyOcrOptions, PdfPipelineOptions
    from docling.document_converter import DocumentConverter, PdfFormatOption

    options = PdfPipelineOptions(
        do_ocr=ocr, do_table_structure=True,
        do_picture_classification=False, do_picture_description=False,
        do_code_enrichment=False, do_formula_enrichment=False,
        generate_page_images=True, generate_picture_images=False,
        images_scale=1.0, queue_max_size=1,
        layout_batch_size=1, table_batch_size=1, ocr_batch_size=1,
        document_timeout=600,
    )
    options.accelerator_options = AcceleratorOptions(
        device=AcceleratorDevice.CPU, num_threads=1,
    )
    if ocr:
        options.ocr_options = EasyOcrOptions(lang=["ko", "en"], use_gpu=False)
    artifacts = os.environ.get("DOCLING_ARTIFACTS_PATH", "").strip()
    if artifacts:
        directory = Path(artifacts)
        if not directory.is_dir() or not any(directory.iterdir()):
            raise ValueError("DOCLING_ARTIFACTS_PATH must contain downloaded models; otherwise unset it.")
        options.artifacts_path = directory
    return DocumentConverter(format_options={
        InputFormat.PDF: PdfFormatOption(
            pipeline_options=options,
            backend_options=ThreadedDoclingParseBackendOptions(
                parser_threads=1, max_concurrent_results=1,
            ),
        )
    })


def export_batch(result, start, end, output):
    from docling_core.types.doc import ImageRefMode

    doc = result.document
    stem = f"batch_{start:04d}_{end:04d}"
    expected = set(range(start, end + 1))
    actual = {int(number) for number in doc.pages}
    problems = []
    if actual != expected:
        problems.append(f"Expected original PDF pages {sorted(expected)}; got {sorted(actual)}.")
    items = [*doc.texts, *doc.tables, *doc.pictures]
    for item in items:
        for provenance in item.prov:
            if provenance.page_no not in expected:
                problems.append(f"Item {item.self_ref} has out-of-range page {provenance.page_no}.")
    records = []
    for key, page in sorted(doc.pages.items()):
        number = int(page.page_no)
        if number != int(key) or number not in expected:
            problems.append(f"Invalid page key/number: {key}/{number}.")
            continue
        if page.image is None or page.image.pil_image is None:
            problems.append(f"Page {number} has no rendered image.")
            continue
        image_path = output / f"page_{number:04d}.png"
        if image_path.exists():
            raise RuntimeError(f"Refusing to overwrite {image_path.name}")
        page.image.pil_image.save(image_path, format="PNG")
        text_items = [item for item in doc.texts if any(p.page_no == number for p in item.prov)]
        records.append({
            "original_page_no": number, "image": image_path.name,
            "docling_json": stem + ".json", "text_items": len(text_items),
            "text_characters": sum(len(item.text) for item in text_items),
            "table_items": sum(any(p.page_no == number for p in item.prov) for item in doc.tables),
            "picture_items": sum(any(p.page_no == number for p in item.prov) for item in doc.pictures),
        })
    # Referenced mode retains a loadable Docling JSON without inline base64 images.
    # Its assets are separate from the numbered PNGs intended for quick inspection.
    # A relative artifacts_dir makes image URIs relative to the JSON file itself.
    doc.save_as_json(output / (stem + ".json"), artifacts_dir=Path(stem + "_assets"),
                     image_mode=ImageRefMode.REFERENCED)
    doc.save_as_markdown(output / (stem + ".md"), image_mode=ImageRefMode.PLACEHOLDER)
    return records, problems


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pdf", type=Path, help="local PDF path, not a URL")
    parser.add_argument("--output-dir", type=Path, default=Path("/work/output"))
    selection = parser.add_mutually_exclusive_group()
    selection.add_argument("--max-pages", type=positive_int, default=5,
                           help="convert only the first N pages (default: 5)")
    selection.add_argument("--all-pages", action="store_true", help="convert the entire PDF")
    parser.add_argument("--batch-pages", type=positive_int, default=5)
    parser.add_argument("--ocr", action="store_true", help="enable Korean/English EasyOCR")
    args = parser.parse_args()
    source = args.pdf.expanduser().resolve()
    if not source.is_file():
        parser.error("pdf must be an existing local file")
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    output = args.output_dir.expanduser().resolve() / run_id
    output.mkdir(parents=True, exist_ok=False)
    manifest_path = output / "manifest.json"
    started = time.perf_counter()
    manifest = {
        "run_id": run_id, "status": "running", "source": str(source),
        "ocr": args.ocr, "batch_pages": args.batch_pages,
        "versions": {"python": sys.version.split()[0]}, "batches": [], "pages": [],
        "validation_scope": "Selected page coverage and original page numbers; not semantic extraction accuracy.",
        "rss_scope": "Linux process high-water RSS, including model initialization; not total container/host memory.",
    }
    write_json(manifest_path, manifest)
    print(f"Run output: {output}", flush=True)
    exit_code = 0
    try:
        import pypdfium2 as pdfium
        from docling.datamodel.base_models import ConversionStatus

        for package in ("docling", "docling-core", "docling-parse", "pypdfium2", "torch"):
            manifest["versions"][package] = importlib.metadata.version(package)
        pdf = pdfium.PdfDocument(source)
        try:
            total = len(pdf)
        finally:
            pdf.close()
        if total < 1:
            raise ValueError("PDF has no pages")
        selected = total if args.all_pages else min(total, args.max_pages)
        manifest.update(total_pdf_pages=total, selected_pages=selected,
                        selection="all_pages" if args.all_pages else "first_n_pages",
                        selection_is_truncated=selected < total)
        write_json(manifest_path, manifest)
        print(f"Converting original pages 1-{selected} of {total}; OCR={args.ocr}", flush=True)
        converter = make_converter(args.ocr)
        for start in range(1, selected + 1, args.batch_pages):
            end = min(start + args.batch_pages - 1, selected)
            batch_start = time.perf_counter()
            result = converter.convert(source, page_range=(start, end), raises_on_error=False)
            batch = {"page_range": [start, end], "status": result.status.value,
                     "conversion_seconds": round(time.perf_counter() - batch_start, 3),
                     "errors": [str(error)[:1000] for error in result.errors]}
            manifest["batches"].append(batch)
            if result.status in (ConversionStatus.SUCCESS, ConversionStatus.PARTIAL_SUCCESS):
                records, problems = export_batch(result, start, end, output)
                manifest["pages"].extend(records)
                batch["validation_errors"] = problems
            else:
                batch["validation_errors"] = ["Conversion did not produce a successful document."]
            batch["process_peak_rss_mib"] = peak_rss_mib()
            write_json(manifest_path, manifest)
            if result.status != ConversionStatus.SUCCESS or batch["validation_errors"]:
                raise RuntimeError(f"Pages {start}-{end} failed or were partial; inspect manifest.json.")
            del result
            gc.collect()
            print(f"Pages {start}-{end}: success ({batch['conversion_seconds']} s)", flush=True)
        if {page["original_page_no"] for page in manifest["pages"]} != set(range(1, selected + 1)):
            raise RuntimeError("Final selected-page coverage check failed.")
        manifest["status"] = "success"
    except KeyboardInterrupt:
        manifest.update(status="interrupted", error="Interrupted by user")
        exit_code = 130
    except Exception as error:
        manifest.update(status="failed", error=f"{type(error).__name__}: {error}")
        print(manifest["error"], file=sys.stderr, flush=True)
        exit_code = 1
    finally:
        manifest.update(elapsed_seconds=round(time.perf_counter() - started, 3),
                        process_peak_rss_mib=peak_rss_mib())
        write_json(manifest_path, manifest)
    print(f"Status: {manifest['status']}; manifest: {manifest_path}", flush=True)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

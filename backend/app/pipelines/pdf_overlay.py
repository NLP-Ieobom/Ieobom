"""Render extracted block positions on copies of the original PDF pages."""

from hashlib import file_digest
from math import isclose
from pathlib import Path

import pypdfium2 as pdfium
from PIL import ImageDraw, ImageFont


BLOCK_COLORS = {
    "title": "#155fc3",
    "text": "#25743a",
    "list_item": "#25743a",
    "table": "#aa4a00",
    "figure": "#8535ac",
    "formula": "#b12957",
    "code": "#007285",
    "caption": "#60536e",
}


def _draw_blocks(
    image, blocks: list[dict], dpi: int, block_ids: set[str] | None
) -> None:
    draw = ImageDraw.Draw(image)
    font = ImageFont.load_default(size=max(10, round(dpi / 12)))
    line_width = max(1, round(dpi / 96))
    labels = []

    for index, block in enumerate(blocks, 1):
        if block_ids is not None and block["block_id"] not in block_ids:
            continue
        left, top, right, bottom = block["bbox"]
        if not (0 <= left < right <= 1 and 0 <= top < bottom <= 1):
            raise ValueError(f"Invalid normalized bbox for {block['block_id']}.")
        # Multiply by the rendered size, then bound coordinates at the last pixel.
        x0 = min(round(left * image.width), image.width - 1)
        y0 = min(round(top * image.height), image.height - 1)
        x1 = min(round(right * image.width), image.width - 1)
        y1 = min(round(bottom * image.height), image.height - 1)
        color = BLOCK_COLORS.get(block["kind"], "#526171")
        draw.rectangle((x0, y0, x1, y1), outline=color, width=line_width)
        labels.append((str(index), x0, y0, color))

    for label, x, y, color in labels:
        left, top, right, bottom = draw.textbbox((0, 0), label, font=font)
        label_width = right - left + 6
        label_height = bottom - top + 4
        x = max(0, min(x, image.width - label_width))
        # Prefer the space above the block so the badge does not cover its text.
        y = max(0, min(y - label_height, image.height - label_height))
        draw.rectangle((x, y, x + label_width - 1, y + label_height - 1), fill=color)
        draw.text((x + 3 - left, y + 2 - top), label, fill="white", font=font)


def render_overlays(
    pdf_path: Path,
    extraction: dict,
    output_dir: Path,
    *,
    page_numbers: set[int] | None = None,
    block_ids: list[str] | None = None,
    dpi: int = 144,
) -> list[Path]:
    """Write one PNG per selected 1-based page and return paths in page order.

    The number next to a box is the block's 1-based position in its page's JSON
    `blocks` array. Existing PNGs with the same page names are replaced.
    If block IDs are given, render only their pages and draw only those boxes.
    """
    if type(dpi) is not int or dpi <= 0:
        raise ValueError("DPI must be a positive integer.")
    if extraction["coordinate_system"] != "normalized_top_left":
        raise ValueError("Expected normalized_top_left coordinates.")

    pages_by_number = {}
    for entry in extraction["pages"]:
        number = entry["page_number"]
        if type(number) is not int or number < 1 or number in pages_by_number:
            raise ValueError(f"Invalid or repeated extraction page number: {number!r}.")
        pages_by_number[number] = entry

    selected = set(pages_by_number) if page_numbers is None else page_numbers
    if not selected:
        raise ValueError("Select at least one page to render.")
    missing = selected.difference(pages_by_number)
    if missing:
        raise ValueError(f"Pages missing from the extraction: {sorted(missing)}.")

    selected_ids = None
    if block_ids is not None:
        if not block_ids:
            raise ValueError("Select at least one block to render.")
        selected_ids = set(block_ids)
        if len(selected_ids) != len(block_ids):
            raise ValueError("Each requested block ID must appear only once.")

        block_pages = {}
        for number, page in pages_by_number.items():
            for block in page["blocks"]:
                block_id = block["block_id"]
                if block_id in block_pages:
                    raise ValueError(f"Repeated block ID in the extraction: {block_id!r}.")
                block_pages[block_id] = number
        unknown = selected_ids.difference(block_pages)
        if unknown:
            raise ValueError(f"Block IDs missing from the extraction: {sorted(unknown)}.")
        outside = {block_id for block_id in selected_ids if block_pages[block_id] not in selected}
        if outside:
            raise ValueError(f"Block IDs outside the selected pages: {sorted(outside)}.")
        selected = {block_pages[block_id] for block_id in selected_ids}

    selected = sorted(selected)

    outputs = []
    with pdf_path.open("rb") as pdf_stream:
        if file_digest(pdf_stream, "sha256").hexdigest() != extraction["source"]["sha256"]:
            raise ValueError("The PDF SHA-256 does not match the extraction JSON.")
        pdf_stream.seek(0)
        with pdfium.PdfDocument(pdf_stream) as pdf:
            if selected[-1] > len(pdf):
                raise ValueError(f"Page {selected[-1]} is outside the original PDF.")
            for number in selected:
                entry = pages_by_number[number]
                page = pdf[number - 1]
                try:
                    width, height = page.get_size()
                finally:
                    page.close()
                if not (
                    isclose(width, entry["width_pt"], rel_tol=0, abs_tol=0.5)
                    and isclose(height, entry["height_pt"], rel_tol=0, abs_tol=0.5)
                ):
                    raise ValueError(
                        f"Page {number} has different dimensions in the PDF and extraction. "
                        "Check the page crop and rotation before rendering boxes."
                    )

            output_dir.mkdir(parents=True, exist_ok=True)
            for number in selected:
                page = pdf[number - 1]
                try:
                    bitmap = page.render(scale=dpi / 72)
                    try:
                        image = bitmap.to_pil().convert("RGB")
                    finally:
                        bitmap.close()
                finally:
                    page.close()

                with image:
                    _draw_blocks(image, pages_by_number[number]["blocks"], dpi, selected_ids)
                    path = output_dir / f"page-{number:04d}.png"
                    image.save(path, dpi=(dpi, dpi))
                    outputs.append(path)
    return outputs

"""PDF Parser using PyMuPDF (fitz).

Extracts per-page text with character offsets and bounding boxes,
detects tables and serializes them to markdown, and renders page images for the UI evidence viewer.
"""

import fitz  # PyMuPDF
import os
import hashlib
from typing import List, Dict, Any, Optional
from app.config import settings


def parse_pdf(doc_id: str, file_path: str, job_id: Optional[str] = None) -> List[Dict[str, Any]]:
    """Parse PDF file into page structures with text, bounding boxes, tables, and page PNG images.

    Returns a list of dicts, one per page:
    [
        {
            "page_num": 1,
            "text": "...",
            "spans": [{"text": "...", "bbox": [x0, y0, x1, y1], "start": 0, "end": 10}, ...],
            "tables": [{"markdown": "...", "bbox": [...]}, ...],
            "width": 595.0,
            "height": 842.0
        }, ...
    ]
    """
    doc = fitz.open(file_path)
    pages_data = []
    total_pages = len(doc)

    # Ensure page images directory exists
    doc_pages_dir = os.path.join(settings.pages_dir, doc_id)
    os.makedirs(doc_pages_dir, exist_ok=True)

    if job_id:
        from app.jobs import update_job

    for page_index in range(total_pages):
        page = doc[page_index]
        page_num = page_index + 1

        # 1. Render page image for frontend evidence viewer (150 DPI for crisp text & low memory)
        pix = page.get_pixmap(dpi=150)
        img_path = os.path.join(doc_pages_dir, f"page_{page_num}.png")
        pix.save(img_path)

        # 2. Extract text layout & spans with bboxes
        text_page = page.get_text("dict")
        page_width = text_page.get("width", page.rect.width)
        page_height = text_page.get("height", page.rect.height)

        full_page_text = ""
        spans = []
        current_offset = 0

        # Extract text blocks
        for block in text_page.get("blocks", []):
            if block.get("type") == 0:  # Text block
                for line in block.get("lines", []):
                    line_text = ""
                    line_bbox = line.get("bbox")
                    for span in line.get("spans", []):
                        span_text = span.get("text", "")
                        if span_text:
                            line_text += span_text

                    if line_text.strip():
                        start_offset = current_offset
                        full_page_text += line_text + "\n"
                        current_offset = len(full_page_text)
                        end_offset = current_offset - 1  # Excluding newline

                        spans.append({
                            "text": line_text,
                            "bbox": [round(c, 2) for c in line_bbox] if line_bbox else [0, 0, 0, 0],
                            "start": start_offset,
                            "end": end_offset,
                        })

        # 3. Detect tables with PyMuPDF find_tables()
        tables_data = []
        try:
            tabs = page.find_tables()
            for tab in tabs:
                table_md = _table_to_markdown(tab)
                if table_md.strip():
                    tables_data.append({
                        "markdown": table_md,
                        "bbox": [round(c, 2) for c in tab.rect],
                    })
        except Exception:
            # Fallback if table detection fails on specific layout
            pass

        pages_data.append({
            "page_num": page_num,
            "text": full_page_text,
            "spans": spans,
            "tables": tables_data,
            "width": page_width,
            "height": page_height,
        })

        if job_id:
            # Parsing (page rendering + table detection) is the slowest stage on
            # dense multi-page filings, so report per-page progress instead of
            # leaving the job on a single frozen "Parsing PDF" stage for minutes.
            update_job(
                job_id,
                stage=f"Parsing PDF (page {page_num}/{total_pages})",
                progress=0.2 * page_num / total_pages,
            )

    # Update page count in documents table
    from app.db import get_db
    with get_db() as conn:
        conn.execute(
            "UPDATE documents SET page_count = ? WHERE doc_id = ?",
            (len(doc), doc_id),
        )

    doc.close()
    return pages_data


def _table_to_markdown(table) -> str:
    """Convert a PyMuPDF Table object to markdown table string."""
    try:
        df_rows = table.extract()
        if not df_rows or len(df_rows) == 0:
            return ""

        headers = [str(cell or "").strip().replace("\n", " ") for cell in df_rows[0]]
        # Build markdown header
        md = "| " + " | ".join(headers) + " |\n"
        md += "| " + " | ".join(["---"] * len(headers)) + " |\n"

        for row in df_rows[1:]:
            cells = [str(cell or "").strip().replace("\n", " ") for cell in row]
            md += "| " + " | ".join(cells) + " |\n"

        return md
    except Exception:
        return ""

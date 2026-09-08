"""Layout-aware chunking for extracted PDF pages.

Creates ~800 token chunks with ~100 token overlap while preserving exact
(doc_id, page, char_start, char_end) offsets for evidence grounding.
Serializes detected tables as dedicated table chunks.
"""

import uuid
from typing import List, Dict, Any
from app.db import get_db

TARGET_CHUNK_TOKENS = 600  # ~800 words
OVERLAP_TOKENS = 80


def chunk_document(doc_id: str, pages_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Create chunks from page data and save them to SQLite.

    Returns a list of created chunk dicts.
    """
    created_chunks = []

    with get_db() as conn:
        for page_info in pages_data:
            page_num = page_info["page_num"]
            page_text = page_info["text"]
            spans = page_info["spans"]
            tables = page_info["tables"]

            # 1. Process table chunks first
            for table in tables:
                table_md = table["markdown"]
                if not table_md.strip():
                    continue

                chunk_id = f"c_{uuid.uuid4().hex[:8]}"
                words = table_md.split()

                conn.execute(
                    """INSERT INTO chunks (chunk_id, doc_id, page, char_start, char_end, is_table, text, token_count)
                       VALUES (?, ?, ?, ?, ?, 1, ?, ?)""",
                    (chunk_id, doc_id, page_num, 0, len(table_md), table_md, len(words)),
                )

                created_chunks.append({
                    "chunk_id": chunk_id,
                    "doc_id": doc_id,
                    "page": page_num,
                    "char_start": 0,
                    "char_end": len(table_md),
                    "is_table": True,
                    "text": table_md,
                    "token_count": len(words),
                })

            # 2. Process text chunks for prose content
            if not spans:
                # Fallback if no spans were extracted
                if page_text.strip():
                    chunk_id = f"c_{uuid.uuid4().hex[:8]}"
                    words = page_text.split()
                    conn.execute(
                        """INSERT INTO chunks (chunk_id, doc_id, page, char_start, char_end, is_table, text, token_count)
                           VALUES (?, ?, ?, ?, ?, 0, ?, ?)""",
                        (chunk_id, doc_id, page_num, 0, len(page_text), page_text, len(words)),
                    )
                    created_chunks.append({
                        "chunk_id": chunk_id,
                        "doc_id": doc_id,
                        "page": page_num,
                        "char_start": 0,
                        "char_end": len(page_text),
                        "is_table": False,
                        "text": page_text,
                        "token_count": len(words),
                    })
                continue

            # Group spans into layout-aware chunks based on token length
            current_spans = []
            current_token_count = 0

            for span in spans:
                span_words = span["text"].split()
                span_token_count = len(span_words)

                if current_token_count + span_token_count > TARGET_CHUNK_TOKENS and current_spans:
                    # Flush current chunk
                    chunk_dict = _create_text_chunk(conn, doc_id, page_num, current_spans)
                    created_chunks.append(chunk_dict)

                    # Keep overlap spans for smooth context transition
                    overlap_spans = []
                    overlap_tokens = 0
                    for s in reversed(current_spans):
                        st_tokens = len(s["text"].split())
                        if overlap_tokens + st_tokens <= OVERLAP_TOKENS:
                            overlap_spans.insert(0, s)
                            overlap_tokens += st_tokens
                        else:
                            break

                    current_spans = overlap_spans
                    current_token_count = overlap_tokens

                current_spans.append(span)
                current_token_count += span_token_count

            # Flush final chunk on page
            if current_spans:
                chunk_dict = _create_text_chunk(conn, doc_id, page_num, current_spans)
                created_chunks.append(chunk_dict)

    return created_chunks


def _create_text_chunk(conn, doc_id: str, page_num: int, spans: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Helper to assemble a chunk from spans and insert into DB."""
    chunk_id = f"c_{uuid.uuid4().hex[:8]}"
    chunk_text = "\n".join(s["text"] for s in spans)
    char_start = spans[0]["start"]
    char_end = spans[-1]["end"]
    words = chunk_text.split()

    conn.execute(
        """INSERT INTO chunks (chunk_id, doc_id, page, char_start, char_end, is_table, text, token_count)
           VALUES (?, ?, ?, ?, ?, 0, ?, ?)""",
        (chunk_id, doc_id, page_num, char_start, char_end, chunk_text, len(words)),
    )

    return {
        "chunk_id": chunk_id,
        "doc_id": doc_id,
        "page": page_num,
        "char_start": char_start,
        "char_end": char_end,
        "is_table": False,
        "text": chunk_text,
        "token_count": len(words),
    }

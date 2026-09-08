"""High-level extractor module.

Processes chunks with Gemini/Groq LLM calls using prompts, rate limiting, and disk caching.
"""

import asyncio
import logging
from typing import List, Dict, Any

from app.llm.gemini import GeminiProvider
from app.llm.groq import GroqProvider
from app.llm.cache import compute_cache_key, get_cached_response, save_cached_response
from app.extract.prompts import (
    PROMPT_VERSION,
    EXTRACTION_SYSTEM_PROMPT,
    PROSE_EXTRACTION_USER_PROMPT,
    TABLE_EXTRACTION_USER_PROMPT,
)
from app.jobs import update_job

logger = logging.getLogger(__name__)

# Initialize providers
gemini_provider = GeminiProvider()
groq_provider = GroqProvider()


def extract_facts(doc_id: str, job_id: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Synchronous wrapper for async chunk processing."""
    return asyncio.run(_extract_facts_async(doc_id, job_id, chunks))


async def _extract_facts_async(doc_id: str, job_id: str, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extract raw facts from chunks using LLM calls or disk cache."""
    raw_facts = []
    total_chunks = len(chunks)

    for idx, chunk in enumerate(chunks):
        chunk_text = chunk["text"]
        is_table = chunk.get("is_table", False)

        # Compute cache key
        cache_key = compute_cache_key(chunk_text, PROMPT_VERSION)
        cached = get_cached_response(cache_key)

        if cached is not None:
            extracted_list = cached
        else:
            # Prepare prompt
            user_prompt = (
                TABLE_EXTRACTION_USER_PROMPT.format(chunk_text=chunk_text)
                if is_table
                else PROSE_EXTRACTION_USER_PROMPT.format(chunk_text=chunk_text)
            )

            try:
                # Primary attempt: Gemini
                extracted_list = await gemini_provider.generate_json(
                    prompt=user_prompt,
                    system_instruction=EXTRACTION_SYSTEM_PROMPT,
                    temperature=0.1,
                )
                save_cached_response(cache_key, PROMPT_VERSION, extracted_list, model="gemini-3.6-flash")
            except Exception as e:
                logger.warning(f"Gemini call failed for chunk {chunk['chunk_id']}: {e}. Trying Groq fallback.")
                try:
                    extracted_list = await groq_provider.generate_json(
                        prompt=user_prompt,
                        system_instruction=EXTRACTION_SYSTEM_PROMPT,
                        temperature=0.1,
                    )
                    save_cached_response(cache_key, PROMPT_VERSION, extracted_list, model="groq-openai-gpt-oss-20b")
                except Exception as fallback_err:
                    logger.error(f"Groq fallback failed as well: {fallback_err}")
                    extracted_list = []

        if isinstance(extracted_list, list):
            for raw_fact in extracted_list:
                if isinstance(raw_fact, dict):
                    raw_fact["chunk_id"] = chunk["chunk_id"]
                    raw_fact["doc_id"] = doc_id
                    raw_fact["chunk_text"] = chunk_text
                    raw_fact["chunk_page"] = chunk["page"]
                    raw_facts.append(raw_fact)

        # Update job progress after each chunk
        update_job(
            job_id,
            chunks_done=idx + 1,
            progress=0.2 + (0.3 * (idx + 1) / max(total_chunks, 1)),
        )

    return raw_facts

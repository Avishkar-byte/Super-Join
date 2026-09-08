"""Google Gemini LLM Provider (Primary)."""

import json
import logging
from typing import List, Dict, Any, Optional
import google.generativeai as genai

from app.config import settings
from app.llm.provider import LLMProvider
from app.llm.limiter import execute_with_backoff

logger = logging.getLogger(__name__)


class GeminiProvider(LLMProvider):
    """Gemini API provider using gemini-3.6-flash and text-embedding-004."""

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or settings.gemini_api_key
        if key:
            genai.configure(api_key=key)
        self.model_name = "gemini-3.6-flash"
        self.embed_model_name = "models/text-embedding-004"

    async def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Any:
        """Call Gemini API and return parsed JSON."""

        async def _call():
            model = genai.GenerativeModel(
                model_name=self.model_name,
                system_instruction=system_instruction,
                generation_config={
                    "temperature": temperature,
                    "response_mime_type": "application/json",
                },
            )
            response = model.generate_content(prompt)
            text = response.text.strip()
            # Strip potential markdown fences if present
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            return json.loads(text.strip())

        return await execute_with_backoff(_call)

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Generate embeddings using text-embedding-004."""
        if not texts:
            return []

        async def _call():
            embeddings = []
            # Batch in sets of 20
            batch_size = 20
            for i in range(0, len(texts), batch_size):
                batch = texts[i : i + batch_size]
                res = genai.embed_content(
                    model=self.embed_model_name,
                    content=batch,
                    task_type="retrieval_document",
                )
                embeddings.extend(res["embedding"])
            return embeddings

        return await execute_with_backoff(_call)

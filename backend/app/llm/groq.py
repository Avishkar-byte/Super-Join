"""Groq LLM Provider (Fallback)."""

import json
import logging
from typing import List, Dict, Any, Optional
from groq import Groq

from app.config import settings
from app.llm.provider import LLMProvider
from app.llm.limiter import execute_with_backoff

logger = logging.getLogger(__name__)


class GroqProvider(LLMProvider):
    """Groq API provider for fallback generation."""

    def __init__(self, api_key: Optional[str] = None):
        key = api_key or settings.groq_api_key
        self.client = Groq(api_key=key) if key else None
        self.model_name = "openai/gpt-oss-20b"

    async def generate_json(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Any:
        """Call Groq API with JSON response format."""
        if not self.client:
            raise ValueError("Groq API key not configured")

        async def _call():
            messages = []
            if system_instruction:
                messages.append({"role": "system", "content": system_instruction})
            messages.append({"role": "user", "content": prompt})

            completion = self.client.chat.completions.create(
                model=self.model_name,
                messages=messages,
                temperature=temperature,
                max_completion_tokens=4096,
                # openai/gpt-oss-20b is a reasoning model: on default effort it
                # burns the whole completion budget on hidden reasoning tokens
                # before writing the answer, leaving content empty. This is a
                # plain extraction task, so keep reasoning effort low.
                extra_body={"reasoning_effort": "low"},
            )
            text = completion.choices[0].message.content.strip()
            # response_format=json_object was dropped: it only accepts a top-level
            # JSON object, but extraction prompts ask for a top-level array. Parse
            # leniently instead, stripping markdown fences if the model adds them.
            if text.startswith("```json"):
                text = text[7:]
            if text.startswith("```"):
                text = text[3:]
            if text.endswith("```"):
                text = text[:-3]
            return json.loads(text.strip())

        return await execute_with_backoff(_call)

    async def embed_texts(self, texts: List[str]) -> List[List[float]]:
        """Groq does not provide an embedding endpoint; return zero vectors if called as fallback."""
        return [[0.0] * 768 for _ in texts]

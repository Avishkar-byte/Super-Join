"""LLM Fallback Adjudicator for Reconciliation (Rule 6 Residue)."""

import json
import logging
from typing import Dict, Any, Tuple
from app.llm.gemini import GeminiProvider
from app.llm.groq import GroqProvider
from app.extract.prompts import RELATION_ADJUDICATION_SYSTEM_PROMPT, RELATION_ADJUDICATION_USER_PROMPT

logger = logging.getLogger(__name__)

gemini_provider = GeminiProvider()
groq_provider = GroqProvider()


async def adjudicate_relation_llm(fact_a: dict, fact_b: dict) -> Tuple[str, str, float]:
    """Ask LLM to reconcile relation between two facts.

    Returns: (verdict, reason, confidence)
    """
    ev_a = json.loads(fact_a["evidence"]) if isinstance(fact_a["evidence"], str) else fact_a["evidence"]
    ev_b = json.loads(fact_b["evidence"]) if isinstance(fact_b["evidence"], str) else fact_b["evidence"]

    prompt = RELATION_ADJUDICATION_USER_PROMPT.format(
        subj_a=fact_a["subject_raw"], pred_a=fact_a["predicate_raw"], obj_a=fact_a["object_value"],
        quals_a=fact_a["qualifiers"], quote_a=ev_a.get("quote", ""),
        subj_b=fact_b["subject_raw"], pred_b=fact_b["predicate_raw"], obj_b=fact_b["object_value"],
        quals_b=fact_b["qualifiers"], quote_b=ev_b.get("quote", ""),
    )

    try:
        res = await gemini_provider.generate_json(
            prompt=prompt, system_instruction=RELATION_ADJUDICATION_SYSTEM_PROMPT, temperature=0.1
        )
        return _parse_adjudication(res)
    except Exception as e:
        logger.warning(f"Gemini relation adjudication failed: {e}. Trying Groq fallback.")
        try:
            res = await groq_provider.generate_json(
                prompt=prompt, system_instruction=RELATION_ADJUDICATION_SYSTEM_PROMPT, temperature=0.1
            )
            return _parse_adjudication(res)
        except Exception as fallback_err:
            return "UNRELATED", f"Adjudication fallback exception: {str(fallback_err)}", 0.5


def _parse_adjudication(res: dict) -> Tuple[str, str, float]:
    verdict = res.get("verdict", "UNRELATED")
    reason = res.get("reason", "LLM adjudication result.")
    confidence = float(res.get("confidence", 0.75))
    return verdict, reason, confidence

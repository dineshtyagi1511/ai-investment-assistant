"""
LiteLLM Query Router
Classifies every query into a tier BEFORE calling any LLM.
Rule-based = zero additional cost, ~0.1ms latency.
"""
import re
from enum import Enum
from typing import Any
from litellm import acompletion
from loguru import logger
from app.core.config import settings


class QueryTier(str, Enum):
    SIMPLE   = "simple"    # gpt-4o-mini  — factual lookups
    MODERATE = "moderate"  # gpt-4o-mini  — summaries, news digests
    COMPLEX  = "complex"   # gpt-4o       — comparisons, reasoning, recommendations


MODEL_MAP = {
    QueryTier.SIMPLE:   settings.MODEL_SIMPLE,
    QueryTier.MODERATE: settings.MODEL_SIMPLE,
    QueryTier.COMPLEX:  settings.MODEL_COMPLEX,
}


# 🔥 Signals
COMPLEX_SIGNALS = {
    "compare", "versus", "vs", "recommend", "should i invest",
    "portfolio", "risk-adjusted", "correlation", "forecast",
    "predict", "multi-year", "sector rotation", "macro", "outlook",
    "strategy", "allocation", "better", "which is better",
}

SIMPLE_SIGNALS = {
    "price", "current", "today", "52-week", "market cap",
    "pe ratio", "dividend", "eps", "what is", "define",
    "revenue", "profit", "earnings per share",
}


def classify_query(query: str) -> QueryTier:
    """
    Fast, deterministic classifier.
    """
    q = query.lower()

    # ── Basic features ──────────────────────────────────────────────
    word_count = len(q.split())

    # ✅ Fixed entity detection (NO double counting)
    entities = set()

    # Tickers (TCS, INFY)
    entities.update(re.findall(r'\b[A-Z]{2,6}\b', query))

    # Company names (HDFC Bank, Reliance)
    entities.update(re.findall(r'\b[A-Z][a-z]+(?:\s[A-Z][a-z]+)*\b', query))

    entity_count = len(entities)

    has_comparison = bool(re.search(r'\b(vs|versus|compare|against|better)\b', q))

    # ✅ Fixed timeframe detection
    has_timeframe = bool(
        re.search(r'\b(\d+[\s-]?year|multi[-\s]?year|long[-\s]?term|short[-\s]?term)\b', q)
    )

    complex_hits = sum(1 for kw in COMPLEX_SIGNALS if kw in q)
    simple_hits  = sum(1 for kw in SIMPLE_SIGNALS  if kw in q)

    # ── 🔥 Strong intent override (MOST IMPORTANT) ──────────────────
    if any(k in q for k in [
        "should i invest",
        "is it good to invest",
        "worth investing",
        "long-term investment",
        "short-term investment"
    ]):
        return QueryTier.COMPLEX

    # ── SIMPLE ─────────────────────────────────────────────────────
    if (
        simple_hits >= 1
        and word_count <= 12
        and entity_count <= 2
        and not has_comparison
    ):
        return QueryTier.SIMPLE

    # ── COMPLEX ────────────────────────────────────────────────────
    if complex_hits >= 1 and (has_timeframe or entity_count >= 1 or word_count > 10):
        return QueryTier.COMPLEX

    if has_comparison:
        return QueryTier.COMPLEX

    if word_count > 30 or entity_count >= 3:
        return QueryTier.COMPLEX

    # ── DEFAULT ────────────────────────────────────────────────────
    return QueryTier.MODERATE


async def route_completion(
    messages: list[dict],
    query: str,
    force_json: bool = False,
    **kwargs: Any,
) -> tuple[str, QueryTier]:
    """
    Classify → pick model → call via LiteLLM → return (text, tier)
    """
    tier  = classify_query(query)
    model = MODEL_MAP[tier]

    logger.info(
        f"[router] tier={tier.value:<8} model={model:<15} "
        f"words={len(query.split()):<4} query={query[:60]!r}"
    )

    if force_json:
        kwargs.setdefault("response_format", {"type": "json_object"})

    response = await acompletion(
        model=model,
        messages=messages,
        **kwargs,
    )

    text = response.choices[0].message.content

    # Token logging
    input_tokens  = response.usage.prompt_tokens
    output_tokens = response.usage.completion_tokens

    logger.info(
        f"[router] tokens in={input_tokens} out={output_tokens} tier={tier.value}"
    )

    return text, tier
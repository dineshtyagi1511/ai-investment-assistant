"""
Multi-Agent Debate System
Bull Agent  → argues the positive investment case
Bear Agent  → argues the risks and downsides
Synthesizer → weighs both sides and produces a balanced final view

This pattern produces more balanced analysis than a single prompt
and is genuinely memorable in interviews/demos.
"""
import json
from loguru import logger
from app.services.llm_router import route_completion, QueryTier
from app.services.data_ingestion import FinancialDataService
from app.schemas.analysis import ComparisonAnalysis


BULL_SYSTEM = """You are an optimistic equity analyst (Bull).
Your job: make the STRONGEST possible positive case for this stock/comparison.
Focus on: growth potential, competitive moat, improving fundamentals, tailwinds.
Be specific, cite data. Max 150 words.
Output plain text — no JSON."""

BEAR_SYSTEM = """You are a skeptical risk analyst (Bear).
Your job: make the STRONGEST possible negative/risk case for this stock/comparison.
Focus on: valuation concerns, competition, macro risks, weak financials, red flags.
Be specific, cite data. Max 150 words.
Output plain text — no JSON."""

SYNTH_SYSTEM = """You are a neutral chief investment officer.
You have read both the bull and bear case for a stock or comparison.
Produce a BALANCED final synthesis:
- Acknowledge the strongest points from each side
- State which thesis you find more credible and WHY
- Identify the ONE key risk investors must watch
Respond ONLY with a valid JSON object with these keys:
  synthesis (string, 3-4 sentences)
  winner (ticker string, or null if inconclusive)
  confidence_score (float 0-1)
  risk_levels (object: {ticker: "Low|Medium|High|Extreme"})
No markdown, no preamble."""


class MultiAgentDebate:
    def __init__(self):
        self.data_service = FinancialDataService()

    async def _run_agent(
        self, system: str, user_content: str, query: str
    ) -> str:
        messages = [
            {"role": "system",  "content": system},
            {"role": "user",    "content": user_content},
        ]
        text, _ = await route_completion(
            messages=messages,
            query=query,
            temperature=0.4,
            max_tokens=300,
        )
        return text.strip()

    async def compare(
        self, tickers: list[str], user_query: str
    ) -> ComparisonAnalysis:
        """
        Run the full 3-agent debate for a list of tickers.
        Returns a validated ComparisonAnalysis.
        """
        tickers = [t.upper() for t in tickers]
        logger.info(f"[debate] starting for {tickers}")

        # Fetch data for all tickers
        all_data = {}
        for t in tickers:
            all_data[t] = await self.data_service.get_stock_data(t)

        data_summary = json.dumps(all_data, indent=2, default=str)
        ticker_str   = " vs ".join(tickers)

        # Bull pass
        logger.info("[debate] bull agent running...")
        bull_case = await self._run_agent(
            BULL_SYSTEM,
            f"Tickers: {ticker_str}\n\nData:\n{data_summary}\n\nUser question: {user_query}",
            user_query,
        )

        # Bear pass
        logger.info("[debate] bear agent running...")
        bear_case = await self._run_agent(
            BEAR_SYSTEM,
            f"Tickers: {ticker_str}\n\nData:\n{data_summary}\n\nUser question: {user_query}",
            user_query,
        )

        # Synthesizer (always uses gpt-4o for final reasoning)
        logger.info("[debate] synthesizer running...")
        synth_content = f"""Tickers being debated: {ticker_str}

BULL CASE:
{bull_case}

BEAR CASE:
{bear_case}

Financial data:
{data_summary}

Produce your synthesis JSON now."""

        synth_messages = [
            {"role": "system", "content": SYNTH_SYSTEM},
            {"role": "user",   "content": synth_content},
        ]
        raw_synth, _ = await route_completion(
            messages=synth_messages,
            query=f"complex comparison {ticker_str}",   # forces gpt-4o tier
            force_json=True,
            temperature=0.2,
            max_tokens=400,
        )

        synth_data = json.loads(raw_synth)
        logger.info(f"[debate] synthesizer winner={synth_data.get('winner')}")

        return ComparisonAnalysis(
            tickers=tickers,
            bull_case=bull_case,
            bear_case=bear_case,
            synthesis=synth_data.get("synthesis", ""),
            winner=synth_data.get("winner"),
            confidence_score=float(synth_data.get("confidence_score", 0.5)),
            risk_levels=synth_data.get("risk_levels", {}),
        )
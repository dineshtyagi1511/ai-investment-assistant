"""
Main Analyst Agent
Orchestrates the full pipeline:
  Cache check → Data fetch → RAG retrieval → LLM → Guardrails → Cache store
"""
import json
from loguru import logger
from app.services.llm_router import route_completion
from app.services.data_ingestion import FinancialDataService
from app.services.rag_engine import RAGEngine
from app.services.cache import SemanticCache
from app.core.guardrails import apply_guardrails, compute_confidence
from app.schemas.analysis import StockAnalysis
from app.db.mongo import save_analysis, log_agent_call


SYSTEM_PROMPT = """You are a senior investment analyst AI.
Your job is to produce structured, factual financial analysis.

RULES:
1. Use ONLY the provided data and context — never fabricate metrics.
2. If a metric is missing, explicitly say "data unavailable".
3. Never give specific buy/sell prices or "guaranteed returns".
4. Cite your sources in recommendation_logic using [Source: X] notation.
5. Be concise: summary ≤ 3 sentences, recommendation_logic ≤ 5 sentences.
6. Respond ONLY with a valid JSON object — no markdown, no preamble.
"""


class AnalystAgent:
    def __init__(self):
        self.data_service = FinancialDataService()
        self.rag          = RAGEngine()
        self.cache        = SemanticCache()

    async def analyze(self, ticker: str, user_query: str) -> StockAnalysis:
        """
        Full analysis pipeline for a single ticker.
        Returns a validated StockAnalysis Pydantic object.
        """
        ticker = ticker.upper().strip()

        # 1. Semantic cache check
        cache_result = await self.cache.get(user_query)
        if cache_result and cache_result.get("ticker") == ticker:
            logger.info(f"[analyst] cache hit for {ticker}")
            return StockAnalysis(**cache_result)

        # 2. Fetch structured financial data
        stock_data = await self.data_service.get_stock_data(ticker)
        news       = await self.data_service.get_news(
            stock_data.get("company_name", ticker), ticker
        )

        # 3. Index news into vector store + RAG retrieval
        if news:
            self.rag.index([
                {
                    "text": f"{a['title']}. {a.get('description', '')}",
                    "metadata": {
                        "source": a.get("source", "news"),
                        "url":    a.get("url", ""),
                        "ticker": ticker,
                        "type":   "news",
                    },
                }
                for a in news
            ])

        rag_context = await self.rag.retrieve(user_query, use_hyde=True)

        # 4. Build LLM prompt
        confidence = compute_confidence(stock_data, news)
        schema     = StockAnalysis.model_json_schema()

        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"""Analyze {ticker} ({stock_data.get('company_name', ticker)}).

=== STRUCTURED FINANCIAL DATA ===
{json.dumps(stock_data, indent=2, default=str)}

=== RAG CONTEXT (news & reports) ===
{rag_context or 'No additional context retrieved.'}

=== USER QUESTION ===
{user_query}

=== OUTPUT SCHEMA ===
{json.dumps(schema, indent=2)}

Return a JSON object with EXACTLY these fields:
- ticker (string)
- company_name (string)
- summary (string, ≤3 sentences)
- metrics (list of {{label, value, unit, trend}})
- top_news (list of {{title, source, sentiment_score, url, published_at}})
- risk_level (one of: Low, Medium, High, Extreme)
- confidence_score ({confidence})
- recommendation_logic (string with [Source: X] citations)
- data_sources (list of strings)
""",
            },
        ]

        # 5. Call LLM via router
        raw, tier = await route_completion(
            messages=messages,
            query=user_query,
            force_json=True,
            temperature=0.1,
            max_tokens=1500,
        )

        # 6. Parse + validate with Pydantic
        try:
            data = json.loads(raw)
            data["model_tier"]       = tier.value
            data["confidence_score"] = confidence   # always use computed score
            analysis = StockAnalysis(**data)
        except Exception as e:
            logger.error(f"[analyst] Pydantic validation failed: {e}\nraw={raw[:400]}")
            raise ValueError(f"AI output failed schema validation: {e}")

        # 7. Apply guardrails
        safe_logic, warnings = apply_guardrails(
            analysis.recommendation_logic, add_disclaimer=False
        )
        analysis.recommendation_logic = safe_logic

        if warnings:
            logger.warning(f"[analyst] guardrails triggered: {warnings}")

        # 8. Persist + cache
        result_dict = analysis.model_dump(mode="json")
        await save_analysis(result_dict)
        await self.cache.set(user_query, result_dict, tier=tier.value)
        await log_agent_call({
            "ticker":   ticker,
            "query":    user_query,
            "tier":     tier.value,
            "warnings": warnings,
        })

        return analysis
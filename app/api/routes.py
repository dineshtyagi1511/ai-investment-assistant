"""
FastAPI route definitions.
All endpoints are async and stream-compatible.
"""
from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional
from loguru import logger

from app.agents.analyst import AnalystAgent
from app.agents.debate import MultiAgentDebate
from app.services.data_ingestion import FinancialDataService
from app.core.guardrails import DISCLAIMER
from app.schemas.analysis import StockAnalysis, ComparisonAnalysis, NewsDigest


router   = APIRouter()
_analyst = AnalystAgent()
_debate  = MultiAgentDebate()
_data    = FinancialDataService()


# ── Request models ─────────────────────────────────────────────────────────────
class AnalyzeRequest(BaseModel):
    ticker: str
    query:  str = "Give me a full investment analysis"


class CompareRequest(BaseModel):
    tickers: list[str]
    query:   str = "Compare these stocks"


class IndexRequest(BaseModel):
    text:     str
    source:   str
    ticker:   Optional[str] = None
    doc_type: str = "report"


# ── Endpoints ─────────────────────────────────────────────────────────────────
@router.get("/health")
async def health():
    return {"status": "ok", "service": "AIRA"}


@router.post("/analyze", response_model=StockAnalysis)
async def analyze_stock(req: AnalyzeRequest):
    """
    Full single-stock analysis.
    Checks cache → fetches data → RAG retrieval → LLM → guardrails.
    """
    try:
        analysis = await _analyst.analyze(req.ticker, req.query)
        return analysis
    except ValueError as e:
        raise HTTPException(status_code=422, detail=str(e))
    except Exception as e:
        logger.error(f"[api] /analyze error: {e}")
        raise HTTPException(status_code=500, detail="Analysis failed. Please retry.")


@router.post("/compare", response_model=ComparisonAnalysis)
async def compare_stocks(req: CompareRequest):
    """
    Multi-agent Bull vs Bear debate for 2+ tickers.
    Always uses the complex model tier.
    """
    if len(req.tickers) < 2:
        raise HTTPException(status_code=400, detail="Provide at least 2 tickers to compare.")
    if len(req.tickers) > 4:
        raise HTTPException(status_code=400, detail="Maximum 4 tickers per comparison.")

    try:
        result = await _debate.compare(req.tickers, req.query)
        return result
    except Exception as e:
        logger.error(f"[api] /compare error: {e}")
        raise HTTPException(status_code=500, detail="Comparison failed. Please retry.")


@router.get("/quote/{ticker}")
async def get_quote(ticker: str):
    """Fast real-time quote — no LLM, just API data."""
    data = await _data.get_stock_data(ticker.upper())
    if "error" in data:
        raise HTTPException(status_code=404, detail=f"No data found for {ticker}")
    return data


@router.get("/news")
async def get_market_news(limit: int = Query(default=10, le=20)):
    """General market news digest."""
    articles = await _data.get_market_news()
    return {"count": len(articles[:limit]), "articles": articles[:limit]}


@router.get("/news/{ticker}")
async def get_stock_news(ticker: str, limit: int = Query(default=5, le=10)):
    """News specific to a ticker."""
    data     = await _data.get_stock_data(ticker.upper())
    company  = data.get("company_name", ticker)
    articles = await _data.get_news(company, ticker.upper())
    return {
        "ticker":   ticker.upper(),
        "company":  company,
        "count":    len(articles[:limit]),
        "articles": articles[:limit],
    }


@router.post("/index")
async def index_document(req: IndexRequest):
    """
    Index a document chunk into the vector store.
    Use this to add annual reports, earnings calls, etc.
    """
    n = _analyst.rag.index([{
        "text": req.text,
        "metadata": {
            "source":   req.source,
            "ticker":   req.ticker or "general",
            "doc_type": req.doc_type,
        },
    }])
    return {"indexed_chunks": n, "source": req.source}


@router.get("/disclaimer")
async def get_disclaimer():
    return {"disclaimer": DISCLAIMER.strip()}
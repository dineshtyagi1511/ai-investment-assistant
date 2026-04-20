"""
AIRA Test Suite
Run with: pytest tests/ -v
"""
import pytest
from datetime import datetime


# ── Schema tests ──────────────────────────────────────────────────────────────
class TestSchemas:
    def test_stock_analysis_valid(self):
        from app.schemas.analysis import StockAnalysis
        data = {
            "ticker":       "RELIANCE",
            "company_name": "Reliance Industries Limited",
            "summary":      "Strong growth in digital segment with stable O2C business.",
            "metrics": [
                {"label": "P/E Ratio", "value": 25.4, "unit": "x",  "trend": "Stable"},
                {"label": "Revenue",   "value": 8900, "unit": "INR Cr", "trend": "Upward"},
            ],
            "top_news": [
                {
                    "title":           "Reliance Jio expands 5G coverage",
                    "source":          "Economic Times",
                    "sentiment_score": 0.7,
                    "url":             "https://example.com",
                }
            ],
            "risk_level":            "Medium",
            "confidence_score":      0.82,
            "recommendation_logic":  "Strong digital growth [Source: Q3 Report]. Stable O2C cash flows.",
            "data_sources":          ["alpha_vantage", "news_api"],
        }
        analysis = StockAnalysis(**data)
        assert analysis.ticker == "RELIANCE"
        assert analysis.risk_level == "Medium"
        assert 0 <= analysis.confidence_score <= 1

    def test_ticker_uppercased(self):
        from app.schemas.analysis import StockAnalysis
        data = {
            "ticker": "reliance", "company_name": "Reliance",
            "summary": "Test.", "metrics": [], "top_news": [],
            "risk_level": "Low", "confidence_score": 0.5,
            "recommendation_logic": "Test.", "data_sources": [],
        }
        a = StockAnalysis(**data)
        assert a.ticker == "RELIANCE"

    def test_invalid_risk_level(self):
        from app.schemas.analysis import StockAnalysis
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            StockAnalysis(
                ticker="TCS", company_name="TCS",
                summary="Test.", metrics=[], top_news=[],
                risk_level="VERY_HIGH",   # invalid
                confidence_score=0.5,
                recommendation_logic="Test.", data_sources=[],
            )

    def test_sentiment_score_bounds(self):
        from app.schemas.analysis import NewsReference
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            NewsReference(
                title="Test", source="Test",
                sentiment_score=1.5,   # out of range
            )

    def test_metric_trend_validation(self):
        from app.schemas.analysis import FinancialMetric
        from pydantic import ValidationError
        with pytest.raises(ValidationError):
            FinancialMetric(label="P/E", value=20.0, trend="Sideways")  # invalid trend


# ── Router tests ──────────────────────────────────────────────────────────────
class TestQueryRouter:
    def test_simple_classification(self):
        from app.services.llm_router import classify_query, QueryTier
        assert classify_query("What is Reliance current price?") == QueryTier.SIMPLE
        assert classify_query("What is PE ratio?")               == QueryTier.SIMPLE

    def test_complex_classification(self):
        from app.services.llm_router import classify_query, QueryTier
        assert classify_query("Compare TCS vs Infosys risk-adjusted returns") == QueryTier.COMPLEX
        assert classify_query("Should I invest in HDFC Bank long-term?")      == QueryTier.COMPLEX
        assert classify_query("Forecast RELIANCE stock for next 2 years")     == QueryTier.COMPLEX

    def test_moderate_fallthrough(self):
        from app.services.llm_router import classify_query, QueryTier
        assert classify_query("Summarize recent news for Infosys") == QueryTier.MODERATE

    def test_model_map(self):
        from app.services.llm_router import MODEL_MAP, QueryTier
        from app.core.config import settings
        assert MODEL_MAP[QueryTier.SIMPLE]   == settings.MODEL_SIMPLE
        assert MODEL_MAP[QueryTier.COMPLEX]  == settings.MODEL_COMPLEX


# ── Guardrails tests ──────────────────────────────────────────────────────────
class TestGuardrails:
    def test_buy_advice_blocked(self):
        from app.core.guardrails import apply_guardrails
        text = "You should buy at ₹2500 when the stock dips."
        safe, warnings = apply_guardrails(text, add_disclaimer=False)
        assert "buy at" not in safe.lower() or "[specific financial advice removed]" in safe
        assert len(warnings) > 0

    def test_pii_redacted(self):
        from app.core.guardrails import redact_pii
        text  = "Contact investor ABCDE1234F at 9876543210."
        clean = redact_pii(text)
        assert "9876543210"  not in clean
        assert "ABCDE1234F"  not in clean

    def test_disclaimer_added(self):
        from app.core.guardrails import apply_guardrails, DISCLAIMER
        text, _ = apply_guardrails("Normal analysis text.", add_disclaimer=True)
        assert "Disclaimer" in text

    def test_clean_text_unchanged(self):
        from app.core.guardrails import apply_guardrails
        clean = "Revenue grew 12% due to strong digital segment performance."
        result, warnings = apply_guardrails(clean, add_disclaimer=False)
        assert len(warnings) == 0


# ── Confidence score tests ────────────────────────────────────────────────────
class TestConfidence:
    def test_full_data_high_confidence(self):
        from app.core.guardrails import compute_confidence
        data = {"price": 2500.0, "company_name": "Reliance Industries"}
        news = [{"title": f"News {i}"} for i in range(5)]
        score = compute_confidence(data, news)
        assert score >= 0.8

    def test_empty_data_low_confidence(self):
        from app.core.guardrails import compute_confidence
        score = compute_confidence({}, [])
        assert score < 0.3


# ── Chunker tests ─────────────────────────────────────────────────────────────
class TestRAGChunker:
    def test_chunks_created(self):
        from app.services.rag_engine import _chunk_text
        text   = " ".join([f"word{i}" for i in range(200)])
        chunks = _chunk_text(text, size=50, overlap=10)
        assert len(chunks) >= 3

    def test_tiny_chunks_dropped(self):
        from app.services.rag_engine import _chunk_text
        text   = "Short text that is not long enough."
        chunks = _chunk_text(text, size=50, overlap=10)
        # Should drop chunks with fewer than 10 words
        for c in chunks:
            assert len(c.split()) >= 10 or len(chunks) == 0
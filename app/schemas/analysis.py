from pydantic import BaseModel, Field, field_validator

from datetime import datetime
import loguru

from typing import List, Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

class FinancialMetric(BaseModel):
    label: str = Field(..., description="Metric name, e.g. P/E Ratio, Revenue")
    value: float
    unit: str = Field(default="", description="e.g. INR, USD, %, x")
    trend: Optional[str] = Field(None, description="Upward | Downward | Stable")

    @field_validator("trend")
    @classmethod
    def validate_trend(cls, v):
        if v is not None and v not in ("Upward", "Downward", "Stable"):
            raise ValueError("trend must be Upward, Downward, or Stable")
        return v


class NewsReference(BaseModel):
    title: str
    source: str
    sentiment_score: float = Field(
        ..., ge=-1, le=1,
        description="-1 = very bearish, 0 = neutral, 1 = very bullish"
    )
    url: Optional[str] = None
    published_at: Optional[str] = None

    @field_validator("sentiment_score")
    @classmethod
    def round_sentiment(cls, v):
        return round(v, 3)


class StockAnalysis(BaseModel):
    ticker: str
    company_name: str
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    summary: str = Field(..., description="Executive overview, max 3 sentences")
    metrics: List[FinancialMetric] = Field(default_factory=list)
    top_news: List[NewsReference] = Field(default_factory=list)
    risk_level: Literal["Low", "Medium", "High", "Extreme"] = Field(
        ..., description="Low | Medium | High | Extreme"
    )
    confidence_score: float = Field(
        ..., ge=0, le=1,
        description="AI confidence in analysis based on data coverage"
    )
    recommendation_logic: str = Field(
        ..., description="Explainable reasoning with source citations"
    )
    data_sources: List[str] = Field(
        default_factory=list,
        description="Sources used: API, VectorDB, WebSearch"
    )
    model_tier: Optional[str] = None  # simple | moderate | complex — set by router

    # --- Validators ---

    @field_validator("ticker", mode="before")
    @classmethod
    def uppercase_ticker(cls, v: str) -> str:
        return v.upper().strip()

    @field_validator("risk_level", mode="before")
    @classmethod
    def coerce_risk_level(cls, v: str) -> str:
        allowed = {"Low", "Medium", "High", "Extreme"}
        if v not in allowed:
            logger.warning(
                "[analyst] Invalid risk_level from LLM: %r — defaulting to 'Medium'", v
            )
            return "Medium"
        return v

    @field_validator("confidence_score", mode="before")
    @classmethod
    def clamp_confidence(cls, v: float) -> float:
        # LLM sometimes returns values slightly out of range e.g. 1.02
        return max(0.0, min(1.0, float(v)))

    @model_validator(mode="after")
    def low_confidence_when_no_data(self) -> "StockAnalysis":
        # If LLM had no real data, cap confidence and flag it
        has_metrics = bool(self.metrics)
        has_news = bool(self.top_news)
        if not has_metrics and not has_news and self.confidence_score > 0.4:
            logger.warning(
                "[analyst] No metrics or news for %s but confidence=%.2f — clamping to 0.3",
                self.ticker, self.confidence_score
            )
            self.confidence_score = 0.3
        return self

    # --- Convenience ---

    @property
    def is_low_confidence(self) -> bool:
        return self.confidence_score < 0.4

    @property
    def has_sufficient_data(self) -> bool:
        return bool(self.metrics) or bool(self.top_news)


class ComparisonAnalysis(BaseModel):
    """Used by the Bull vs Bear multi-agent debate."""
    tickers: List[str]
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    bull_case: str = Field(..., description="Positive investment case")
    bear_case: str = Field(..., description="Negative / risk case")
    synthesis: str = Field(..., description="Balanced final recommendation logic")
    winner: Optional[str] = Field(
        None,
        description="Ticker the synthesizer favours, or None if inconclusive"
    )
    confidence_score: float = Field(..., ge=0, le=1)
    risk_levels: dict = Field(default_factory=dict)  # {ticker: risk_level}


class NewsDigest(BaseModel):
    """Summarised daily news digest."""
    date: str
    headline_count: int
    top_stories: List[NewsReference]
    market_sentiment: str = Field(
        ..., description="Bullish | Bearish | Neutral | Mixed"
    )
    sector_impacts: dict = Field(
        default_factory=dict,
        description="{'Technology': 'Positive', 'Banking': 'Negative'}"
    )
    summary: str
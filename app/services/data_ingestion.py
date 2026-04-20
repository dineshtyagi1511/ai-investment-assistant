"""
Financial data ingestion.
Fetches structured stock data from Alpha Vantage (primary) with Yahoo Finance fallback.
Includes retry logic with exponential backoff.
"""
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from loguru import logger
from app.core.config import settings


# ── Retry decorator ──────────────────────────────────────────────────────────
def _is_retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code in {429, 500, 502, 503}
    return isinstance(exc, (httpx.ConnectError, httpx.TimeoutException))


retry_policy = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=10),
    retry=retry_if_exception_type((httpx.HTTPStatusError, httpx.ConnectError, httpx.TimeoutException)),
    reraise=True,
)


# ── Alpha Vantage ─────────────────────────────────────────────────────────────
class AlphaVantageClient:
    BASE_URL = "https://www.alphavantage.co/query"

    def __init__(self):
        self.api_key = settings.ALPHA_VANTAGE_API_KEY

    @retry_policy
    async def get_quote(self, ticker: str) -> dict:
        """Fetch real-time global quote for a ticker."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self.BASE_URL, params={
                "function": "GLOBAL_QUOTE",
                "symbol": ticker,
                "apikey": self.api_key,
            })
            resp.raise_for_status()
            data = resp.json()

        quote = data.get("Global Quote", {})
        if not quote:
            logger.warning(f"[alpha_vantage] empty quote for {ticker}")
            return {}

        return {
            "ticker":       ticker.upper(),
            "price":        float(quote.get("05. price", 0)),
            "change_pct":   float(quote.get("10. change percent", "0").strip("%")),
            "volume":       int(quote.get("06. volume", 0)),
            "high_52w":     float(quote.get("03. high", 0)),
            "low_52w":      float(quote.get("04. low", 0)),
            "prev_close":   float(quote.get("08. previous close", 0)),
            "source":       "alpha_vantage",
        }

    @retry_policy
    async def get_overview(self, ticker: str) -> dict:
        """Fetch company overview (PE, EPS, market cap, sector, etc.)."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self.BASE_URL, params={
                "function": "OVERVIEW",
                "symbol": ticker,
                "apikey": self.api_key,
            })
            resp.raise_for_status()
            data = resp.json()

        if "Symbol" not in data:
            logger.warning(f"[alpha_vantage] no overview for {ticker}")
            return {}

        def safe_float(val):
            try:
                return float(val)
            except (ValueError, TypeError):
                return None

        return {
            "ticker":       data.get("Symbol", ticker),
            "company_name": data.get("Name", ""),
            "sector":       data.get("Sector", ""),
            "industry":     data.get("Industry", ""),
            "pe_ratio":     safe_float(data.get("PERatio")),
            "eps":          safe_float(data.get("EPS")),
            "market_cap":   safe_float(data.get("MarketCapitalization")),
            "dividend_yield": safe_float(data.get("DividendYield")),
            "52w_high":     safe_float(data.get("52WeekHigh")),
            "52w_low":      safe_float(data.get("52WeekLow")),
            "beta":         safe_float(data.get("Beta")),
            "description":  data.get("Description", ""),
            "source":       "alpha_vantage",
        }


# ── News API ──────────────────────────────────────────────────────────────────
class NewsAPIClient:
    BASE_URL = "https://newsapi.org/v2/everything"

    def __init__(self):
        self.api_key = settings.NEWS_API_KEY

    @retry_policy
    async def get_company_news(self, company_name: str, ticker: str, page_size: int = 10) -> list[dict]:
        """Fetch recent news articles for a company."""
        query = f'"{company_name}" OR "{ticker}" stock'
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self.BASE_URL, params={
                "q":        query,
                "apiKey":   self.api_key,
                "pageSize": page_size,
                "sortBy":   "publishedAt",
                "language": "en",
            })
            resp.raise_for_status()
            data = resp.json()

        articles = data.get("articles", [])
        logger.info(f"[news_api] fetched {len(articles)} articles for {ticker}")

        return [
            {
                "title":        a.get("title", ""),
                "description":  a.get("description", ""),
                "source":       a.get("source", {}).get("name", ""),
                "url":          a.get("url", ""),
                "published_at": a.get("publishedAt", ""),
                "content":      (a.get("content") or "")[:500],  # cap for embeddings
            }
            for a in articles
            if a.get("title") and "[Removed]" not in a.get("title", "")
        ]

    @retry_policy
    async def get_market_news(self, page_size: int = 20) -> list[dict]:
        """Fetch general financial market headlines."""
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.get(self.BASE_URL, params={
                "q":        "stock market finance investing",
                "apiKey":   self.api_key,
                "pageSize": page_size,
                "sortBy":   "publishedAt",
                "language": "en",
            })
            resp.raise_for_status()
            data = resp.json()

        return [
            {
                "title":        a.get("title", ""),
                "source":       a.get("source", {}).get("name", ""),
                "url":          a.get("url", ""),
                "published_at": a.get("publishedAt", ""),
            }
            for a in data.get("articles", [])
            if a.get("title") and "[Removed]" not in a.get("title", "")
        ]


# ── Unified fetcher ───────────────────────────────────────────────────────────
class FinancialDataService:
    """
    Single interface used by the rest of the app.
    Combines Alpha Vantage quote + overview into one enriched dict.
    """
    def __init__(self):
        self.av   = AlphaVantageClient()
        self.news = NewsAPIClient()

    async def get_stock_data(self, ticker: str) -> dict:
        """Returns combined quote + overview data for a ticker."""
        try:
            quote    = await self.av.get_quote(ticker)
            overview = await self.av.get_overview(ticker)
        except Exception as e:
            logger.error(f"[financial_service] failed for {ticker}: {e}")
            return {"ticker": ticker, "error": str(e)}

        return {**overview, **quote}   # quote values win on key collision

    async def get_news(self, company_name: str, ticker: str) -> list[dict]:
        try:
            return await self.news.get_company_news(company_name, ticker)
        except Exception as e:
            logger.error(f"[financial_service] news fetch failed for {ticker}: {e}")
            return []

    async def get_market_news(self) -> list[dict]:
        try:
            return await self.news.get_market_news()
        except Exception as e:
            logger.error(f"[financial_service] market news failed: {e}")
            return []
"""
MongoDB connector (async via Motor).
Collections:
  - stocks      : raw stock data cache (TTL 1h)
  - news        : raw news cache (TTL 6h)
  - analysis    : full StockAnalysis results (TTL 1h)
  - agent_logs  : agent call traces for debugging
"""
from datetime import datetime, timedelta
from loguru import logger
from app.core.config import settings

try:
    import motor.motor_asyncio
    MOTOR_AVAILABLE = True
except ImportError:
    MOTOR_AVAILABLE = False
    logger.warning("[db] motor not installed — MongoDB persistence disabled")


class MongoDB:
    _client = None
    _db     = None

    @classmethod
    async def connect(cls):
        if not MOTOR_AVAILABLE:
            return
        try:
            cls._client = motor.motor_asyncio.AsyncIOMotorClient(settings.MONGO_URI)
            cls._db     = cls._client[settings.MONGO_DB_NAME]
            await cls._ensure_indexes()
            logger.info(f"[db] MongoDB connected to '{settings.MONGO_DB_NAME}'")
        except Exception as e:
            logger.error(f"[db] MongoDB connection failed: {e}")

    @classmethod
    async def _ensure_indexes(cls):
        """Create TTL and search indexes on first connect."""
        if cls._db is None:
            return

        # TTL indexes — documents auto-delete after expiry
        await cls._db.stocks.create_index(
            "fetched_at", expireAfterSeconds=3600
        )
        await cls._db.news.create_index(
            "fetched_at", expireAfterSeconds=21600   # 6h
        )
        await cls._db.analysis.create_index(
            "timestamp", expireAfterSeconds=3600
        )
        # Search indexes
        await cls._db.stocks.create_index("ticker")
        await cls._db.analysis.create_index([("ticker", 1), ("timestamp", -1)])
        logger.info("[db] MongoDB indexes ensured")

    @classmethod
    async def disconnect(cls):
        if cls._client:
            cls._client.close()

    @classmethod
    def get_db(cls):
        return cls._db


async def get_db():
    return MongoDB.get_db()


# ── Convenience helpers ───────────────────────────────────────────────────────

async def save_stock_data(ticker: str, data: dict) -> None:
    db = MongoDB.get_db()
    if db is None:
        return
    data["ticker"]     = ticker.upper()
    data["fetched_at"] = datetime.utcnow()
    await db.stocks.update_one(
        {"ticker": ticker.upper()},
        {"$set": data},
        upsert=True,
    )


async def get_cached_stock(ticker: str) -> dict | None:
    db = MongoDB.get_db()
    if db is None:
        return None
    return await db.stocks.find_one(
        {"ticker": ticker.upper()},
        {"_id": 0},
    )


async def save_analysis(analysis_dict: dict) -> None:
    db = MongoDB.get_db()
    if db is None:
        return
    await db.analysis.insert_one({**analysis_dict})  


async def get_recent_analysis(ticker: str) -> dict | None:
    db = MongoDB.get_db()
    if db is None:
        return None
    return await db.analysis.find_one(
        {"ticker": ticker.upper()},
        sort=[("timestamp", -1)],
        projection={"_id": 0},
    )


async def log_agent_call(entry: dict) -> None:
    db = MongoDB.get_db()
    if db is None:
        return
    await db.agent_logs.insert_one({**entry, "logged_at": datetime.utcnow()})
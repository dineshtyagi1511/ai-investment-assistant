"""
Semantic Cache
Embeds every query and stores result in Redis.
On a new query: if cosine similarity > threshold, return cached result.
Skips the LLM entirely — the biggest cost saver.
"""
import json
import hashlib
import numpy as np
from loguru import logger
from app.core.config import settings

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False
    logger.warning("[cache] redis not installed — caching disabled")

try:
    from sentence_transformers import SentenceTransformer
    _embedder = SentenceTransformer("all-MiniLM-L6-v2")
    EMBED_AVAILABLE = True
except ImportError:
    _embedder = None
    EMBED_AVAILABLE = False
    logger.warning("[cache] sentence-transformers not installed — semantic cache disabled")


def _embed(text: str) -> list[float]:
    if not EMBED_AVAILABLE:
        return []
    vec = _embedder.encode(text, normalize_embeddings=True)
    return vec.tolist()


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b:
        return 0.0
    va, vb = np.array(a), np.array(b)
    denom = np.linalg.norm(va) * np.linalg.norm(vb)
    return float(np.dot(va, vb) / denom) if denom else 0.0


class SemanticCache:
    """
    Redis-backed semantic cache.
    Key format:  aira:cache:<md5_of_query>
    Value:       JSON blob {query, embedding, result, tier}
    Index key:   aira:cache:index  — SET of all cache keys for similarity scan
    """

    PREFIX = "aira:cache:"
    INDEX_KEY = "aira:cache:index"

    def __init__(self):
        self._redis = None
        self._threshold = settings.CACHE_SIMILARITY_THRESHOLD
        self._ttl = settings.CACHE_TTL_SECONDS

    async def _get_redis(self):
        if self._redis is None and REDIS_AVAILABLE:
            try:
                self._redis = aioredis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                )
                await self._redis.ping()
                logger.info("[cache] Redis connected")
            except Exception as e:
                logger.warning(f"[cache] Redis unavailable: {e}")
                self._redis = None
        return self._redis

    async def get(self, query: str) -> dict | None:
        """
        Returns cached result if a semantically similar query exists.
        Returns None on cache miss.
        """
        r = await self._get_redis()
        if not r or not EMBED_AVAILABLE:
            return None

        query_vec = _embed(query)
        index_keys = await r.smembers(self.INDEX_KEY)

        best_score, best_entry = 0.0, None
        for key in index_keys:
            raw = await r.get(key)
            if not raw:
                continue
            try:
                entry = json.loads(raw)
                sim   = _cosine_similarity(query_vec, entry["embedding"])
                if sim > best_score:
                    best_score, best_entry = sim, entry
            except Exception:
                continue

        if best_score >= self._threshold and best_entry:
            logger.info(
                f"[cache] HIT  sim={best_score:.3f} "
                f"(threshold={self._threshold}) query={query[:50]!r}"
            )
            best_entry["result"]["_cache_hit"]  = True
            best_entry["result"]["_cache_sim"]  = round(best_score, 3)
            return best_entry["result"]

        logger.info(f"[cache] MISS sim={best_score:.3f} query={query[:50]!r}")
        return None

    async def set(self, query: str, result: dict, tier: str = "moderate") -> None:
        """Store a query+result in the cache."""
        r = await self._get_redis()
        if not r or not EMBED_AVAILABLE:
            return

        query_vec = _embed(query)
        key       = self.PREFIX + hashlib.md5(query.encode()).hexdigest()
        entry     = {"query": query, "embedding": query_vec, "result": result, "tier": tier}

        try:
            await r.set(key, json.dumps(entry), ex=self._ttl)
            await r.sadd(self.INDEX_KEY, key)
            await r.expire(self.INDEX_KEY, self._ttl)
            logger.info(f"[cache] SET  tier={tier} key={key[-8:]} query={query[:50]!r}")
        except Exception as e:
            logger.error(f"[cache] SET failed: {e}")

    async def invalidate(self, ticker: str) -> int:
        """Remove all cache entries mentioning a ticker (e.g. on fresh data arrival)."""
        r = await self._get_redis()
        if not r:
            return 0

        removed = 0
        index_keys = await r.smembers(self.INDEX_KEY)
        for key in index_keys:
            raw = await r.get(key)
            if raw and ticker.upper() in raw:
                await r.delete(key)
                await r.srem(self.INDEX_KEY, key)
                removed += 1

        logger.info(f"[cache] invalidated {removed} entries for ticker={ticker}")
        return removed
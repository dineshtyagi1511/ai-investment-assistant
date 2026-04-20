"""
RAG Engine
- ChromaDB for vector storage
- BGE-reranker for cross-encoder reranking (cuts noisy chunks)
- HyDE: generates a hypothetical answer first, embeds it, then searches
- Query router decides: API data vs vector search vs both
"""
import hashlib
from loguru import logger

try:
    import chromadb
    from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    logger.warning("[rag] chromadb not installed — vector search disabled")

try:
    from sentence_transformers import CrossEncoder
    RERANKER_AVAILABLE = True
except ImportError:
    RERANKER_AVAILABLE = False
    logger.warning("[rag] sentence-transformers not installed — reranker disabled")

from app.core.config import settings
from app.services.llm_router import route_completion


def _chunk_text(text: str, size: int = None, overlap: int = None) -> list[str]:
    """Simple word-based chunker."""
    size    = size    or settings.CHUNK_SIZE
    overlap = overlap or settings.CHUNK_OVERLAP
    words   = text.split()
    chunks  = []
    i = 0
    while i < len(words):
        chunk = " ".join(words[i : i + size])
        chunks.append(chunk)
        i += size - overlap
    return [c for c in chunks if len(c.split()) > 10]  # drop tiny tail chunks


class VectorStore:
    """Thin wrapper around ChromaDB with document indexing and similarity search."""

    def __init__(self, collection_name: str = "aira_docs"):
        if not CHROMA_AVAILABLE:
            self._client = None
            self._collection = None
            return

        self._client = chromadb.PersistentClient(path=settings.CHROMA_PERSIST_DIR)
        embed_fn = SentenceTransformerEmbeddingFunction(
            model_name="all-MiniLM-L6-v2"  # fast, good enough for finance
        )
        self._collection = self._client.get_or_create_collection(
            name=collection_name,
            embedding_function=embed_fn,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"[vector_store] collection '{collection_name}' ready")

    def index_documents(self, documents: list[dict]) -> int:
        """
        Index a list of {text, metadata} dicts.
        Chunks each document and upserts into ChromaDB.
        Returns number of chunks indexed.
        """
        if not self._collection:
            return 0

        all_chunks, all_ids, all_metas = [], [], []
        for doc in documents:
            text  = doc.get("text", "")
            meta  = doc.get("metadata", {})
            chunks = _chunk_text(text)
            for i, chunk in enumerate(chunks):
                doc_id = hashlib.md5(f"{meta.get('source','')}-{i}-{chunk[:40]}".encode()).hexdigest()
                all_chunks.append(chunk)
                all_ids.append(doc_id)
                all_metas.append(meta)

        if all_chunks:
            self._collection.upsert(
                documents=all_chunks,
                ids=all_ids,
                metadatas=all_metas,
            )
            logger.info(f"[vector_store] indexed {len(all_chunks)} chunks")

        return len(all_chunks)

    def search(self, query: str, top_k: int = None) -> list[dict]:
        """Return top-K most similar chunks for a query string."""
        if not self._collection:
            return []

        top_k = top_k or settings.TOP_K_RETRIEVAL
        results = self._collection.query(
            query_texts=[query],
            n_results=min(top_k, self._collection.count() or 1),
        )

        chunks = []
        for doc, meta, dist in zip(
            results["documents"][0],
            results["metadatas"][0],
            results["distances"][0],
        ):
            chunks.append({
                "text":      doc,
                "metadata":  meta,
                "score":     round(1 - dist, 4),   # cosine similarity
            })

        return chunks


class Reranker:
    """Cross-encoder reranker using BGE-reranker-base."""

    def __init__(self):
        if not RERANKER_AVAILABLE:
            self._model = None
            return
        try:
            self._model = CrossEncoder("BAAI/bge-reranker-base")
            logger.info("[reranker] BGE-reranker-base loaded")
        except Exception as e:
            logger.warning(f"[reranker] failed to load: {e}")
            self._model = None

    def rerank(self, query: str, chunks: list[dict], top_k: int = None) -> list[dict]:
        """Rerank chunks by cross-encoder relevance. Falls back gracefully."""
        if not self._model or not chunks:
            return chunks[: top_k or settings.TOP_K_RERANK]

        top_k = top_k or settings.TOP_K_RERANK
        pairs  = [(query, c["text"]) for c in chunks]
        scores = self._model.predict(pairs)

        for chunk, score in zip(chunks, scores):
            chunk["rerank_score"] = round(float(score), 4)

        reranked = sorted(chunks, key=lambda x: x["rerank_score"], reverse=True)
        logger.info(
            f"[reranker] {len(chunks)} → {top_k} chunks "
            f"(top score: {reranked[0]['rerank_score']:.3f})"
        )
        return reranked[:top_k]


class RAGEngine:
    """
    Full RAG pipeline:
      1. Optionally apply HyDE (generate hypothetical answer, use it as query)
      2. Search ChromaDB
      3. Rerank with BGE cross-encoder
      4. Return top-K chunks as formatted context string
    """

    def __init__(self):
        self.vector_store = VectorStore()
        self.reranker     = Reranker()

    async def _hyde_query(self, original_query: str) -> str:
        """
        HyDE: ask the LLM to write a hypothetical answer,
        then embed THAT instead of the raw question.
        Dramatically improves semantic match for financial queries.
        """
        messages = [
            {"role": "system", "content": (
                "You are a financial analyst. Write a short, factual paragraph "
                "that DIRECTLY answers the following question. "
                "Use realistic financial language and numbers. "
                "This is for embedding, not for the end user."
            )},
            {"role": "user", "content": original_query},
        ]
        try:
            hyp_answer, _ = await route_completion(
                messages=messages,
                query=original_query,
                max_tokens=200,
                temperature=0.3,
            )
            logger.info(f"[hyde] generated hypothetical answer ({len(hyp_answer)} chars)")
            return hyp_answer
        except Exception as e:
            logger.warning(f"[hyde] failed, using original query: {e}")
            return original_query

    async def retrieve(
        self,
        query: str,
        use_hyde: bool = True,
        top_k_retrieve: int = None,
        top_k_rerank: int = None,
    ) -> str:
        """
        Full retrieval pipeline. Returns a formatted context string
        ready to be injected into an LLM prompt.
        """
        search_query = await self._hyde_query(query) if use_hyde else query
        chunks       = self.vector_store.search(search_query, top_k=top_k_retrieve)

        if not chunks:
            logger.info("[rag] no chunks retrieved from vector store")
            return ""

        reranked = self.reranker.rerank(query, chunks, top_k=top_k_rerank)

        # Format as numbered context blocks
        lines = []
        for i, c in enumerate(reranked, 1):
            src  = c.get("metadata", {}).get("source", "unknown")
            score = c.get("rerank_score", c.get("score", 0))
            lines.append(f"[{i}] Source: {src} (relevance: {score:.2f})\n{c['text']}")

        return "\n\n".join(lines)

    def index(self, documents: list[dict]) -> int:
        """Convenience method to index documents into the vector store."""
        return self.vector_store.index_documents(documents)
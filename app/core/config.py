import litellm
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    PROJECT_NAME: str = "AIRA - AI Investment Research Assistant"
    VERSION: str = "1.0.0"

    # LLM
    OPENAI_API_KEY: str = "your-openai-key-here"

    # Data APIs
    ALPHA_VANTAGE_API_KEY: str = "your-alpha-vantage-key-here"
    NEWS_API_KEY: str = "your-news-api-key-here"

    # Databases
    MONGO_URI: str = "mongodb://localhost:27017"
    MONGO_DB_NAME: str = "aira"
    REDIS_URL: str = "redis://localhost:6379"

    # ChromaDB
    CHROMA_PERSIST_DIR: str = "./data/chroma"

    # RAG settings
    CHUNK_SIZE: int = 512
    CHUNK_OVERLAP: int = 64
    TOP_K_RETRIEVAL: int = 10
    TOP_K_RERANK: int = 3
    CACHE_TTL_SECONDS: int = 3600        # 1 hour cache
    CACHE_SIMILARITY_THRESHOLD: float = 0.92

    # Model routing
    MODEL_SIMPLE: str = "gpt-4o-mini"
    MODEL_COMPLEX: str = "gpt-4o"

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()

# LiteLLM global config — single place, applied everywhere
litellm.api_key = settings.OPENAI_API_KEY
litellm.set_verbose = False
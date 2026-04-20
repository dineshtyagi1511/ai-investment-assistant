"""
AIRA - AI Investment Research Assistant
FastAPI application entrypoint.
"""
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from loguru import logger

from app.core.config import settings
from app.api.routes import router
from app.db.mongo import MongoDB


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup and shutdown events."""
    logger.info(f"Starting {settings.PROJECT_NAME} v{settings.VERSION}")
    await MongoDB.connect()
    yield
    logger.info("Shutting down...")
    await MongoDB.disconnect()


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    description=(
        "Production-grade Multi-Source RAG system for financial intelligence. "
        "NOT financial advice."
    ),
    lifespan=lifespan,
)

# CORS — tighten allowed origins in production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")


@app.get("/")
async def root():
    return {
        "name":    settings.PROJECT_NAME,
        "version": settings.VERSION,
        "docs":    "/docs",
        "status":  "running",
    }
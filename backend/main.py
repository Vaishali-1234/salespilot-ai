"""FastAPI backend entrypoint for SalesPilot AI."""

from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from ai_engine.llm import llm_client
from backend.config import settings
from backend.routes.api import router as api_router
from crm.operations import init_db
from rag.embeddings import embedding_engine
from rag.retriever import default_retriever

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
)
logger = logging.getLogger("salespilot.backend")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing SalesPilot AI database and FAISS knowledge index...")
    init_db()
    idx_status = default_retriever.ensure_ready(force_rebuild=False)
    logger.info("Knowledge Base ready: %s", idx_status)
    logger.info("LLM status: %s", llm_client.get_status()["message"])
    yield
    logger.info("Shutting down SalesPilot AI backend.")


app = FastAPI(
    title="SalesPilot AI — TechNova Solutions API",
    description="Autonomous AI Sales Voice Agent Backend (RAG, Lead Qualification, Sentiment, CRM, Booking)",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router)


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "app_name": settings.app_name,
        "llm_status": llm_client.get_status(),
        "embedding_mode": embedding_engine.mode,
        "total_kb_chunks": len(default_retriever.store.chunks),
        "whisper_model": settings.whisper_model_size,
        "edge_tts_voice": settings.edge_tts_voice,
    }

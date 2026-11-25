"""Central configuration module for SalesPilot AI."""

import os

# Prevent OpenMP duplicate-library crashes on Windows when faiss, torch, and ctranslate2 coexist
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Typed application settings sourced from .env and environment variables."""

    app_name: str = "SalesPilot AI — TechNova Solutions"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-2.5-flash"
    openai_api_key: str = ""

    # Voice layer
    whisper_model_size: str = "base"
    whisper_device: str = "cpu"
    whisper_compute_type: str = "int8"
    edge_tts_voice: str = "en-US-AriaNeural"

    # RAG layer
    embedding_model: str = "all-MiniLM-L6-v2"
    knowledge_base_dir: Path = BASE_DIR / "knowledge_base"
    faiss_index_dir: Path = BASE_DIR / "data" / "faiss_index"

    # Storage & server
    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'salespilot_crm.db').as_posix()}"
    backend_url: str = "http://127.0.0.1:8000"
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    log_level: str = "INFO"

    model_config = SettingsConfigDict(
        env_file=str(BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
settings.knowledge_base_dir.mkdir(parents=True, exist_ok=True)
(BASE_DIR / "data").mkdir(parents=True, exist_ok=True)

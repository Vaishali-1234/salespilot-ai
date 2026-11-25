"""Document loading and LangChain chunking for the TechNova Solutions knowledge base."""

from dataclasses import dataclass
import logging
from pathlib import Path
from typing import List, Optional

from backend.config import settings

logger = logging.getLogger(__name__)


@dataclass
class DocumentChunk:
    """Represents a single indexed chunk with provenance metadata."""

    chunk_id: str
    source: str
    title: str
    content: str
    char_count: int


def _extract_title(text: str, fallback: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped.lstrip("#").strip()
    return fallback.replace("_", " ").title()


def load_documents(kb_dir: Optional[Path] = None) -> List[dict]:
    """Load all .txt and .md documents from the knowledge base directory."""
    directory = Path(kb_dir or settings.knowledge_base_dir)
    if not directory.exists():
        directory.mkdir(parents=True, exist_ok=True)
        return []

    documents: List[dict] = []
    for file_path in sorted(directory.iterdir()):
        if file_path.is_file() and file_path.suffix.lower() in {".txt", ".md"}:
            text = file_path.read_text(encoding="utf-8", errors="ignore").strip()
            if not text:
                continue
            documents.append(
                {
                    "source": file_path.name,
                    "path": str(file_path),
                    "title": _extract_title(text, file_path.stem),
                    "text": text,
                }
            )
    logger.info("Loaded %d knowledge base documents from %s", len(documents), directory)
    return documents


def chunk_documents(
    documents: List[dict],
    chunk_size: int = 500,
    chunk_overlap: int = 80,
) -> List[DocumentChunk]:
    """Split raw documents into overlapping semantic chunks via LangChain."""
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", ". ", " ", ""],
    )

    chunks: List[DocumentChunk] = []
    for doc in documents:
        splits = splitter.split_text(doc["text"])
        for idx, split_text in enumerate(splits):
            cleaned = split_text.strip()
            if not cleaned:
                continue
            chunk_id = f"{doc['source']}::chunk_{idx + 1}"
            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    source=doc["source"],
                    title=doc["title"],
                    content=cleaned,
                    char_count=len(cleaned),
                )
            )
    logger.info("Generated %d chunks across %d documents", len(chunks), len(documents))
    return chunks

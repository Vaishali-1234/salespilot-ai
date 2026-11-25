"""High-level RAG retriever interface for the SalesPilot AI agent and API."""

import logging
from pathlib import Path
from typing import Any, Dict, List, Optional

from backend.config import settings
from rag.document_loader import load_documents
from rag.embeddings import embedding_engine
from rag.vector_store import FAISSVectorStore

logger = logging.getLogger(__name__)


class KnowledgeRetriever:
    """Orchestrates knowledge base retrieval with explicit groundedness checks."""

    def __init__(
        self,
        kb_dir: Optional[Path] = None,
        index_dir: Optional[Path] = None,
    ) -> None:
        self.kb_dir = Path(kb_dir or settings.knowledge_base_dir)
        self.store = FAISSVectorStore(kb_dir=self.kb_dir, index_dir=index_dir)

    def ensure_ready(self, force_rebuild: bool = False) -> Dict[str, Any]:
        return self.store.build_index(force_rebuild=force_rebuild)

    def retrieve_company_information(
        self,
        query: str,
        top_k: int = 4,
        min_score: float = 0.22,
    ) -> Dict[str, Any]:
        """Retrieve relevant TechNova Solutions knowledge chunks for a customer query."""
        if not query or not query.strip():
            return {
                "found": False,
                "query": query,
                "embedding_mode": embedding_engine.mode,
                "results": [],
                "context_text": "",
                "sources": [],
            }

        results = self.store.search(query=query.strip(), top_k=top_k, min_score=min_score)
        if not results:
            return {
                "found": False,
                "query": query,
                "embedding_mode": self.store.embedding_mode,
                "results": [],
                "context_text": "",
                "sources": [],
            }

        context_lines = []
        unique_sources: List[str] = []
        for item in results:
            src = item["source"]
            if src not in unique_sources:
                unique_sources.append(src)
            context_lines.append(
                f"[Source: {src} | Score: {item['score']}]\n{item['content']}"
            )

        return {
            "found": True,
            "query": query,
            "embedding_mode": self.store.embedding_mode,
            "results": results,
            "context_text": "\n\n---\n\n".join(context_lines),
            "sources": unique_sources,
        }

    def list_documents(self) -> List[Dict[str, Any]]:
        docs = load_documents(self.kb_dir)
        return [
            {
                "source": d["source"],
                "title": d["title"],
                "characters": len(d["text"]),
                "preview": d["text"][:300],
                "content": d["text"],
            }
            for d in docs
        ]

    def add_document(self, filename: str, content: str) -> Dict[str, Any]:
        """Save a new knowledge document and rebuild the FAISS index."""
        safe_name = Path(filename).name
        if not safe_name.endswith((".txt", ".md")):
            safe_name = f"{safe_name}.txt"
        target_path = self.kb_dir / safe_name
        target_path.write_text(content.strip() + "\n", encoding="utf-8")
        rebuild_info = self.store.build_index(force_rebuild=True)
        return {
            "filename": safe_name,
            "rebuild": rebuild_info,
        }


default_retriever = KnowledgeRetriever()

"""FAISS vector store indexing, persistence, and cosine similarity search."""

from dataclasses import asdict
import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np

from backend.config import settings
from rag.document_loader import DocumentChunk, chunk_documents, load_documents
from rag.embeddings import embedding_engine

logger = logging.getLogger(__name__)


def _load_faiss():
    """Lazily import faiss to avoid Windows C++ DLL init issues during test collection."""
    try:
        import faiss
        return faiss
    except Exception as exc:
        logger.warning("FAISS unavailable (%s); using NumPy exact cosine search fallback.", exc)
        return None


class FAISSVectorStore:
    """Persistent FAISS IndexFlatIP store for TechNova Solutions knowledge chunks."""

    def __init__(
        self,
        kb_dir: Optional[Path] = None,
        index_dir: Optional[Path] = None,
    ) -> None:
        self.kb_dir = Path(kb_dir or settings.knowledge_base_dir)
        self.index_dir = Path(index_dir or settings.faiss_index_dir)
        self.index_path = self.index_dir / "index.faiss"
        self.vectors_path = self.index_dir / "vectors.npy"
        self.meta_path = self.index_dir / "chunks.json"

        self.index: Any = None
        self.vectors: Optional[np.ndarray] = None
        self.chunks: List[Dict[str, Any]] = []
        self.embedding_mode: str = "uninitialized"
        self.vector_backend: str = "uninitialized"

    def build_index(self, force_rebuild: bool = False) -> Dict[str, Any]:
        """Build or load the FAISS index from knowledge_base documents."""
        self.index_dir.mkdir(parents=True, exist_ok=True)

        if not force_rebuild and self.meta_path.exists() and (self.index_path.exists() or self.vectors_path.exists()):
            try:
                self.load_index()
                if (self.index is not None or self.vectors is not None) and self.chunks:
                    return {
                        "status": "loaded",
                        "chunks": len(self.chunks),
                        "embedding_mode": self.embedding_mode,
                        "vector_backend": self.vector_backend,
                    }
            except Exception as exc:
                logger.warning("Failed loading cached vector index (%s); rebuilding.", exc)

        docs = load_documents(self.kb_dir)
        chunk_objs: List[DocumentChunk] = chunk_documents(docs)
        if not chunk_objs:
            self.index = None
            self.vectors = None
            self.chunks = []
            return {"status": "empty", "chunks": 0, "embedding_mode": "none"}

        texts = [c.content for c in chunk_objs]
        vectors, mode = embedding_engine.embed_texts(texts)
        self.embedding_mode = mode
        self.vectors = np.ascontiguousarray(vectors, dtype=np.float32)
        dim = int(self.vectors.shape[1])

        self.chunks = [asdict(c) for c in chunk_objs]
        np.save(str(self.vectors_path), self.vectors)

        faiss = _load_faiss()
        if faiss is not None:
            index = faiss.IndexFlatIP(dim)
            index.add(self.vectors)
            self.index = index
            self.vector_backend = "faiss_index_flat_ip"
            faiss.write_index(self.index, str(self.index_path))
        else:
            self.index = None
            self.vector_backend = "numpy_cosine_fallback"

        self.meta_path.write_text(
            json.dumps(
                {
                    "embedding_mode": self.embedding_mode,
                    "vector_backend": self.vector_backend,
                    "dimension": dim,
                    "chunks": self.chunks,
                },
                indent=2,
                ensure_ascii=False,
            ),
            encoding="utf-8",
        )
        logger.info(
            "Built vector index with %d chunks (dim=%d, embed=%s, backend=%s)",
            len(self.chunks),
            dim,
            self.embedding_mode,
            self.vector_backend,
        )
        return {
            "status": "built",
            "chunks": len(self.chunks),
            "embedding_mode": self.embedding_mode,
            "vector_backend": self.vector_backend,
        }

    def load_index(self) -> None:
        """Load persisted FAISS index (or numpy fallback) and chunk metadata from disk."""
        if not self.meta_path.exists():
            raise FileNotFoundError("Vector index metadata does not exist yet.")
        payload = json.loads(self.meta_path.read_text(encoding="utf-8"))
        self.chunks = payload.get("chunks", [])
        self.embedding_mode = payload.get("embedding_mode", "unknown")

        faiss = _load_faiss()
        if faiss is not None and self.index_path.exists():
            self.index = faiss.read_index(str(self.index_path))
            self.vector_backend = "faiss_index_flat_ip"
        elif self.vectors_path.exists():
            self.vectors = np.load(str(self.vectors_path))
            self.index = None
            self.vector_backend = "numpy_cosine_fallback"
        else:
            raise FileNotFoundError("No persisted vector index file found.")

    def search(
        self,
        query: str,
        top_k: int = 4,
        min_score: float = 0.22,
    ) -> List[Dict[str, Any]]:
        """Run cosine similarity search and return matching chunks with scores."""
        if (self.index is None and self.vectors is None) or not self.chunks:
            self.build_index(force_rebuild=False)
        if (self.index is None and self.vectors is None) or not self.chunks:
            return []

        q_vec, q_mode = embedding_engine.embed_texts([query])
        expected_dim = self.index.d if self.index is not None else int(self.vectors.shape[1])
        if q_mode != self.embedding_mode or q_vec.shape[1] != expected_dim:
            self.build_index(force_rebuild=True)
            q_vec, _ = embedding_engine.embed_texts([query])

        k = min(top_k, len(self.chunks))
        q_arr = np.ascontiguousarray(q_vec, dtype=np.float32)

        if self.index is not None:
            scores, indices = self.index.search(q_arr, k)
            pairs = zip(scores[0], indices[0])
        else:
            sims = (self.vectors @ q_arr[0]).astype(float)
            top_indices = np.argsort(-sims)[:k]
            pairs = [(float(sims[i]), int(i)) for i in top_indices]

        results: List[Dict[str, Any]] = []
        for score, idx in pairs:
            if idx < 0 or idx >= len(self.chunks):
                continue
            sim = float(score)
            if sim < min_score:
                continue
            chunk = self.chunks[idx]
            results.append(
                {
                    "chunk_id": chunk["chunk_id"],
                    "source": chunk["source"],
                    "title": chunk["title"],
                    "content": chunk["content"],
                    "score": round(sim, 4),
                }
            )
        return results

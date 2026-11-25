"""Embedding generation using SentenceTransformers with transparent offline fallback."""

import hashlib
import logging
import re
from typing import List, Optional, Tuple

import numpy as np

from backend.config import settings

logger = logging.getLogger(__name__)


class EmbeddingEngine:
    """Generates L2-normalized dense vector embeddings for RAG indexing and queries."""

    def __init__(self, model_name: Optional[str] = None) -> None:
        self.model_name = model_name or settings.embedding_model
        self._model = None
        self.mode: str = "uninitialized"
        self.fallback_reason: Optional[str] = None
        self.dimension: int = 384

    def _ensure_loaded(self) -> None:
        if self.mode != "uninitialized":
            return
        try:
            from sentence_transformers import SentenceTransformer

            try:
                self._model = SentenceTransformer(self.model_name, local_files_only=True)
            except Exception:
                self._model = SentenceTransformer(self.model_name)
            test_vec = self._model.encode(["healthcheck"], normalize_embeddings=True)
            self.dimension = int(test_vec.shape[1])
            self.mode = "sentence_transformers"
            logger.info("Loaded SentenceTransformer model '%s' (dim=%d)", self.model_name, self.dimension)
        except Exception as exc:
            self._model = None
            self.mode = "offline_hash_fallback"
            self.fallback_reason = str(exc)
            self.dimension = 384
            logger.warning(
                "SentenceTransformer unavailable (%s). Using deterministic lexical-hash fallback.",
                exc,
            )

    def embed_texts(self, texts: List[str]) -> Tuple[np.ndarray, str]:
        """Return L2-normalized float32 embeddings of shape (N, D) and the active mode."""
        self._ensure_loaded()
        if not texts:
            return np.zeros((0, self.dimension), dtype=np.float32), self.mode

        if self._model is not None:
            vectors = self._model.encode(
                texts,
                normalize_embeddings=True,
                convert_to_numpy=True,
                show_progress_bar=False,
            )
            return np.asarray(vectors, dtype=np.float32), self.mode

        # Deterministic word + character-trigram hash projection fallback (never pretends to be ST)
        mat = np.zeros((len(texts), self.dimension), dtype=np.float32)
        for row_idx, text in enumerate(texts):
            tokens = re.findall(r"[a-z0-9]+", text.lower())
            features = list(tokens)
            for tok in tokens:
                if len(tok) >= 3:
                    features.extend(tok[i : i + 3] for i in range(len(tok) - 2))
            for feat in features:
                digest = hashlib.md5(feat.encode("utf-8")).digest()
                bucket = int.from_bytes(digest[:4], "little") % self.dimension
                sign = 1.0 if (digest[4] % 2 == 0) else -1.0
                mat[row_idx, bucket] += sign
            norm = np.linalg.norm(mat[row_idx])
            if norm > 0:
                mat[row_idx] /= norm
        return mat, self.mode


embedding_engine = EmbeddingEngine()

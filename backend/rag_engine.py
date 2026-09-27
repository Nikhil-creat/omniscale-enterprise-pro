"""
backend/rag_engine.py
OmniScale Enterprise Pro — Designed and Developed by NIKHIL CHARY SRIRAMOJU

Vector-store backed retrieval engine. Uses FAISS for the index and
sentence-transformers for embeddings. Each user/document set gets its own
namespace, persisted to disk under VECTOR_INDEX_DIR so it survives
worker restarts.
"""
from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import dataclass
from typing import Optional

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from backend.config import get_settings

logger = logging.getLogger("omniscale.rag")
settings = get_settings()

_model_lock = threading.Lock()
_model: Optional[SentenceTransformer] = None


def _get_model() -> SentenceTransformer:
    global _model
    if _model is None:
        with _model_lock:
            if _model is None:
                logger.info("Loading embedding model %s", settings.EMBEDDING_MODEL)
                _model = SentenceTransformer(settings.EMBEDDING_MODEL)
    return _model


def chunk_text(text: str, chunk_size: int = 800, overlap: int = 120) -> list[str]:
    """Simple sliding-window chunker sized for embedding-model context."""
    text = " ".join(text.split())
    if not text:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(text):
        end = min(start + chunk_size, len(text))
        chunks.append(text[start:end])
        if end == len(text):
            break
        start = end - overlap
    return chunks


@dataclass
class RetrievedChunk:
    chunk_text: str
    score: float
    source_document: str


class VectorNamespace:
    """A FAISS index + metadata store scoped to one namespace (e.g. per user)."""

    def __init__(self, namespace: str):
        self.namespace = namespace
        self.dir = os.path.join(settings.VECTOR_INDEX_DIR, namespace)
        os.makedirs(self.dir, exist_ok=True)
        self.index_path = os.path.join(self.dir, "index.faiss")
        self.meta_path = os.path.join(self.dir, "meta.json")
        self._dim = _get_model().get_sentence_embedding_dimension()
        self.index = self._load_or_create_index()
        self.metadata: list[dict] = self._load_metadata()

    def _load_or_create_index(self) -> faiss.Index:
        if os.path.exists(self.index_path):
            return faiss.read_index(self.index_path)
        return faiss.IndexFlatIP(self._dim)

    def _load_metadata(self) -> list[dict]:
        if os.path.exists(self.meta_path):
            with open(self.meta_path, "r", encoding="utf-8") as f:
                return json.load(f)
        return []

    def _persist(self) -> None:
        faiss.write_index(self.index, self.index_path)
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f)

    def add_document(self, source_document: str, text: str) -> int:
        chunks = chunk_text(text)
        if not chunks:
            return 0
        model = _get_model()
        embeddings = model.encode(chunks, normalize_embeddings=True, show_progress_bar=False)
        self.index.add(np.asarray(embeddings, dtype="float32"))
        for chunk in chunks:
            self.metadata.append({"text": chunk, "source": source_document})
        self._persist()
        return len(chunks)

    def query(self, query_text: str, top_k: int = 5) -> list[RetrievedChunk]:
        if self.index.ntotal == 0:
            return []
        model = _get_model()
        query_vec = model.encode([query_text], normalize_embeddings=True, show_progress_bar=False)
        scores, indices = self.index.search(np.asarray(query_vec, dtype="float32"), min(top_k, self.index.ntotal))
        results: list[RetrievedChunk] = []
        for score, idx in zip(scores[0], indices[0]):
            if idx == -1:
                continue
            meta = self.metadata[idx]
            results.append(RetrievedChunk(chunk_text=meta["text"], score=float(score), source_document=meta["source"]))
        return results


_namespace_cache: dict[str, VectorNamespace] = {}
_cache_lock = threading.Lock()


def get_namespace(namespace: str) -> VectorNamespace:
    with _cache_lock:
        if namespace not in _namespace_cache:
            _namespace_cache[namespace] = VectorNamespace(namespace)
        return _namespace_cache[namespace]


def ingest_document(namespace: str, source_document: str, text: str) -> int:
    """Synchronous ingest, intended to be called from a Celery worker."""
    ns = get_namespace(namespace)
    return ns.add_document(source_document, text)


def retrieve(namespace: str, query_text: str, top_k: int = 5) -> list[RetrievedChunk]:
    ns = get_namespace(namespace)
    return ns.query(query_text, top_k=top_k)

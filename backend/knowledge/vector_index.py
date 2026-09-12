"""
backend/knowledge/vector_index.py — Vector Index Abstraction & Metadata Filtering.

Provides a reproducible, deterministic vector index for NOVA engineering knowledge:
- Dense vector similarity search (cosine similarity via BAAI/bge-small-en-v1.5)
- Exact-match industrial metadata filtering (document_type, equipment_id, equipment_type, unit_area, etc.)
- In-memory local indexing for deterministic unit and integration testing
- Full add, update, delete, rebuild, and search capabilities
"""

from __future__ import annotations

import logging
from typing import Any, Callable, Dict, List, Optional, Protocol, Tuple, Union

import numpy as np

from backend.knowledge.models import DocumentChunk, DocumentType
from backend.memory.embeddings import embed_batch, embed_text

logger = logging.getLogger("nova.knowledge.vector_index")


class VectorIndex(Protocol):
    """Protocol defining vector index contract."""

    def add_chunks(self, chunks: List[DocumentChunk]) -> int:
        ...

    def delete_document(self, document_id: str) -> int:
        ...

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[DocumentChunk, float]]:
        ...

    def clear(self) -> None:
        ...

    def count(self) -> int:
        ...


class LocalVectorIndex:
    """
    Deterministic, in-memory vector index with multi-field industrial metadata filtering.
    """

    def __init__(self, embedder_fn: Optional[Callable[[List[str]], List[List[float]]]] = None) -> None:
        self._embedder_fn = embedder_fn or embed_batch
        self._chunks: Dict[str, DocumentChunk] = {}
        self._vectors: Dict[str, np.ndarray] = {}  # chunk_id -> normalized vector array

    def count(self) -> int:
        return len(self._chunks)

    def get_chunk(self, chunk_id: str) -> Optional[DocumentChunk]:
        return self._chunks.get(chunk_id)

    def clear(self) -> None:
        self._chunks.clear()
        self._vectors.clear()

    def add_chunks(self, chunks: List[DocumentChunk]) -> int:
        """
        Embed and index a list of DocumentChunk objects.
        """
        if not chunks:
            return 0

        # Filter out chunks that need embedding
        new_chunks = [c for c in chunks if c.chunk_id not in self._vectors]
        if new_chunks:
            texts = [c.text for c in new_chunks]
            raw_vecs = self._embedder_fn(texts)

            for chunk, vec in zip(new_chunks, raw_vecs):
                arr = np.array(vec, dtype=np.float32)
                norm = np.linalg.norm(arr)
                if norm > 0:
                    arr = arr / norm
                self._chunks[chunk.chunk_id] = chunk
                self._vectors[chunk.chunk_id] = arr

        # For chunks that already had vectors, update chunk object
        for c in chunks:
            self._chunks[c.chunk_id] = c

        logger.info("Indexed %d chunks (total in index: %d)", len(chunks), len(self._chunks))
        return len(chunks)

    def delete_document(self, document_id: str) -> int:
        """
        Remove all chunks associated with a document_id.
        """
        to_delete = [
            cid for cid, chunk in self._chunks.items()
            if chunk.document_id == document_id
        ]
        for cid in to_delete:
            self._chunks.pop(cid, None)
            self._vectors.pop(cid, None)
        logger.info("Deleted %d chunks for document '%s'", len(to_delete), document_id)
        return len(to_delete)

    def rebuild(self, chunks: List[DocumentChunk]) -> int:
        """
        Clear and rebuild index from provided chunks.
        """
        self.clear()
        return self.add_chunks(chunks)

    def search(
        self,
        query_vector: List[float],
        top_k: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Tuple[DocumentChunk, float]]:
        """
        Perform cosine similarity search with exact metadata filtering.
        """
        if not self._chunks or not query_vector:
            return []

        q_vec = np.array(query_vector, dtype=np.float32)
        q_norm = np.linalg.norm(q_vec)
        if q_norm > 0:
            q_vec = q_vec / q_norm

        candidates: List[Tuple[DocumentChunk, float]] = []

        for cid, chunk in self._chunks.items():
            # 1. Apply metadata filtering
            if filters and not self._matches_filters(chunk, filters):
                continue

            doc_vec = self._vectors.get(cid)
            if doc_vec is None:
                continue

            # 2. Cosine similarity
            similarity = float(np.dot(q_vec, doc_vec))
            # Normalise similarity from [-1, 1] to [0, 1] for friendly presentation
            score = max(0.0, min(1.0, (similarity + 1.0) / 2.0))
            candidates.append((chunk, score))

        # Sort descending by similarity score
        candidates.sort(key=lambda x: x[1], reverse=True)

        return candidates[:top_k]

    def _matches_filters(self, chunk: DocumentChunk, filters: Dict[str, Any]) -> bool:
        """
        Check if a chunk matches all provided filter constraints.
        Supports: document_type, equipment_id, equipment_type, unit_area, version, authority.
        """
        meta = chunk.metadata or {}

        for key, target_val in filters.items():
            if target_val is None:
                continue

            # Standardize key names
            norm_key = key.lower()

            if norm_key in ("document_type", "doc_type", "type"):
                chunk_type = meta.get("document_type") or meta.get("doc_type")
                if isinstance(target_val, (list, set, tuple)):
                    target_types = [
                        t.value if isinstance(t, DocumentType) else str(t).lower()
                        for t in target_val
                    ]
                    if str(chunk_type).lower() not in target_types:
                        return False
                else:
                    target_str = target_val.value if isinstance(target_val, DocumentType) else str(target_val)
                    if str(chunk_type).lower() != target_str.lower():
                        return False

            elif norm_key in ("equipment_id", "asset_id", "tag"):
                chunk_eq = meta.get("equipment_id") or meta.get("asset_id")
                if not chunk_eq:
                    return False
                if isinstance(target_val, (list, set, tuple)):
                    if str(chunk_eq).upper() not in [str(x).upper() for x in target_val]:
                        return False
                else:
                    if str(chunk_eq).upper() != str(target_val).upper():
                        return False

            elif norm_key in ("equipment_type", "asset_type", "equipment_class"):
                chunk_type = meta.get("equipment_type") or meta.get("equipment_class")
                if not chunk_type:
                    return False
                if isinstance(target_val, (list, set, tuple)):
                    if str(chunk_type).lower() not in [str(x).lower() for x in target_val]:
                        return False
                else:
                    if str(chunk_type).lower() != str(target_val).lower():
                        return False

            elif norm_key in ("unit_area", "unit", "area", "zone_id"):
                chunk_unit = meta.get("unit_area") or meta.get("unit") or meta.get("area") or meta.get("zone_id")
                if not chunk_unit:
                    return False
                if str(chunk_unit).upper() != str(target_val).upper():
                    return False

            elif norm_key in ("version", "ver"):
                chunk_ver = meta.get("version")
                if str(chunk_ver).lower() != str(target_val).lower():
                    return False

            elif norm_key in ("authority", "standard_body", "issuer"):
                chunk_auth = meta.get("authority")
                if str(chunk_auth).lower() != str(target_val).lower():
                    return False

            else:
                # Custom metadata filter
                chunk_custom = meta.get(key)
                if chunk_custom != target_val:
                    return False

        return True

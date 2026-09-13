"""QdrantMemoryClient — managed wrapper around the official Qdrant Python client.

Provides:
- Environment-driven configuration (QDRANT_URL, QDRANT_API_KEY via python-dotenv).
- ``health_check()`` — non-throwing liveness probe.
- ``ensure_collections()`` — idempotent creation of all 8 VIGIL collections.
- Direct access to the underlying ``qdrant_client.QdrantClient`` via ``.qclient``.

On import, a module-level health check logs a clear warning if Qdrant is
unreachable — but does **not** raise, so dependent modules can still import
and degrade gracefully.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import time
from dotenv import load_dotenv
from qdrant_client import QdrantClient
from qdrant_client.http.exceptions import UnexpectedResponse
from qdrant_client.models import Distance, PointStruct, VectorParams

from qdrant.collections.schema import ALL_COLLECTION_NAMES, COLLECTION_CONFIGS

logger = logging.getLogger(__name__)

# Load environment variables from repo-root .env file if present
load_dotenv()

DEFAULT_QDRANT_URL = "http://localhost:6333"


class QdrantMemoryClient:
    """Managed wrapper around ``qdrant_client.QdrantClient``.

    Args:
        url: Qdrant server URL. Defaults to env ``QDRANT_URL`` or ``http://localhost:6333``.
        api_key: Qdrant API key. Defaults to env ``QDRANT_API_KEY``.
        location: Qdrant location string (e.g. ``":memory:"`` for unit tests).
    """

    def __init__(
        self,
        url: str | None = None,
        api_key: str | None = None,
        location: str | None = None,
    ) -> None:
        self.url = url or os.getenv("QDRANT_URL") or DEFAULT_QDRANT_URL
        self.api_key = api_key if api_key is not None else os.getenv("QDRANT_API_KEY")
        self.location = location
        self.prefix = os.getenv("QDRANT_COLLECTION_PREFIX") or "vigil_"

        if location:
            self.qclient = QdrantClient(location=location)
        else:
            self.qclient = QdrantClient(
                url=self.url,
                api_key=self.api_key,
                timeout=30,
                check_compatibility=False,
            )

    def _resolve_collection_name(self, name: str) -> str:
        """Prepends self.prefix if not already present."""
        if name.startswith(self.prefix):
            return name
        return f"{self.prefix}{name}"

    # ------------------------------------------------------------------
    # Health
    # ------------------------------------------------------------------

    def health_check(self) -> bool:
        """Return ``True`` if Qdrant responds, ``False`` otherwise."""
        for attempt in range(3):
            try:
                self.qclient.get_collections()
                return True
            except Exception as exc:
                if attempt == 2:
                    logger.warning("Qdrant health check failed at %s: %s", self.url, exc)
                    return False
                time.sleep(1)
        return False

    # ------------------------------------------------------------------
    # Collection management
    # ------------------------------------------------------------------

    def ensure_collections(self) -> None:
        """Idempotently create all 8 VIGIL collections.

        - Fetches existing collection names first.
        - Only creates collections that do not already exist.
        - **Never** drops/recreates an existing collection.
        """
        try:
            existing = {
                c.name for c in self.qclient.get_collections().collections
            }
        except Exception:
            logger.exception(
                "Cannot list Qdrant collections at %s — aborting ensure_collections",
                self.url,
            )
            return

        distance_map = {
            "Cosine": Distance.COSINE,
            "Euclid": Distance.EUCLID,
            "Dot": Distance.DOT,
        }

        from qdrant_client.models import PayloadSchemaType

        for name in ALL_COLLECTION_NAMES:
            prefixed_name = self._resolve_collection_name(name)
            if prefixed_name not in existing:
                cfg = COLLECTION_CONFIGS[name]
                dist = distance_map.get(cfg["distance"], Distance.COSINE)
                try:
                    self.qclient.create_collection(
                        collection_name=prefixed_name,
                        vectors_config=VectorParams(
                            size=cfg["vector_size"],
                            distance=dist,
                        ),
                    )
                    logger.info("Created Qdrant collection '%s'.", prefixed_name)
                except UnexpectedResponse as exc:
                    if exc.status_code == 409:
                        logger.debug("Collection '%s' was created concurrently — OK.", prefixed_name)
                    else:
                        logger.exception("Failed to create collection '%s'.", prefixed_name)
                except Exception:
                    logger.exception("Failed to create collection '%s'.", prefixed_name)

            # Ensure payload indexes exist for filtered fields
            for field in ("equipment_id", "zone_id", "equipment_class"):
                try:
                    self.qclient.create_payload_index(
                        collection_name=prefixed_name,
                        field_name=field,
                        field_schema=PayloadSchemaType.KEYWORD,
                    )
                except Exception:
                    pass

    # ------------------------------------------------------------------
    # Low-level helpers used by hybrid_search / collections
    # ------------------------------------------------------------------

    def upsert_points(
        self,
        collection_name: str,
        points: list[PointStruct],
    ) -> None:
        """Upsert a batch of points into *collection_name*."""
        prefixed_name = self._resolve_collection_name(collection_name)
        try:
            self.qclient.upsert(
                collection_name=prefixed_name,
                points=points,
            )
        except Exception:
            logger.exception(
                "Failed to upsert %d points into '%s'.",
                len(points),
                prefixed_name,
            )
            raise

    def search(
        self,
        collection_name: str,
        query_vector: list[float],
        limit: int = 10,
        query_filter: Any = None,
    ) -> list:
        """Vector similarity search with optional pre-filter.

        Returns a list of ``ScoredPoint`` objects, or ``[]`` on error.
        """
        prefixed_name = self._resolve_collection_name(collection_name)
        try:
            if hasattr(self.qclient, "query_points"):
                res = self.qclient.query_points(
                    collection_name=prefixed_name,
                    query=query_vector,
                    limit=limit,
                    query_filter=query_filter,
                )
                return res.points
            elif hasattr(self.qclient, "search"):
                return getattr(self.qclient, "search")(
                    collection_name=prefixed_name,
                    query_vector=query_vector,
                    limit=limit,
                    query_filter=query_filter,
                )
            return []
        except Exception:
            logger.exception(
                "Search failed on collection '%s'.", prefixed_name
            )
            return []


    def scroll(
        self,
        collection_name: str,
        scroll_filter: Any = None,
        limit: int = 10,
    ) -> list:
        """Filtered scroll (exact-match retrieval, no vector ranking).

        Returns a list of ``Record`` objects, or ``[]`` on error.
        """
        prefixed_name = self._resolve_collection_name(collection_name)
        try:
            records, _ = self.qclient.scroll(
                collection_name=prefixed_name,
                scroll_filter=scroll_filter,
                limit=limit,
            )
            return records
        except Exception:
            logger.exception(
                "Scroll failed on collection '%s'.", prefixed_name
            )
            return []


# ------------------------------------------------------------------
# Module-level liveness probe (warning only, never raises)
# ------------------------------------------------------------------

def _startup_health_check() -> None:
    try:
        _probe = QdrantMemoryClient()
        if _probe.health_check():
            logger.info("Qdrant is reachable at %s", _probe.url)
        else:
            logger.warning(
                "Qdrant is NOT reachable at %s — memory layer will degrade.",
                _probe.url,
            )
    except Exception:
        target_url = os.getenv("QDRANT_URL") or DEFAULT_QDRANT_URL
        logger.warning(
            "Qdrant is NOT reachable at %s — memory layer will degrade.",
            target_url,
        )


_startup_health_check()

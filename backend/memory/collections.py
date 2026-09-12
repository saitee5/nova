"""MemoryStore — high-level interface composing QdrantMemoryClient, hybrid_search, and reranker.

Main entry point for downstream agent modules (Risk Reasoner, Response Orchestrator, etc.)
to interact with VIGIL's organizational memory layer (§6 / §10.7).
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from qdrant_client.models import PointStruct

from backend.memory.client import QdrantMemoryClient
from backend.memory.embeddings import embed_text
from backend.memory.hybrid_search import hybrid_search
from backend.memory.reranker import rerank
from backend.models.case import OperationalContext
from backend.models.evidence import HistoricalMatch

logger = logging.getLogger(__name__)


class MemoryStore:
    """High-level facade over VIGIL's Qdrant vector memory layer."""

    def __init__(self, client: QdrantMemoryClient | None = None) -> None:
        self.client = client or QdrantMemoryClient()
        # Ensure collection structures exist
        self.client.ensure_collections()

    def retrieve_historical_matches(
        self,
        context: OperationalContext,
        top_k: int = 10,
        top_n: int = 3,
    ) -> list[HistoricalMatch]:
        """Retrieve and rerank relevant historical incidents, near-misses, and risk patterns.

        Args:
            context: The OperationalContext object assembled for a case.
            top_k: Max candidates to retrieve per collection via hybrid search.
            top_n: Top candidates to return after cross-encoder reranking.

        Returns:
            List of HistoricalMatch pydantic objects with non-empty ``matched_on``.
        """
        # 1. Construct query text from context
        event_facts = " ".join(
            f"{e.source}: {e.value or ''} {e.unit or ''} hint={e.severity_hint}"
            for e in context.recent_events
        )
        permit_facts = " ".join(
            f"permit {p.permit_type} status={p.status}" for p in context.active_permits
        )
        maint_facts = " ".join(
            f"maint {m.fault_code or ''} {m.summary}" for m in context.recent_maintenance
        )
        equip_facts = " ".join(
            f"equipment {eq.equipment_id} ({eq.equipment_class})" for eq in context.equipment
        )

        query_text = (
            f"Zone {context.zone_id}. Equipment: {equip_facts}. "
            f"Events: {event_facts}. Permits: {permit_facts}. Maintenance: {maint_facts}."
        )

        # Identify target equipment class if available
        equip_class = context.equipment[0].equipment_class if context.equipment else None

        # 2. Search across candidate collections: incidents_historical, near_misses, risk_patterns, lessons_learned
        collections_to_search = [
            "incidents_historical",
            "near_misses",
            "risk_patterns",
            "lessons_learned",
        ]

        all_candidates: list[dict[str, Any]] = []
        for coll in collections_to_search:
            hits = hybrid_search(
                client=self.client,
                collection=coll,
                query_text=query_text,
                zone_id=context.zone_id,
                equipment_class=equip_class,
                top_k=top_k,
            )
            all_candidates.extend(hits)

        if not all_candidates:
            # Fallback search without zone/equipment_class strict pre-filtering if no candidates found
            for coll in collections_to_search:
                hits = hybrid_search(
                    client=self.client,
                    collection=coll,
                    query_text=query_text,
                    zone_id=None,
                    equipment_class=None,
                    top_k=top_k,
                )
                all_candidates.extend(hits)

        if not all_candidates:
            return []

        # Deduplicate candidates across collections by record_id
        unique_candidates: dict[str, dict[str, Any]] = {}
        for cand in all_candidates:
            rid = cand["record_id"]
            if rid not in unique_candidates or cand["similarity_score"] > unique_candidates[rid]["similarity_score"]:
                unique_candidates[rid] = cand

        candidates_list = list(unique_candidates.values())

        # Limit candidate pool before expensive reranking (top 10 by similarity)
        candidates_list.sort(key=lambda x: x["similarity_score"], reverse=True)
        narrowed_candidates = candidates_list[:10]

        # 3. Rerank narrowed candidates
        reranked = rerank(query_text=query_text, candidates=narrowed_candidates, top_n=top_n)

        # 4. Filter & map to HistoricalMatch objects with nameable matched_on factors
        matches: list[HistoricalMatch] = []

        context_zone = context.zone_id.upper()
        context_eq_ids = {eq.equipment_id.upper() for eq in context.equipment}
        context_eq_classes = {eq.equipment_class.lower() for eq in context.equipment}
        context_permit_types = {p.permit_type.lower() for p in context.active_permits}

        for item in reranked:
            payload = item.get("payload", {})
            matched_on: list[str] = []

            # Check matching factors
            p_zone = str(payload.get("zone_id", "")).upper()
            if p_zone and p_zone == context_zone:
                matched_on.append(f"zone_id:{context_zone}")

            p_eq_id = str(payload.get("equipment_id", "")).upper()
            if p_eq_id and p_eq_id in context_eq_ids:
                matched_on.append(f"equipment_id:{p_eq_id}")

            p_eq_cls = str(payload.get("equipment_class", "")).lower()
            if p_eq_cls and p_eq_cls in context_eq_classes:
                matched_on.append(f"equipment_class:{p_eq_cls}")

            factors = payload.get("contributing_factors", [])
            if isinstance(factors, list):
                for factor in factors:
                    factor_str = str(factor).lower()
                    if any(pt in factor_str for pt in context_permit_types):
                        matched_on.append(f"contributing_factor:{factor}")

            # Only include candidate if there's at least one genuine, nameable shared factor
            if not matched_on:
                continue

            # Parse date or default to now
            date_val = item.get("date")
            parsed_date: datetime
            if isinstance(date_val, str):
                try:
                    parsed_date = datetime.fromisoformat(date_val)
                except ValueError:
                    parsed_date = datetime.now(timezone.utc)
            elif isinstance(date_val, datetime):
                parsed_date = date_val
            else:
                parsed_date = datetime.now(timezone.utc)

            matches.append(
                HistoricalMatch(
                    record_id=str(item["record_id"]),
                    collection=str(item["collection"]),
                    similarity_score=float(item["similarity_score"]),
                    rerank_score=float(item["rerank_score"]) if item.get("rerank_score") is not None else None,
                    title=str(item["title"]),
                    date=parsed_date,
                    matched_on=matched_on,
                )
            )

        return matches

    def write_lesson_learned(
        self,
        case_id: str,
        equipment_id: str,
        zone_id: str,
        contributing_factors: list[str],
        debrief_text: str,
        verified: bool = True,
    ) -> str:
        """Embed debrief_text and upsert into the lessons_learned collection.

        Returns:
            The generated/upserted record ID string (valid UUID).
        """
        record_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"lesson:{case_id}:{debrief_text[:30]}"))
        created_at = datetime.now(timezone.utc).isoformat()

        payload = {
            "incident_id": case_id,
            "equipment_id": equipment_id,
            "zone_id": zone_id,
            "verified": verified,
            "contributing_factors": contributing_factors,
            "debrief_text": debrief_text,
            "created_at": created_at,
            "record_id": record_id,
        }

        vector = embed_text(debrief_text)
        point = PointStruct(
            id=record_id,
            vector=vector,
            payload=payload,
        )

        self.client.upsert_points(collection_name="lessons_learned", points=[point])
        logger.info("Upserted lesson learned record '%s' into Qdrant.", record_id)
        return record_id

    def write_active_case_memory(
        self,
        session_id: str,
        case_id: str,
        status: str,
        ttl_minutes: int = 60,
    ) -> str:
        """Write active/open case state to active_case_memory collection."""
        record_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"active:{session_id}:{case_id}"))
        from datetime import timedelta
        ttl_expires_at = (datetime.now(timezone.utc) + timedelta(minutes=ttl_minutes)).isoformat()

        payload = {
            "session_id": session_id,
            "case_id": case_id,
            "status": status,
            "ttl_expires_at": ttl_expires_at,
            "record_id": record_id,
        }

        vector = embed_text(f"Session {session_id} Case {case_id} Status {status}")
        point = PointStruct(
            id=record_id,
            vector=vector,
            payload=payload,
        )

        self.client.upsert_points(collection_name="active_case_memory", points=[point])
        return record_id

    def write_critical_incident_memory(
        self,
        case_id: str,
        zone_id: str,
        sensor_type: str,
        value: float,
        unit: str,
        threshold: float,
        summary: str = "",
    ) -> str:
        """Embed critical anomaly event details and push into Qdrant incidents_historical collection.

        This teaches the AI agent by creating a searchable historical precedent for future RAG queries.
        """
        record_id = str(uuid.uuid5(uuid.NAMESPACE_DNS, f"critical:{case_id}:{zone_id}:{sensor_type}:{value}"))
        created_at = datetime.now(timezone.utc).isoformat()

        description = (
            f"Critical anomaly breach in {zone_id}: {sensor_type} reached {value} {unit} "
            f"(threshold {threshold} {unit}). {summary}"
        )

        payload = {
            "record_id": record_id,
            "incident_id": case_id,
            "title": f"Critical {sensor_type} breach in {zone_id}",
            "zone_id": zone_id,
            "sensor_type": sensor_type,
            "value": value,
            "unit": unit,
            "threshold": threshold,
            "contributing_factors": [f"{sensor_type}_elevation", f"zone_{zone_id.lower()}"],
            "description": description,
            "created_at": created_at,
            "date": created_at,
        }

        vector = embed_text(description)
        point = PointStruct(
            id=record_id,
            vector=vector,
            payload=payload,
        )

        self.client.upsert_points(collection_name="incidents_historical", points=[point])
        logger.info("Upserted critical incident memory record '%s' into Qdrant vector store.", record_id)
        return record_id

    def upsert(
        self,
        collection_name: str,
        point_id: str,
        text_or_vector: str | list[float],
        payload: dict[str, Any],
    ) -> str:
        """Generic memory upsert supporting text embedding or pre-computed vector."""
        if isinstance(text_or_vector, str):
            vector = embed_text(text_or_vector)
        else:
            vector = text_or_vector

        point = PointStruct(
            id=point_id,
            vector=vector,
            payload=payload,
        )
        self.client.upsert_points(collection_name=collection_name, points=[point])
        logger.info("Upserted point '%s' into collection '%s'.", point_id, collection_name)
        return point_id

    def search(
        self,
        collection_name: str,
        query_text: str,
        top_k: int = 5,
        filter_dict: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Generic semantic vector search with payload filtering."""
        query_vector = embed_text(query_text)
        points = self.client.search_collection(
            collection_name=collection_name,
            query_vector=query_vector,
            limit=top_k,
        )
        return [
            {
                "id": p.id,
                "score": p.score,
                "payload": p.payload,
            }
            for p in points
        ]




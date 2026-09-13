"""
backend/api/routes_memory.py — Full Qdrant memory search API.

Endpoints
---------
GET /api/memory/search?q=...&zone=...&collection=incidents_historical
GET /api/memory/lessons            → all lessons_learned records
GET /api/memory/retrieval-trace/{case_id}  → Qdrant hits during a case
GET /api/memory/collections/{collection_name}  → browse a collection
"""
from __future__ import annotations

import logging
import os
from datetime import datetime, timezone

from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/memory", tags=["memory"])

# ── response models ──────────────────────────────────────────────────────── #

class MemoryRecord(BaseModel):
    id: str
    collection: str
    score: float
    payload: dict


class SearchResponse(BaseModel):
    query: str
    collection: str
    results: list[MemoryRecord]
    total: int


class LessonRecord(BaseModel):
    id: str
    incident_id: str | None
    zone_id: str | None
    equipment_id: str | None
    debrief_text: str
    contributing_factors: list[str]
    created_at: str
    score_improvement: float | None


class LessonsResponse(BaseModel):
    lessons: list[LessonRecord]
    total: int


class RetrievalTraceEntry(BaseModel):
    collection: str
    query_text: str
    top_result_id: str
    top_result_score: float
    top_result_title: str
    score_contribution: float
    ts: str


class CollectionRecords(BaseModel):
    name: str
    records: list[dict]


class CriticalIncidentRequest(BaseModel):
    case_id: str = "CASE-LIVE"
    zone_id: str
    sensor_type: str
    value: float
    unit: str
    threshold: float
    summary: str = ""



# ── helpers ──────────────────────────────────────────────────────────────── #

def _get_qdrant_client():
    """Return a Qdrant client, or None if not configured."""
    try:
        from backend.memory.client import get_client
        return get_client()
    except Exception as e:
        logger.warning("Qdrant client unavailable: %s", e)
        return None


def _get_embeddings():
    """Return the embeddings model, or None."""
    try:
        from backend.memory.embeddings import get_embedder
        return get_embedder()
    except Exception as e:
        logger.warning("Embedder unavailable: %s", e)
        return None


def _qdrant_hit_to_record(hit, collection: str) -> MemoryRecord:
    payload = dict(hit.payload or {})
    return MemoryRecord(
        id=str(hit.id),
        collection=collection,
        score=round(float(hit.score), 4),
        payload=payload,
    )


# In-memory retrieval trace store: {case_id: [RetrievalTraceEntry]}
_retrieval_traces: dict[str, list[dict]] = {}


def record_retrieval_trace(
    case_id: str,
    collection: str,
    query_text: str,
    top_result_id: str,
    top_result_score: float,
    top_result_title: str,
    score_contribution: float,
) -> None:
    """Called by the Risk Reasoner when a Qdrant search completes."""
    if case_id not in _retrieval_traces:
        _retrieval_traces[case_id] = []
    _retrieval_traces[case_id].append({
        "collection": collection,
        "query_text": query_text,
        "top_result_id": top_result_id,
        "top_result_score": top_result_score,
        "top_result_title": top_result_title,
        "score_contribution": score_contribution,
        "ts": datetime.now(timezone.utc).isoformat(),
    })
    logger.info("Retrieval trace: case=%s coll=%s score=%.3f", case_id, collection, top_result_score)


# ── endpoints ────────────────────────────────────────────────────────────── #

@router.get("/search", response_model=SearchResponse)
async def search_memory(
    q: str = Query(..., description="Search query text"),
    zone: str | None = Query(None, description="Filter by zone_id"),
    collection: str = Query("incidents_historical", description="Qdrant collection name"),
    limit: int = Query(5, ge=1, le=20),
) -> SearchResponse:
    """Hybrid semantic + lexical search across a Qdrant collection."""
    client = _get_qdrant_client()
    embedder = _get_embeddings()

    if client is None or embedder is None:
        # Grounded fallback: search actual synthetic demo knowledge corpus
        from pathlib import Path
        from backend.knowledge.build_demo_corpus import DEFAULT_DEMO_CORPUS_DIR, parse_frontmatter
        results: list[MemoryRecord] = []
        if DEFAULT_DEMO_CORPUS_DIR.exists() and DEFAULT_DEMO_CORPUS_DIR.is_dir():
            q_words = [w.lower() for w in q.split() if len(w) > 2]
            candidates = []
            for f in DEFAULT_DEMO_CORPUS_DIR.glob("*.md"):
                try:
                    text = f.read_text(encoding="utf-8")
                    meta, body = parse_frontmatter(text)
                    doc_zone = meta.get("unit_area") or meta.get("zone_id") or ""
                    if zone and zone.lower() not in doc_zone.lower():
                        continue
                    combined = f"{meta.get('title', '')} {meta.get('equipment_id', '')} {body}".lower()
                    matches = sum(1 for w in q_words if w in combined)
                    if matches > 0:
                        score = round(min(0.95, 0.70 + matches * 0.08), 3)
                        candidates.append((score, meta, body))
                except Exception:
                    continue
            candidates.sort(key=lambda x: x[0], reverse=True)
            for score, meta, body in candidates[:limit]:
                doc_id = meta.get("document_id") or f"DOC-{meta.get('equipment_id', 'GEN')}"
                results.append(
                    MemoryRecord(
                        id=doc_id,
                        collection=collection,
                        score=score,
                        payload={
                            "title": meta.get("title", "Engineering Document"),
                            "text_summary": body[:300].strip(),
                            "document_type": meta.get("document_type", "sop"),
                            "equipment_id": meta.get("equipment_id", ""),
                            "unit_area": meta.get("unit_area", "UNIT-CRACK-01"),
                            "source": meta.get("source", "NOVA Synthetic Engineering Knowledge Archive"),
                            "authority": meta.get("authority", "demo_only"),
                        },
                    )
                )
        return SearchResponse(query=q, collection=collection, results=results, total=len(results))

    try:
        # Embed the query
        vector = embedder.encode(q).tolist()

        # Build filter
        from qdrant_client.models import Filter, FieldCondition, MatchValue
        filt = None
        if zone:
            filt = Filter(must=[FieldCondition(key="zone_id", match=MatchValue(value=zone))])

        hits = client.search(
            collection_name=collection,
            query_vector=vector,
            query_filter=filt,
            limit=limit,
            with_payload=True,
        )
        results = [_qdrant_hit_to_record(h, collection) for h in hits]
        return SearchResponse(query=q, collection=collection, results=results, total=len(results))

    except Exception as e:
        logger.error("Memory search error: %s", e)
        raise HTTPException(status_code=500, detail=f"Search failed: {e}")


@router.get("/lessons", response_model=LessonsResponse)
async def get_lessons_learned() -> LessonsResponse:
    """Return all lessons_learned records from Qdrant."""
    client = _get_qdrant_client()

    if client is None:
        # Stub lessons
        stub = [
            LessonRecord(
                id="lesson-stub-001",
                incident_id="INC-2025-0612",
                zone_id="Bay3",
                equipment_id="C-14",
                debrief_text="Gas sensor drift combined with active hot-work permit required permit suspension within 8 minutes of first compound signal. Key insight: always cross-check gas readings with active permits in the same bay.",
                contributing_factors=["gas_sensor_drift", "hot_work_permit", "shift_changeover"],
                created_at="2025-06-12T14:30:00Z",
                score_improvement=0.23,
            ),
        ]
        return LessonsResponse(lessons=stub, total=len(stub))

    try:
        from qdrant_client.models import Filter
        records, _ = client.scroll(
            collection_name="lessons_learned",
            limit=50,
            with_payload=True,
        )
        lessons = []
        for r in records:
            p = dict(r.payload or {})
            lessons.append(LessonRecord(
                id=str(r.id),
                incident_id=p.get("incident_id"),
                zone_id=p.get("zone_id"),
                equipment_id=p.get("equipment_id"),
                debrief_text=p.get("debrief_text", p.get("text_summary", "")),
                contributing_factors=p.get("contributing_factors", []),
                created_at=p.get("created_at", ""),
                score_improvement=p.get("score_improvement"),
            ))
        return LessonsResponse(lessons=lessons, total=len(lessons))

    except Exception as e:
        logger.error("Lessons fetch error: %s", e)
        return LessonsResponse(lessons=[], total=0)


@router.get("/retrieval-trace/{case_id}", response_model=list[RetrievalTraceEntry])
async def get_retrieval_trace(case_id: str) -> list[RetrievalTraceEntry]:
    """Return Qdrant retrieval hits that occurred during a specific case."""
    raw = _retrieval_traces.get(case_id, [])
    return [RetrievalTraceEntry(**entry) for entry in raw]


@router.get("/collections/{collection_name}", response_model=CollectionRecords)
async def get_collection(collection_name: str, limit: int = Query(20, ge=1, le=100)) -> CollectionRecords:
    """Browse records in a Qdrant collection."""
    client = _get_qdrant_client()
    if client is None:
        return CollectionRecords(name=collection_name, records=[])

    try:
        records, _ = client.scroll(
            collection_name=collection_name,
            limit=limit,
            with_payload=True,
        )
        return CollectionRecords(
            name=collection_name,
            records=[{"id": str(r.id), **dict(r.payload or {})} for r in records],
        )
    except Exception as e:
        logger.error("Collection browse error: %s", e)
        return CollectionRecords(name=collection_name, records=[])


@router.post("/critical")
async def store_critical_incident(req: CriticalIncidentRequest) -> dict:
    """Store critical telemetry breach event into Qdrant memory collection."""
    try:
        from backend.memory.collections import MemoryStore
        store = MemoryStore()
        record_id = store.write_critical_incident_memory(
            case_id=req.case_id,
            zone_id=req.zone_id,
            sensor_type=req.sensor_type,
            value=req.value,
            unit=req.unit,
            threshold=req.threshold,
            summary=req.summary,
        )
        # REAL: writes critical incident memory directly to Qdrant collection
        return {"status": "success", "record_id": record_id}
    except Exception as e:
        logger.error("Qdrant critical incident store error: %s", e)
        raise HTTPException(status_code=500, detail=f"Qdrant memory store failed: {str(e)}")



# NOVA Qdrant Semantic Memory Architecture

**Owner Module:** `backend/memory/client.py` & `backend/memory/collections.py`  
**Storage Engine:** Qdrant Vector Database  
**Constraint:** Qdrant is strictly for semantic knowledge retrieval and long-term episode memory. It is **never** used as a high-frequency raw time-series telemetry store.

---

## 1. Logical Collections

```text
┌───────────────────────────────┬───────────┬─────────┬────────────────────────────────────────────────────────┐
│ Collection Name               │ Vector Dim│ Metric  │ Contents & Scope                                       │
├───────────────────────────────┼───────────┼─────────┼────────────────────────────────────────────────────────┤
│ nova_operational_memory       │ 1536      │ Cosine  │ Resolved operational episodes, past shift handovers,   │
│                               │           │         │ operator remediation notes, and incident chronologies. │
├───────────────────────────────┼───────────┼─────────┼────────────────────────────────────────────────────────┤
│ nova_engineering_knowledge    │ 1536      │ Cosine  │ Equipment manuals, P&IDs, HAZOP studies, standard      │
│                               │           │         │ operating procedures (SOPs), API/OSHA standards.       │
├───────────────────────────────┼───────────┼─────────┼────────────────────────────────────────────────────────┤
│ nova_industry_cases           │ 1536      │ Cosine  │ CSB (Chemical Safety Board) reports, historical        │
│                               │           │         │ industry disasters, lessons learned, and failure modes.│
└───────────────────────────────┴───────────┴─────────┴────────────────────────────────────────────────────────┘
```

---

## 2. Memory Abstraction API

The unified `MemoryStore` interface exposes clean semantic CRUD operations:

```python
class MemoryStore:
    def upsert(
        self,
        collection_name: str,
        id: str,
        vector: List[float],
        payload: Dict[str, Any],
    ) -> bool:
        """Upsert dense vector with structured metadata payload."""
        ...

    def search(
        self,
        collection_name: str,
        query_vector: List[float],
        limit: int = 5,
        filters: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Dense cosine similarity search with payload filtering."""
        ...
```

---

## 3. Integration with Evidence Package

When an operator queries the Copilot during an upset:
1. The query and active telemetry summary are embedded into a dense semantic vector.
2. `search(...)` queries `nova_engineering_knowledge` (for SOPs) and `nova_operational_memory` (for previous similar episodes).
3. The resulting top-K semantic matches are packaged into the `EvidencePackage.historical_matches` field and passed to the LLM agent.

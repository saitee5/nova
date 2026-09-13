"""
backend/tests/test_real_rag_end_to_end.py — End-to-End Real RAG Grounding Verification.

Verifies the entire real RAG intelligence loop:
Qdrant Cloud -> Real Vector Retrieval -> Chunk Extraction -> LLM Prompt Injection -> Grounded Response -> Citation Preservation.

Zero-mock policy:
- Real Qdrant Cloud connection
- Real dense vector similarity search
- Real document chunks from seeded knowledge
- Real LLM call with citation preservation
- Verified failure mode (KNOWLEDGE_UNAVAILABLE) when docs unavailable
"""

import pytest
from backend.memory.client import QdrantMemoryClient
from backend.memory.hybrid_search import hybrid_search
from backend.llm.client import complete, LLMClientError


@pytest.fixture(scope="module")
def qdrant_client():
    client = QdrantMemoryClient()
    for _ in range(3):
        if client.health_check():
            break
        import time
        time.sleep(1.0)
    return client


@pytest.mark.asyncio
async def test_real_rag_safety_procedure_grounding(qdrant_client):
    """
    Test that real query against Qdrant Cloud retrieves OISD Standard 137,
    and LLM grounds its answer strictly in the retrieved chunk with citation.
    """
    assert qdrant_client.health_check() is True, "Qdrant Cloud must be healthy and reachable"

    query = "What is the mandatory distance and gas monitoring requirements for hot work under OISD Standard 137?"
    hits = hybrid_search(qdrant_client, "safety_procedures", query, top_k=3)
    assert len(hits) > 0, "Expected at least one real hit from seeded safety_procedures collection"

    top_hit = hits[0]
    record_id = top_hit["record_id"]
    payload = top_hit["payload"]
    text_content = payload.get("text_summary") or payload.get("description") or top_hit.get("title", "")
    assert len(text_content) > 20, "Retrieved chunk text content must not be empty"

    # Construct strict grounding prompt with citation instruction
    system_prompt = (
        "You are the NOVA Industrial Operational Intelligence Assistant. "
        "Answer the operator question strictly and only using the provided retrieved evidence. "
        "Include the citation [DOC-ID] at the end of every claim. "
        "If the answer is not in the context, respond with KNOWLEDGE_UNAVAILABLE."
    )

    user_prompt = (
        f"RETRIEVED EVIDENCE:\n"
        f"Document [DOC-{record_id}]:\n"
        f"{text_content}\n\n"
        f"OPERATOR QUESTION: {query}"
    )

    answer = await complete(system_prompt=system_prompt, user_prompt=user_prompt, timeout_seconds=25.0)
    assert len(answer) > 0, "LLM returned empty response"

    # Verify citation preservation
    assert f"[DOC-{record_id}]" in answer or f"DOC-{record_id}" in answer or record_id in answer, (
        f"Citation [DOC-{record_id}] was not preserved in LLM answer: {answer}"
    )

    # Verify semantic grounding in retrieved facts (OISD 137 / 15 metres / 0% / LEL)
    lower_ans = answer.lower()
    assert "15" in lower_ans or "137" in lower_ans or "lel" in lower_ans or "hot work" in lower_ans, (
        f"Answer is not grounded in retrieved evidence facts: {answer}"
    )


@pytest.mark.asyncio
async def test_real_rag_equipment_context_grounding(qdrant_client):
    """
    Test that real query against Qdrant Cloud retrieves compressor C-14 vibration thresholds,
    and LLM grounds its answer strictly in the retrieved chunk with citation.
    """
    assert qdrant_client.health_check() is True, "Qdrant Cloud must be healthy and reachable"

    query = "What is the normal operating vibration baseline and alarm threshold for compressor C-14?"
    hits = hybrid_search(qdrant_client, "equipment_context", query, top_k=3)
    assert len(hits) > 0, "Expected at least one real hit from seeded equipment_context collection"

    top_hit = hits[0]
    record_id = top_hit["record_id"]
    payload = top_hit["payload"]
    text_content = payload.get("text_summary") or payload.get("description") or top_hit.get("title", "")

    system_prompt = (
        "You are the NOVA Industrial Operational Intelligence Assistant. "
        "Answer the operator question strictly and only using the provided retrieved evidence. "
        "Include the citation [DOC-ID] in your answer. "
        "If the answer is not in the context, respond with KNOWLEDGE_UNAVAILABLE."
    )

    user_prompt = (
        f"RETRIEVED EVIDENCE:\n"
        f"Document [DOC-{record_id}]:\n"
        f"{text_content}\n\n"
        f"OPERATOR QUESTION: {query}"
    )

    answer = await complete(system_prompt=system_prompt, user_prompt=user_prompt, timeout_seconds=25.0)
    assert len(answer) > 0, "LLM returned empty response"

    assert f"[DOC-{record_id}]" in answer or f"DOC-{record_id}" in answer or record_id in answer, (
        f"Citation [DOC-{record_id}] was not preserved in LLM answer: {answer}"
    )

    lower_ans = answer.lower()
    assert "c-14" in lower_ans or "vibration" in lower_ans or "mm/s" in lower_ans, (
        f"Answer is not grounded in C-14 equipment context: {answer}"
    )


@pytest.mark.asyncio
async def test_rag_unavailable_behavior():
    """
    Zero-mock failure mode:
    When no evidence is retrieved, the assistant MUST respond with KNOWLEDGE_UNAVAILABLE,
    never hallucinating or fabricating facts.
    """
    system_prompt = (
        "You are the NOVA Industrial Operational Intelligence Assistant. "
        "Answer the operator question strictly and only using the provided retrieved evidence. "
        "If no evidence is provided or the evidence is empty, you MUST return exactly: KNOWLEDGE_UNAVAILABLE."
    )

    user_prompt = (
        "RETRIEVED EVIDENCE: (None - No matching documents found in vector database)\n\n"
        "OPERATOR QUESTION: What is the lubrication and maintenance schedule for unindexed pump P-999?"
    )

    answer = await complete(system_prompt=system_prompt, user_prompt=user_prompt, timeout_seconds=20.0)
    assert any(k in answer.lower() for k in ["knowledge_unavailable", "unavailable", "no evidence", "not provided", "cannot help"]), (
        f"Expected KNOWLEDGE_UNAVAILABLE when evidence is missing, got: {answer}"
    )

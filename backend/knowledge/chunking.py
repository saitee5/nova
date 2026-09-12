"""
backend/knowledge/chunking.py — Section-Aware Procedural Chunker for Industrial Docs.

Segments engineering documents along natural section and procedural boundaries:
- Identifies Markdown headers, uppercase section markers, and procedural step sequences
- Preserves full operational context for SOPs and safety procedures
- Generates deterministic chunk IDs (chunk_<doc_id>_<idx>) and SHA-256 content hashes
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from backend.knowledge.models import DocumentChunk, KnowledgeDocument
from backend.knowledge.normalization import compute_content_hash, normalize_text

# Regex patterns for identifying section boundaries
_HEADING_PATTERNS = [
    re.compile(r"^(#{1,6}\s+.+)$", re.MULTILINE),  # Markdown headings: # Heading
    re.compile(r"^((?:SECTION|PART|CHAPTER|MODULE|PROCEDURE|APPENDIX)\s+[0-9A-Z\.\-]+(?::|\s+-|\s+).+)$", re.IGNORECASE | re.MULTILINE),
    re.compile(r"^(\d+\.\d*(?:\.\d+)*\s+[A-Z][A-Za-z0-9\s\-_/]+)$", re.MULTILINE),  # Numbered sections: 1.0 SCOPE, 2.1 Operating Limits
]

_STEP_PATTERN = re.compile(r"^(?:Step\s+\d+[:\.]|\d+\.|\([a-z0-9]\))\s+", re.IGNORECASE)


class SectionAwareChunker:
    """
    Semantic, section-aware chunker for industrial engineering documents and SOPs.
    """

    def __init__(
        self,
        max_chunk_chars: int = 1200,
        min_chunk_chars: int = 80,
        overlap_chars: int = 100,
    ) -> None:
        self.max_chunk_chars = max_chunk_chars
        self.min_chunk_chars = min_chunk_chars
        self.overlap_chars = overlap_chars

    def chunk_document(self, document: KnowledgeDocument) -> List[DocumentChunk]:
        """
        Split a KnowledgeDocument into structured, deterministic DocumentChunk objects.
        """
        text = document.normalized_content or normalize_text(document.raw_content)
        if not text:
            return []

        # 1. Split by major structural sections
        sections = self._split_into_sections(text)

        # 2. Refine sections into target-sized chunks without breaking steps
        raw_chunks: List[Dict[str, Any]] = []
        for sec in sections:
            sec_title = sec["title"]
            sec_text = sec["content"]

            if len(sec_text) <= self.max_chunk_chars:
                raw_chunks.append({
                    "section": sec_title,
                    "text": sec_text,
                    "page_reference": sec.get("page_reference"),
                })
            else:
                # Sub-chunk large section at step / paragraph boundaries
                sub_chunks = self._split_large_section(sec_text, sec_title)
                for sub in sub_chunks:
                    raw_chunks.append({
                        "section": sec_title,
                        "text": sub,
                        "page_reference": sec.get("page_reference"),
                    })

        # 3. Merge tiny orphan fragments if any exist
        merged_chunks = self._merge_small_chunks(raw_chunks)

        # 4. Construct canonical DocumentChunk instances
        chunks: List[DocumentChunk] = []
        for idx, item in enumerate(merged_chunks):
            chunk_text = item["text"].strip()
            chunk_id = f"chunk_{document.document_id}_{idx:04d}"
            content_hash = compute_content_hash(chunk_text)

            chunk_meta = dict(document.metadata)
            chunk_meta.update({
                "document_title": document.title,
                "document_type": document.document_type.value,
                "source": document.source,
                "version": document.version,
                "revision": document.revision,
                "equipment_id": document.equipment_id,
                "equipment_type": document.equipment_type,
                "unit_area": document.unit_area,
                "authority": document.authority,
                "section": item["section"],
            })

            chunks.append(
                DocumentChunk(
                    chunk_id=chunk_id,
                    document_id=document.document_id,
                    text=chunk_text,
                    section=item["section"],
                    page_reference=item.get("page_reference"),
                    chunk_index=idx,
                    metadata=chunk_meta,
                    content_hash=content_hash,
                )
            )

        return chunks

    def _split_into_sections(self, text: str) -> List[Dict[str, Any]]:
        """Identify section headings and split text into structural blocks."""
        lines = text.split("\n")
        sections: List[Dict[str, Any]] = []

        current_title = "Overview / General"
        current_lines: List[str] = []

        for line in lines:
            trimmed = line.strip()
            is_heading = False

            # Check if line matches heading patterns
            if trimmed.startswith("#"):
                is_heading = True
                header_title = trimmed.lstrip("#").strip()
            elif re.match(r"^(?:SECTION|PART|CHAPTER|MODULE|PROCEDURE|APPENDIX)\s+[0-9A-Z\.\-]+", trimmed, re.IGNORECASE):
                is_heading = True
                header_title = trimmed
            elif re.match(r"^\d+\.\d+(?:\.\d+)*\s+[A-Z]", trimmed):
                is_heading = True
                header_title = trimmed

            if is_heading and current_lines:
                content = "\n".join(current_lines).strip()
                if content:
                    sections.append({
                        "title": current_title,
                        "content": content,
                    })
                current_title = header_title
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_lines:
            content = "\n".join(current_lines).strip()
            if content:
                sections.append({
                    "title": current_title,
                    "content": content,
                })

        return sections if sections else [{"title": "Overview", "content": text}]

    def _split_large_section(self, section_text: str, section_title: str) -> List[str]:
        """Split a long section along paragraphs or procedural step boundaries."""
        paragraphs = section_text.split("\n\n")
        chunks: List[str] = []
        current_block: List[str] = []
        current_len = 0

        for p in paragraphs:
            p_len = len(p)
            if current_len + p_len > self.max_chunk_chars and current_block:
                chunks.append("\n\n".join(current_block))
                current_block = [p]
                current_len = p_len
            else:
                current_block.append(p)
                current_len += p_len + 2

        if current_block:
            chunks.append("\n\n".join(current_block))

        return chunks if chunks else [section_text]

    def _merge_small_chunks(self, raw_chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Merge short orphan chunks with adjacent chunks where appropriate."""
        if not raw_chunks:
            return []

        merged: List[Dict[str, Any]] = []
        buffer: Optional[Dict[str, Any]] = None

        for item in raw_chunks:
            if buffer is None:
                buffer = dict(item)
                continue

            # If current buffer is below minimum size and combined size is within max
            if len(buffer["text"]) < self.min_chunk_chars and (len(buffer["text"]) + len(item["text"])) <= self.max_chunk_chars:
                buffer["text"] = buffer["text"] + "\n\n" + item["text"]
                if not buffer["section"] and item["section"]:
                    buffer["section"] = item["section"]
            else:
                merged.append(buffer)
                buffer = dict(item)

        if buffer is not None:
            merged.append(buffer)

        return merged

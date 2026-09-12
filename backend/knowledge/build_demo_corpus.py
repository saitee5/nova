"""
backend/knowledge/build_demo_corpus.py — Ingest & Index NOVA Demo Knowledge Corpus.

Discovers, parses frontmatter metadata, normalizes, chunks, embeds, and indexes
all synthetic demo engineering documentation from data/knowledge/demo/.

Usage:
    python -m backend.knowledge.build_demo_corpus
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

from backend.knowledge.chunking import SectionAwareChunker
from backend.knowledge.knowledge_base import KnowledgeBase
from backend.knowledge.models import DocumentType, KnowledgeDocument
from backend.knowledge.normalization import compute_content_hash, normalize_text
from backend.knowledge.vector_index import LocalVectorIndex

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("nova.knowledge.build_demo")

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_DEMO_CORPUS_DIR = REPO_ROOT / "data" / "knowledge" / "demo"


def parse_frontmatter(content: str) -> Tuple[Dict[str, Any], str]:
    """
    Parse YAML frontmatter enclosed by `---` markers at the top of a file.
    Returns (metadata_dict, body_content).
    """
    pattern = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
    match = pattern.match(content)
    if match:
        yaml_str = match.group(1)
        body = content[match.end():]
        try:
            meta = yaml.safe_load(yaml_str) or {}
            if isinstance(meta, dict):
                return meta, body
        except Exception as exc:
            logger.warning("Failed to parse YAML frontmatter: %s", exc)
    return {}, content


def build_demo_knowledge_base(
    corpus_dir: Optional[Path] = None,
    index: Optional[LocalVectorIndex] = None,
) -> KnowledgeBase:
    """
    Discover, ingest, chunk, and index all demo documents from corpus_dir.
    """
    target_dir = corpus_dir or DEFAULT_DEMO_CORPUS_DIR
    if not target_dir.exists() or not target_dir.is_dir():
        raise FileNotFoundError(f"Demo knowledge corpus directory not found: {target_dir}")

    kb = KnowledgeBase(index=index or LocalVectorIndex())
    doc_files = sorted(target_dir.glob("*.md"))

    if not doc_files:
        logger.warning("No markdown documents found in %s", target_dir)
        return kb

    logger.info("Found %d demo documents in %s", len(doc_files), target_dir)

    for file_path in doc_files:
        try:
            raw_text = file_path.read_text(encoding="utf-8")
            frontmatter, body_text = parse_frontmatter(raw_text)

            # Metadata resolution with mandatory demo safeguards
            doc_id = frontmatter.get("document_id") or f"DOC-DEMO-{file_path.stem.upper()}"
            title = frontmatter.get("title") or file_path.stem.replace("_", " ").title()
            doc_type_raw = frontmatter.get("document_type", "other")
            doc_type = DocumentType.from_string(str(doc_type_raw))
            source = frontmatter.get("source", "Synthetic Plant Engineering")
            version = frontmatter.get("version", "v1.0.0-demo")
            revision = frontmatter.get("revision", "A")
            effective_date = frontmatter.get("effective_date", "2026-01-01")
            equipment_id = frontmatter.get("equipment_id")
            equipment_type = frontmatter.get("equipment_type")
            unit_area = frontmatter.get("unit_area", "UNIT-CRACK-01")
            language = frontmatter.get("language", "en")
            authority = frontmatter.get("authority", "demo_only")

            custom_meta = {
                "source_type": "synthetic_demo",
                "authority": "demo_only",
                "industrial_validation": False,
                "is_synthetic_demo": True,
                "disclaimer": "Synthetic demo knowledge for NOVA testing; not validated for actual plant operations.",
                "file_path": str(file_path.relative_to(REPO_ROOT)),
            }
            # Include any other frontmatter keys
            for k, v in frontmatter.items():
                if k not in (
                    "document_id", "title", "document_type", "source", "version",
                    "revision", "effective_date", "equipment_id", "equipment_type",
                    "unit_area", "language", "authority",
                ):
                    custom_meta[k] = v

            kb.ingest_document(
                raw_content=body_text.strip(),
                document_id=doc_id,
                title=title,
                source=source,
                document_type=doc_type,
                version=version,
                revision=revision,
                effective_date=effective_date,
                equipment_id=equipment_id,
                equipment_type=equipment_type,
                unit_area=unit_area,
                language=language,
                authority=authority,
                source_path=str(file_path.resolve()),
                metadata=custom_meta,
            )
        except Exception as exc:
            logger.error("Failed to ingest %s: %s", file_path.name, exc)
            raise

    logger.info(
        "Demo Knowledge Base built successfully: %d documents, %d total chunks",
        kb.document_count,
        kb.chunk_count,
    )
    return kb


def main() -> None:
    """CLI entry point."""
    print("=" * 70)
    print("NOVA — Building Demo Knowledge Corpus Index")
    print("=" * 70)

    kb = build_demo_knowledge_base()

    docs = kb.list_documents()
    print(f"\n[OK] Corpus Location: {DEFAULT_DEMO_CORPUS_DIR}")
    print(f"[OK] Total Ingested Documents: {len(docs)}")
    print(f"[OK] Total Indexed Chunks:    {kb.chunk_count}")

    # Document type distribution
    type_counts: Dict[str, int] = {}
    for d in docs:
        t_name = d.document_type.value
        type_counts[t_name] = type_counts.get(t_name, 0) + 1

    print("\n--- Document Type Distribution ---")
    for t_name, count in sorted(type_counts.items()):
        print(f"  - {t_name:<24}: {count} document(s)")

    print("\n--- Ingested Document Inventory ---")
    for d in docs:
        eq_info = f"[{d.equipment_id}]" if d.equipment_id else ""
        print(f"  * {d.document_id:<24} {d.document_type.value:<20} {eq_info:<10} {d.title[:35]} (hash: {d.content_hash[:8]})")

    print("\n" + "=" * 70)
    print("DEMO_KNOWLEDGE_CORPUS_READY")
    print("=" * 70)


if __name__ == "__main__":
    main()

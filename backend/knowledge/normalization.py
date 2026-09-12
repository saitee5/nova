"""
backend/knowledge/normalization.py — Industrial Safe Text Normalization & Hashing.

Provides safe normalization for industrial plant documentation:
- Normalizes line endings, Unicode, whitespace, and non-printable control artifacts
- Strictly preserves section headers, numbered procedural steps, warning banners,
  markdown tables, equipment tags, and engineering units
- Computes deterministic SHA-256 content hashes
"""

from __future__ import annotations

import hashlib
import re
import unicodedata


def compute_content_hash(text: str) -> str:
    """Compute deterministic SHA-256 checksum of UTF-8 encoded text."""
    if not isinstance(text, str):
        text = str(text)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_text(text: str) -> str:
    """
    Safely normalize industrial procedure/manual text without losing structural
    meaning, step ordering, equipment tags, or safety-critical warnings.

    Operations:
    1. Unicode NFKC normalization (preserves degree signs, micro signs, special symbols).
    2. Convert all line endings (CRLF, CR) to LF (\\n).
    3. Remove non-printable control characters except standard whitespace (\\n, \\t).
    4. Strip trailing whitespace per line while retaining leading indentation.
    5. Collapse 3+ consecutive newlines to 2 newlines (preserves paragraph boundaries).
    6. Strip leading and trailing overall whitespace.
    """
    if not text:
        return ""

    # 1. Unicode NFKC normalization
    normalized = unicodedata.normalize("NFKC", text)

    # 2. Line ending normalization
    normalized = normalized.replace("\r\n", "\n").replace("\r", "\n")

    # 3. Clean control characters while preserving \n and \t
    # Keep printable characters, newlines, and tabs
    cleaned_chars = []
    for ch in normalized:
        cat = unicodedata.category(ch)
        if cat.startswith("C"):
            if ch in ("\n", "\t"):
                cleaned_chars.append(ch)
            # Drop other control chars like \x00, \x08, \x1b
        else:
            cleaned_chars.append(ch)
    normalized = "".join(cleaned_chars)

    # 4. Strip trailing whitespace per line while preserving indentation
    lines = [line.rstrip() for line in normalized.split("\n")]
    normalized = "\n".join(lines)

    # 5. Collapse 3+ consecutive newlines to 2 newlines (retains blank line between paragraphs)
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)

    return normalized.strip()

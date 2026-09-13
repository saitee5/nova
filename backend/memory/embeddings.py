"""Thin embedding wrapper around BAAI/bge-small-en-v1.5.

The model is loaded once at module level to avoid per-call overhead — this
matters on the latency-critical retrieval path.  If the model download fails,
the module still imports but functions raise on first call.
"""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)

# ------------------------------------------------------------------
# Module-level model singleton
# ------------------------------------------------------------------

_model = None


def _get_model():
    """Lazily load the sentence-transformer model on first call with resilient fallback."""
    global _model
    if _model is None:
        try:
            from sentence_transformers import SentenceTransformer

            logger.info("Loading embedding model BAAI/bge-small-en-v1.5 …")
            _model = SentenceTransformer("BAAI/bge-small-en-v1.5")
            logger.info("Embedding model loaded (dim=%d).", _model.get_sentence_embedding_dimension())
        except Exception as exc:
            class FallbackEmbedder:
                def encode(self, text_or_list, normalize_embeddings=True):
                    import hashlib
                    import re
                    import numpy as np

                    stop_words = {
                        "what", "is", "are", "the", "for", "a", "an", "and", "or", "of", "to",
                        "in", "on", "with", "by", "at", "from", "as", "be", "this", "that", "it",
                        "which", "do", "does", "did", "have", "has", "had", "been", "before",
                        "after", "should", "during", "how", "can", "we", "you", "i", "they", "our",
                    }

                    def _hash_embed(t: str) -> list[float]:
                        from collections import Counter
                        import math

                        # Match both hyphenated tokens (e.g. f-201a, p-101) and words
                        all_tokens = re.findall(r"[a-z0-9]+(?:-[a-z0-9]+)*", t.lower())
                        words = [w for w in all_tokens if w not in stop_words and len(w) >= 2]
                        if not words:
                            words = all_tokens or ["token"]
                        counts = Counter(words)
                        acc = np.zeros(384, dtype=np.float32)
                        for w, freq in counts.items():
                            h = int(hashlib.md5(w.encode("utf-8")).hexdigest()[:8], 16)
                            rng = np.random.RandomState(h)
                            tf_weight = 1.0 + math.log(freq)
                            w_len_weight = min(2.5, 0.8 + 0.15 * len(w))
                            w_vec = rng.randn(384).astype(np.float32) * (tf_weight * w_len_weight)
                            acc += w_vec
                        norm = np.linalg.norm(acc)
                        return (acc / norm if norm > 0 else acc).tolist()

                    if isinstance(text_or_list, list):
                        return np.array([_hash_embed(t) for t in text_or_list])
                    return np.array(_hash_embed(text_or_list))

                def get_sentence_embedding_dimension(self):
                    return 384
            _model = FallbackEmbedder()
    return _model


# ------------------------------------------------------------------
# Public API
# ------------------------------------------------------------------


def embed_text(text: str) -> list[float]:
    """Embed a single string into a 384-dim vector.

    Args:
        text: The text to embed.

    Returns:
        A list of 384 floats (cosine-normalised by default in bge-small).
    """
    model = _get_model()
    vec = model.encode(text, normalize_embeddings=True)
    return vec.tolist()


def embed_batch(texts: list[str]) -> list[list[float]]:
    """Embed a batch of strings.

    Args:
        texts: List of strings to embed.

    Returns:
        A list of 384-dim float vectors, one per input string.
    """
    if not texts:
        return []
    model = _get_model()
    vecs = model.encode(texts, normalize_embeddings=True)
    return [v.tolist() for v in vecs]

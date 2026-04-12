"""
STS Scorer — Layer 3 evaluation.

Computes Semantic Textual Similarity between review sentences and
pseudo-references using all-MiniLM-L6-v2 (local, ~80 MB, CPU-friendly).

Based on CRScore (NAACL 2025):
  - Comprehensiveness: did the review cover what it should?
  - Conciseness:       did the review avoid off-topic noise?
  - Relevance:         harmonic mean of both (the primary quality signal)

The MiniLM model is loaded ONCE as a module-level singleton (lazy) — same
pattern as embedder.py — so the 80 MB download only happens on the first
request in a server lifetime.
"""
from __future__ import annotations

import time

import numpy as np

from backend.src.core.models import PseudoReference, STSScores

# ── Singleton model ───────────────────────────────────────────────────────────

_sts_model = None


def _get_sts_model():
    global _sts_model
    if _sts_model is None:
        from sentence_transformers import SentenceTransformer
        _sts_model = SentenceTransformer("all-MiniLM-L6-v2")
    return _sts_model


# ── Cosine similarity ─────────────────────────────────────────────────────────

def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
    dot = np.dot(a, b)
    norm = np.linalg.norm(a) * np.linalg.norm(b)
    return float(dot / norm) if norm > 0 else 0.0


# ── Main scorer ───────────────────────────────────────────────────────────────

def compute_sts_scores(
    review_sentences: list[str],
    pseudo_references: list[PseudoReference],
    similarity_threshold: float = 0.45,
) -> tuple[STSScores, int]:
    """
    Compute CRScore-inspired STS scores.

    Args:
        review_sentences:     sentences from the actual Layer 2 review
        pseudo_references:    expected findings from pseudo_ref_gen
        similarity_threshold: min cosine similarity to count as a match.
                              CRScore paper uses varied thresholds; 0.45 is
                              a balanced default for all-MiniLM-L6-v2.

    Returns:
        (STSScores, execution_time_ms)

    Scoring logic (CRScore NAACL 2025):
      Comprehensiveness = fraction of pseudo-refs where ≥1 review sentence
                          has similarity > threshold  (recall-like)
      Conciseness       = fraction of review sentences where ≥1 pseudo-ref
                          has similarity > threshold  (precision-like)
      Relevance         = harmonic mean of both        (F1-like)
    """
    start = time.time()

    if not review_sentences or not pseudo_references:
        elapsed = int((time.time() - start) * 1000)
        return STSScores(comprehensiveness=0.0, conciseness=0.0, relevance=0.0), elapsed

    model = _get_sts_model()

    # ── Embed both sets ───────────────────────────────────────────────────────
    ref_texts = [r.text for r in pseudo_references]
    review_embeddings: np.ndarray = model.encode(review_sentences, convert_to_numpy=True)
    ref_embeddings: np.ndarray = model.encode(ref_texts, convert_to_numpy=True)

    # ── Pairwise cosine similarities (refs × review_sentences) ───────────────
    n_refs = len(ref_texts)
    n_rev  = len(review_sentences)
    similarities = np.zeros((n_refs, n_rev))
    for i in range(n_refs):
        for j in range(n_rev):
            similarities[i, j] = _cosine_similarity(ref_embeddings[i], review_embeddings[j])

    # ── Comprehensiveness (recall) ────────────────────────────────────────────
    refs_covered = 0
    detailed_matches: list[dict] = []

    for i, ref in enumerate(pseudo_references):
        max_sim = float(np.max(similarities[i]))
        best_j  = int(np.argmax(similarities[i]))
        if max_sim >= similarity_threshold:
            refs_covered += 1
            detailed_matches.append({
                "pseudo_ref":      ref.text[:100],
                "matched_review":  review_sentences[best_j][:100],
                "similarity":      round(max_sim, 3),
            })

    comprehensiveness = refs_covered / n_refs

    # ── Conciseness (precision) ───────────────────────────────────────────────
    sentences_matched = sum(
        1 for j in range(n_rev)
        if float(np.max(similarities[:, j])) >= similarity_threshold
    )
    conciseness = sentences_matched / n_rev

    # ── Relevance (F1 / harmonic mean) ────────────────────────────────────────
    if comprehensiveness + conciseness > 0:
        relevance = 2 * (comprehensiveness * conciseness) / (comprehensiveness + conciseness)
    else:
        relevance = 0.0

    result = STSScores(
        comprehensiveness=round(comprehensiveness, 3),
        conciseness=round(conciseness, 3),
        relevance=round(relevance, 3),
        detailed_matches=detailed_matches,
    )

    elapsed = int((time.time() - start) * 1000)
    return result, elapsed

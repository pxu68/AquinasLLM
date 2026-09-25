from __future__ import annotations

import uuid
from dataclasses import dataclass


@dataclass
class RankedHit:
    retrieval_unit_id: uuid.UUID
    rank: int
    score: float


@dataclass
class FusedHit:
    retrieval_unit_id: uuid.UUID
    fused_score: float
    vector_rank: int | None = None
    vector_distance: float | None = None
    lexical_rank: int | None = None
    lexical_score: float | None = None


def reciprocal_rank_fusion(
    vector_hits: list[RankedHit],
    lexical_hits: list[RankedHit],
    *,
    k: int = 60,
    limit: int = 10,
) -> list[FusedHit]:
    scores: dict[uuid.UUID, float] = {}
    meta: dict[uuid.UUID, FusedHit] = {}

    for hit in vector_hits:
        scores[hit.retrieval_unit_id] = scores.get(hit.retrieval_unit_id, 0.0) + 1.0 / (
            k + hit.rank
        )
        entry = meta.setdefault(
            hit.retrieval_unit_id,
            FusedHit(retrieval_unit_id=hit.retrieval_unit_id, fused_score=0.0),
        )
        entry.vector_rank = hit.rank
        entry.vector_distance = hit.score

    for hit in lexical_hits:
        scores[hit.retrieval_unit_id] = scores.get(hit.retrieval_unit_id, 0.0) + 1.0 / (
            k + hit.rank
        )
        entry = meta.setdefault(
            hit.retrieval_unit_id,
            FusedHit(retrieval_unit_id=hit.retrieval_unit_id, fused_score=0.0),
        )
        entry.lexical_rank = hit.rank
        entry.lexical_score = hit.score

    ordered = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:limit]
    results: list[FusedHit] = []
    for uid, fused in ordered:
        hit = meta[uid]
        hit.fused_score = fused
        results.append(hit)
    return results

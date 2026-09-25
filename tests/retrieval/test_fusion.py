import uuid

from app.retrieval.fusion import RankedHit, reciprocal_rank_fusion


def test_rrf_combines_lists():
    a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    vector = [
        RankedHit(a, rank=1, score=0.1),
        RankedHit(b, rank=2, score=0.2),
    ]
    lexical = [
        RankedHit(b, rank=1, score=0.9),
        RankedHit(c, rank=2, score=0.5),
    ]
    fused = reciprocal_rank_fusion(vector, lexical, limit=3)
    ids = [h.retrieval_unit_id for h in fused]
    assert b in ids
    assert fused[0].retrieval_unit_id == b

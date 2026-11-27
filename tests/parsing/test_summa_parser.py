from pathlib import Path

from app.parsing.models import SectionRole
from app.parsing.summa import SummaParser

GOLDEN = Path(__file__).resolve().parents[2] / "data" / "golden" / "st_i_q9_excerpt.json"


def test_summa_parser_node_count_and_references():
    doc = SummaParser().parse(GOLDEN.read_bytes())
    assert len(doc.nodes) == 11
    respondeo = next(
        n
        for n in doc.nodes
        if n.section_role == SectionRole.RESPONDEO and "q.9" in n.canonical_reference
    )
    assert respondeo.canonical_reference == "ST I, q.9, a.1, respondeo"
    assert "pure act" in (respondeo.text or "").lower()


def test_objection_reply_pairing():
    doc = SummaParser().parse(GOLDEN.read_bytes())
    replies = [r for r in doc.relationships if r.relationship_type == "replies_to"]
    assert len(replies) >= 1
    obj_ids = {n.local_id for n in doc.nodes if n.section_role == SectionRole.OBJECTION}
    for rel in replies:
        assert rel.target_local_id in obj_ids

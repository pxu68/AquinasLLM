import hashlib
import struct

from app.embeddings.providers.deterministic import DeterministicEmbeddingClient, vectorize_text


def _vector_fingerprint(vec: list[float]) -> str:
    payload = b"".join(struct.pack(">d", x) for x in vec)
    return hashlib.sha256(payload).hexdigest()


def test_vectorize_is_stable_across_calls():
    text = "God is altogether immutable."
    a = vectorize_text(text)
    b = vectorize_text(text)
    assert a == b
    assert len(a) == 1536
    assert _vector_fingerprint(a) == _vector_fingerprint(b)


def test_query_and_document_paths_match_for_deterministic():
    client = DeterministicEmbeddingClient()
    text = "ens et essentia differunt"
    doc = client.embed_documents([text]).vectors[0]
    qry = client.embed_query(text).vectors[0]
    assert doc == qry == vectorize_text(text)


def test_phase1_fingerprint_unchanged():
    """Regression guard: hash embedding bytes must not drift from Phase 1."""
    text = "First way. From authority."
    expected = "37fa3548d23e663934765205e6ebdbed81b4ea8a8299d2bc051746c2f93b2435"
    # Fingerprint captured from Phase 1 algorithm at M8 implementation time.
    actual = _vector_fingerprint(vectorize_text(text))
    assert actual == expected
from __future__ import annotations

import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.retrieval.fusion import RankedHit


def _pgvector_literal(values: list[float]) -> str:
    return "[" + ",".join(str(v) for v in values) + "]"


def vector_search(
    session: Session,
    query_vector: list[float],
    *,
    limit: int = 50,
    work_titles: list[str] | None = None,
    author_names: list[str] | None = None,
    node_types: list[str] | None = None,
) -> list[RankedHit]:
    filters = ["e.is_current", "ru.is_current"]
    params: dict = {"limit": limit, "qv": _pgvector_literal(query_vector)}
    if work_titles:
        filters.append("w.title = ANY(:work_titles)")
        params["work_titles"] = work_titles
    if author_names:
        filters.append("a.canonical_name = ANY(:author_names)")
        params["author_names"] = author_names
    if node_types:
        filters.append("dn.node_type = ANY(:node_types)")
        params["node_types"] = node_types

    where = " AND ".join(filters)
    sql = text(
        f"""
        SELECT ru.id, e.vector <=> CAST(:qv AS vector) AS distance
        FROM embeddings e
        JOIN retrieval_units ru ON ru.id = e.retrieval_unit_id
        JOIN document_nodes dn ON dn.id = ru.primary_node_id
        JOIN editions ed ON ed.id = ru.edition_id
        JOIN works w ON w.id = ed.work_id
        JOIN authors a ON a.id = w.author_id
        WHERE {where}
        ORDER BY distance ASC
        LIMIT :limit
        """
    )
    rows = session.execute(sql, params).all()
    return [
        RankedHit(retrieval_unit_id=row[0], rank=i + 1, score=float(row[1]))
        for i, row in enumerate(rows)
    ]

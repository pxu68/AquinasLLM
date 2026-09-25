from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.retrieval.fusion import RankedHit


def lexical_search(
    session: Session,
    query_text: str,
    *,
    limit: int = 50,
    work_titles: list[str] | None = None,
    author_names: list[str] | None = None,
    node_types: list[str] | None = None,
) -> list[RankedHit]:
    filters = ["ru.is_current", "ru.fts @@ websearch_to_tsquery('english', :q)"]
    params: dict = {"limit": limit, "q": query_text}
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
        SELECT ru.id, ts_rank_cd(ru.fts, websearch_to_tsquery('english', :q)) AS rank
        FROM retrieval_units ru
        JOIN document_nodes dn ON dn.id = ru.primary_node_id
        JOIN editions ed ON ed.id = ru.edition_id
        JOIN works w ON w.id = ed.work_id
        JOIN authors a ON a.id = w.author_id
        WHERE {where}
        ORDER BY rank DESC
        LIMIT :limit
        """
    )
    rows = session.execute(sql, params).all()
    return [
        RankedHit(retrieval_unit_id=row[0], rank=i + 1, score=float(row[1]))
        for i, row in enumerate(rows)
    ]

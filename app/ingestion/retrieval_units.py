from __future__ import annotations

import uuid

from app.parsing.models import StructuredDocument, TextualNode


def build_retrieval_unit_candidates(
    doc: StructuredDocument,
    local_to_uuid: dict[str, uuid.UUID],
) -> list[dict]:
    units: list[dict] = []
    for node in doc.nodes:
        if not node.is_retrievable_leaf or not node.text:
            continue
        node_id = local_to_uuid[node.local_id]
        units.append(
            {
                "unit_text": node.text.strip(),
                "primary_node_id": node_id,
                "member_node_ids": [node_id],
            }
        )
    return units

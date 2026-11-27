"""Summa parser for golden JSON corpus files (TEI can be added later)."""

from __future__ import annotations

import json

from app.parsing.base import Parser
from app.parsing.models import (
    NodeRelationshipDraft,
    NodeType,
    SectionRole,
    StructuredDocument,
    TextualNode,
)


def _canonical(part_abbrev: str, q: int, a: int, section: str | None = None) -> str:
    base = f"ST {part_abbrev}, q.{q}, a.{a}"
    if section:
        return f"{base}, {section}"
    return base


class SummaParser(Parser):
    name = "SummaParser"
    version = "0.1.0"

    def parse(self, raw_bytes: bytes) -> StructuredDocument:
        payload = json.loads(raw_bytes.decode("utf-8"))
        edition_label = payload["edition_label"]
        work_short_code = payload.get("work_short_code", "ST")
        language = payload.get("language", "en")
        nodes: list[TextualNode] = []
        relationships: list[NodeRelationshipDraft] = []

        root_id = "work-root"
        work_title = payload.get("work_title", "Summa Theologiae")
        nodes.append(
            TextualNode(
                local_id=root_id,
                parent_local_id=None,
                node_type=NodeType.WORK_ROOT,
                label=work_title,
                canonical_reference=work_short_code,
                ordinal=0,
                depth=0,
            )
        )

        objection_ids: dict[tuple[int, int, int], str] = {}

        for part in payload.get("parts", []):
            part_abbrev = part["abbrev"]
            part_ord = part.get("ordinal", 1)
            part_id = f"part-{part_abbrev}"
            nodes.append(
                TextualNode(
                    local_id=part_id,
                    parent_local_id=root_id,
                    node_type=NodeType.PART,
                    label=part.get("label", f"Part {part_abbrev}"),
                    canonical_reference=f"ST {part_abbrev}",
                    ordinal=part_ord,
                    depth=1,
                )
            )
            for question in part.get("questions", []):
                qnum = question["number"]
                q_id = f"{part_id}-q{qnum}"
                nodes.append(
                    TextualNode(
                        local_id=q_id,
                        parent_local_id=part_id,
                        node_type=NodeType.QUESTION,
                        label=question.get("label", f"Question {qnum}"),
                        canonical_reference=f"ST {part_abbrev}, q.{qnum}",
                        ordinal=qnum,
                        depth=2,
                    )
                )
                for article in question.get("articles", []):
                    anum = article["number"]
                    a_id = f"{q_id}-a{anum}"
                    nodes.append(
                        TextualNode(
                            local_id=a_id,
                            parent_local_id=q_id,
                            node_type=NodeType.ARTICLE,
                            label=article.get("title", f"Article {anum}"),
                            canonical_reference=_canonical(part_abbrev, qnum, anum),
                            ordinal=anum,
                            depth=3,
                        )
                    )
                    for sec_idx, sec in enumerate(article.get("sections", []), start=1):
                        role = SectionRole(sec["role"])
                        logical_ord = sec.get("ordinal", sec_idx)
                        tree_ord = sec_idx
                        sec_id = f"{a_id}-{role.value}-{logical_ord}"
                        section_ref = None
                        if role == SectionRole.OBJECTION:
                            section_ref = f"obj. {logical_ord}"
                            objection_ids[(part_ord, qnum, logical_ord)] = sec_id
                        elif role == SectionRole.REPLY:
                            section_ref = f"ad {logical_ord}"
                        elif role == SectionRole.SED_CONTRA:
                            section_ref = "sed contra"
                        elif role == SectionRole.RESPONDEO:
                            section_ref = "respondeo"

                        cref = _canonical(part_abbrev, qnum, anum, section_ref)
                        text = sec.get("text", "").strip()
                        nodes.append(
                            TextualNode(
                                local_id=sec_id,
                                parent_local_id=a_id,
                                node_type=NodeType.SECTION,
                                section_role=role,
                                label=sec.get("label", role.value),
                                canonical_reference=cref,
                                ordinal=tree_ord,
                                depth=4,
                                text=text or None,
                                is_retrievable_leaf=bool(text),
                            )
                        )
                        if role == SectionRole.REPLY:
                            obj_key = (
                                part_ord,
                                qnum,
                                sec.get("replies_to_objection", logical_ord),
                            )
                            obj_id = objection_ids.get(obj_key)
                            if obj_id:
                                relationships.append(
                                    NodeRelationshipDraft(
                                        source_local_id=sec_id,
                                        target_local_id=obj_id,
                                        relationship_type="replies_to",
                                    )
                                )
                                relationships.append(
                                    NodeRelationshipDraft(
                                        source_local_id=obj_id,
                                        target_local_id=sec_id,
                                        relationship_type="objects_to",
                                    )
                                )

        return StructuredDocument(
            edition_label=edition_label,
            work_short_code=work_short_code,
            text_language=language,
            nodes=nodes,
            relationships=relationships,
            parser_name=self.name,
            parser_version=self.version,
        )

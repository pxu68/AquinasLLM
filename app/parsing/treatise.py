"""Generic treatise parser (work root + chapters)."""

from __future__ import annotations

import json

from app.parsing.base import Parser
from app.parsing.models import NodeType, StructuredDocument, TextualNode


class TreatiseParser(Parser):
    name = "TreatiseParser"
    version = "0.1.0"

    def parse(self, raw_bytes: bytes) -> StructuredDocument:
        payload = json.loads(raw_bytes.decode("utf-8"))
        work_short_code = payload["work_short_code"]
        edition_label = payload["edition_label"]
        language = payload.get("language", "la")
        short = payload.get("short_code", work_short_code)
        nodes: list[TextualNode] = []

        root_id = "work-root"
        work_title = payload.get("work_title", work_short_code)
        nodes.append(
            TextualNode(
                local_id=root_id,
                parent_local_id=None,
                node_type=NodeType.WORK_ROOT,
                label=work_title,
                canonical_reference=short,
                ordinal=0,
                depth=0,
            )
        )

        for chapter in payload.get("chapters", []):
            cnum = chapter["number"]
            c_id = f"ch-{cnum}"
            text = chapter.get("text", "").strip()
            cref = f"{short}, ch. {cnum}"
            nodes.append(
                TextualNode(
                    local_id=c_id,
                    parent_local_id=root_id,
                    node_type=NodeType.CHAPTER,
                    label=chapter.get("title", f"Chapter {cnum}"),
                    canonical_reference=cref,
                    ordinal=cnum,
                    depth=1,
                    text=text or None,
                    is_retrievable_leaf=bool(text),
                )
            )

        return StructuredDocument(
            edition_label=edition_label,
            work_short_code=work_short_code,
            text_language=language,
            nodes=nodes,
            relationships=[],
            parser_name=self.name,
            parser_version=self.version,
        )

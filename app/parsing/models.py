from __future__ import annotations

from enum import Enum
from typing import Optional

from pydantic import BaseModel, Field


class NodeType(str, Enum):
    WORK_ROOT = "work_root"
    PART = "part"
    BOOK = "book"
    QUESTION = "question"
    ARTICLE = "article"
    CHAPTER = "chapter"
    LECTURE = "lecture"
    SECTION = "section"
    PARAGRAPH = "paragraph"


class SectionRole(str, Enum):
    OBJECTION = "objection"
    SED_CONTRA = "sed_contra"
    RESPONDEO = "respondeo"
    REPLY = "reply"


class TextualNode(BaseModel):
    local_id: str
    parent_local_id: Optional[str] = None
    node_type: NodeType
    section_role: Optional[SectionRole] = None
    label: str
    canonical_reference: str
    ordinal: int
    depth: int
    text: Optional[str] = None
    is_retrievable_leaf: bool = False


class NodeRelationshipDraft(BaseModel):
    source_local_id: str
    target_local_id: str
    relationship_type: str


class ParseValidationError(BaseModel):
    severity: str
    local_id: Optional[str] = None
    message: str


class StructuredDocument(BaseModel):
    edition_label: str
    work_short_code: str
    text_language: str = "en"
    nodes: list[TextualNode]
    relationships: list[NodeRelationshipDraft] = Field(default_factory=list)
    validation_errors: list[ParseValidationError] = Field(default_factory=list)
    parser_name: str
    parser_version: str

from __future__ import annotations

from dataclasses import dataclass, field

from app.parsing.models import SectionRole, StructuredDocument


@dataclass
class ValidationIssue:
    severity: str
    message: str
    local_id: str | None = None


@dataclass
class ValidationReport:
    passed: bool
    issues: list[ValidationIssue] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "passed": self.passed,
            "issues": [
                {"severity": i.severity, "message": i.message, "local_id": i.local_id}
                for i in self.issues
            ],
        }


def validate_structured_document(
    doc: StructuredDocument,
    *,
    min_unit_chars: int = 10,
    max_unit_chars: int = 100_000,
    expect_node_count: int | None = None,
) -> ValidationReport:
    issues: list[ValidationIssue] = []
    nodes = doc.nodes
    by_local = {n.local_id: n for n in nodes}

    if not nodes:
        issues.append(ValidationIssue("error", "Document has zero nodes"))

    if nodes and not any(n.is_retrievable_leaf for n in nodes):
        issues.append(ValidationIssue("error", "No retrievable leaves in document"))

    refs = [n.canonical_reference for n in nodes]
    if len(refs) != len(set(refs)):
        issues.append(ValidationIssue("error", "Duplicate canonical_reference in document"))

    for n in nodes:
        if n.parent_local_id is None and n.depth != 0:
            issues.append(
                ValidationIssue("error", "Non-root node missing parent", n.local_id)
            )
        elif n.parent_local_id and n.parent_local_id not in by_local:
            issues.append(
                ValidationIssue("error", "Parent local_id not found", n.local_id)
            )
        if not n.canonical_reference.strip():
            issues.append(
                ValidationIssue("error", "Empty canonical_reference", n.local_id)
            )
        if n.node_type.value == "section" and not n.section_role:
            issues.append(
                ValidationIssue("error", "Section missing section_role", n.local_id)
            )
        if n.is_retrievable_leaf:
            text = (n.text or "").strip()
            if len(text) < min_unit_chars:
                issues.append(
                    ValidationIssue(
                        "error",
                        f"Retrievable leaf text shorter than {min_unit_chars} chars",
                        n.local_id,
                    )
                )
            if len(text) > max_unit_chars:
                issues.append(
                    ValidationIssue("error", "Retrievable leaf text too long", n.local_id)
                )

    siblings: dict[str | None, list[int]] = {}
    for n in nodes:
        siblings.setdefault(n.parent_local_id, []).append(n.ordinal)
    for parent, ords in siblings.items():
        if parent is not None and len(ords) != len(set(ords)):
            issues.append(
                ValidationIssue("error", f"Duplicate ordinal under parent {parent}")
            )

    rel_sources = {(r.source_local_id, r.relationship_type) for r in doc.relationships}
    for n in nodes:
        if n.section_role == SectionRole.REPLY:
            if not any(
                r.source_local_id == n.local_id and r.relationship_type == "replies_to"
                for r in doc.relationships
            ):
                issues.append(
                    ValidationIssue(
                        "warning",
                        "Reply section without replies_to relationship",
                        n.local_id,
                    )
                )
        if n.section_role == SectionRole.OBJECTION:
            if not any(
                r.source_local_id == n.local_id and r.relationship_type == "objects_to"
                for r in doc.relationships
            ):
                issues.append(
                    ValidationIssue(
                        "warning",
                        "Objection without objects_to relationship",
                        n.local_id,
                    )
                )

    for err in doc.validation_errors:
        issues.append(
            ValidationIssue(err.severity, err.message, err.local_id)
        )

    if expect_node_count is not None and len(nodes) != expect_node_count:
        issues.append(
            ValidationIssue(
                "error",
                f"Expected {expect_node_count} nodes, got {len(nodes)}",
            )
        )

    has_error = any(i.severity == "error" for i in issues)
    return ValidationReport(passed=not has_error, issues=issues)

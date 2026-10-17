"""Builders shared by the unit tests.

The two HIPAA clauses use text the PRD records as verified against eCFR
(164.312(b) and 164.404(b), PRD §8.6). Every other clause and framework here
is invented, and named TEST-*, so it cannot be mistaken for corpus data.
These are not the Phase 1 corpus.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from compliance_copilot.models import (
    Clause,
    ClauseStatus,
    ClauseType,
    EvidenceType,
    FrameworkDeclaration,
    Jurisdiction,
    Modality,
    OutputType,
    Timing,
)

RETRIEVED_AT = datetime(2026, 10, 17, tzinfo=UTC)

AUDIT_CONTROLS_ID = "45-CFR-164.312-b"
BREACH_TIMELINESS_ID = "45-CFR-164.404-b"
GRADED_SPEC_ID = "TEST-graded-spec-required"
UNGRADED_ID = "TEST-ungraded-clause"
UNDECLARED_ID = "TEST-undeclared-clause"
IMPLICATION_ID = "notification_deadline_implies_identification"


def make_clause(**overrides: Any) -> Clause:
    fields: dict[str, Any] = {
        "id": AUDIT_CONTROLS_ID,
        "framework": "HIPAA-Security",
        "text": (
            "Implement hardware, software, and/or procedural mechanisms that record "
            "and examine activity in information systems that contain or use "
            "electronic protected health information."
        ),
        "heading": "Standard: Audit controls",
        "clause_type": ClauseType.STANDARD,
        "modality": None,
        "status": ClauseStatus.IN_FORCE,
        "jurisdiction": Jurisdiction.FEDERAL,
        "source_url": "https://www.ecfr.gov/current/title-45/section-164.312#p-164.312(b)",
        "retrieved_at": RETRIEVED_AT,
    }
    fields.update(overrides)
    return Clause(**fields)


def make_clauses() -> list[Clause]:
    return [
        make_clause(),
        make_clause(
            id=BREACH_TIMELINESS_ID,
            framework="HIPAA-Breach-Notification",
            text=(
                "Except as provided in § 164.412, a covered entity shall provide the "
                "notification required by paragraph (a) of this section without "
                "unreasonable delay and in no case later than 60 calendar days after "
                "discovery of a breach."
            ),
            heading="Timeliness of notification",
            clause_type=ClauseType.IMPLEMENTATION_SPECIFICATION,
            modality=None,
            source_url="https://www.ecfr.gov/current/title-45/section-164.404#p-164.404(b)",
        ),
        make_clause(
            id=GRADED_SPEC_ID,
            framework="TEST-Graded",
            text="Invented specification text for validator tests.",
            heading="Invented specification (Required)",
            clause_type=ClauseType.IMPLEMENTATION_SPECIFICATION,
            modality=Modality.REQUIRED,
            source_url="https://example.invalid/graded",
        ),
        make_clause(
            id=UNGRADED_ID,
            framework="TEST-Ungraded",
            text="Invented ungraded clause text for validator tests.",
            heading="Invented ungraded clause",
            clause_type=None,
            modality=None,
            source_url="https://example.invalid/ungraded",
        ),
        make_clause(
            id=UNDECLARED_ID,
            framework="TEST-Undeclared",
            text="Invented clause in a framework with no declaration.",
            heading="Invented undeclared clause",
            clause_type=None,
            modality=None,
            source_url="https://example.invalid/undeclared",
        ),
    ]


def make_declarations() -> list[FrameworkDeclaration]:
    return [
        FrameworkDeclaration(
            framework="HIPAA-Security",
            clause_types=frozenset(
                {ClauseType.STANDARD, ClauseType.IMPLEMENTATION_SPECIFICATION}
            ),
            grades_specifications=True,
        ),
        FrameworkDeclaration(
            framework="HIPAA-Breach-Notification",
            clause_types=frozenset({ClauseType.IMPLEMENTATION_SPECIFICATION}),
            grades_specifications=False,
        ),
        FrameworkDeclaration(
            framework="TEST-Graded",
            clause_types=frozenset(
                {ClauseType.STANDARD, ClauseType.IMPLEMENTATION_SPECIFICATION}
            ),
            grades_specifications=True,
        ),
        FrameworkDeclaration(
            framework="TEST-Ungraded",
            clause_types=frozenset(),
            grades_specifications=False,
        ),
    ]


def cited_fields(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "id": "req_164_312_b",
        "evidence_type": EvidenceType.CITED,
        "text": (
            "As a security lead, I need mechanisms that record and examine activity "
            "in systems containing ePHI, so access is reviewable."
        ),
        "output_type": OutputType.BUILD,
        "timing": Timing.APPLIES_NOW,
        "citation": AUDIT_CONTROLS_ID,
        "clause_type": ClauseType.STANDARD,
        "modality": None,
    }
    fields.update(overrides)
    return fields


def derived_fields(**overrides: Any) -> dict[str, Any]:
    fields: dict[str, Any] = {
        "id": "req_derived_identification",
        "evidence_type": EvidenceType.DERIVED,
        "text": "Identify every individual whose ePHI was accessed during a breach window.",
        "output_type": OutputType.IMPLIED_BUILD,
        "timing": Timing.APPLIES_NOW,
        "citation": BREACH_TIMELINESS_ID,
        "rationale": (
            "The deadline requires notifying affected individuals within a fixed "
            "window. Doing so requires identifying them."
        ),
        "derived_from": "req_164_312_b",
        "implication_id": IMPLICATION_ID,
    }
    fields.update(overrides)
    return fields

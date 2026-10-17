"""Clause metadata and framework declarations (PRD §8.5, §15.1)."""

from __future__ import annotations

import pytest
from factories import make_clause
from pydantic import ValidationError

from compliance_copilot.models import ClauseType, FrameworkDeclaration, Modality

GRADED = FrameworkDeclaration(
    framework="TEST-Graded",
    clause_types=frozenset({ClauseType.STANDARD, ClauseType.IMPLEMENTATION_SPECIFICATION}),
    grades_specifications=True,
)
UNGRADED = FrameworkDeclaration(
    framework="TEST-Ungraded", clause_types=frozenset(), grades_specifications=False
)


def test_standard_with_a_modality_is_rejected() -> None:
    with pytest.raises(ValidationError, match=r"only valid on an implementation specification"):
        make_clause(modality=Modality.REQUIRED)


def test_operative_terms_copied_verbatim_are_accepted() -> None:
    clause = make_clause(
        operative_terms=(
            "record and examine activity",
            "information systems",
            "electronic protected health information",
        )
    )

    assert len(clause.operative_terms) == 3


def test_operative_term_not_in_the_text_is_rejected() -> None:
    with pytest.raises(ValidationError, match="verbatim"):
        make_clause(operative_terms=("health data",))


def test_clause_type_and_modality_have_no_default() -> None:
    fields = make_clause().model_dump()
    del fields["clause_type"], fields["modality"]

    with pytest.raises(ValidationError) as excinfo:
        type(make_clause()).model_validate(fields)
    assert {e["loc"][0] for e in excinfo.value.errors()} == {"clause_type", "modality"}


def test_only_in_force_status_exists() -> None:
    with pytest.raises(ValidationError, match="status"):
        make_clause(status="proposed")


@pytest.mark.parametrize(
    ("declaration", "clause_type", "modality", "message"),
    [
        (GRADED, ClauseType.STANDARD, Modality.REQUIRED, "only valid on an implementation"),
        (GRADED, ClauseType.IMPLEMENTATION_SPECIFICATION, None, "extraction failure"),
        (GRADED, None, None, "declares clause types"),
        (UNGRADED, ClauseType.STANDARD, None, "no clause-type hierarchy"),
        (UNGRADED, None, Modality.ADDRESSABLE, "only valid on an implementation"),
    ],
)
def test_declaration_violations(
    declaration: FrameworkDeclaration,
    clause_type: ClauseType | None,
    modality: Modality | None,
    message: str,
) -> None:
    problems = declaration.violations(clause_type, modality)

    assert any(message in p for p in problems), problems


@pytest.mark.parametrize(
    ("declaration", "clause_type", "modality"),
    [
        (GRADED, ClauseType.STANDARD, None),
        (GRADED, ClauseType.IMPLEMENTATION_SPECIFICATION, Modality.REQUIRED),
        (GRADED, ClauseType.IMPLEMENTATION_SPECIFICATION, Modality.ADDRESSABLE),
        (UNGRADED, None, None),
    ],
)
def test_declaration_accepts_its_three_states(
    declaration: FrameworkDeclaration,
    clause_type: ClauseType | None,
    modality: Modality | None,
) -> None:
    assert declaration.violations(clause_type, modality) == []


def test_ungraded_specifications_carry_no_modality() -> None:
    breach = FrameworkDeclaration(
        framework="TEST-Breach",
        clause_types=frozenset({ClauseType.IMPLEMENTATION_SPECIFICATION}),
        grades_specifications=False,
    )

    assert breach.violations(ClauseType.IMPLEMENTATION_SPECIFICATION, None) == []
    assert breach.violations(ClauseType.IMPLEMENTATION_SPECIFICATION, Modality.REQUIRED)


def test_grading_without_specifications_is_rejected() -> None:
    with pytest.raises(ValidationError, match="grades_specifications needs"):
        FrameworkDeclaration(
            framework="TEST-Bad",
            clause_types=frozenset({ClauseType.STANDARD}),
            grades_specifications=True,
        )

"""PRD §8.6 checks 1–6, enforced when a Requirement is built."""

from __future__ import annotations

import pytest
from factories import (
    AUDIT_CONTROLS_ID,
    GRADED_SPEC_ID,
    UNDECLARED_ID,
    UNGRADED_ID,
    cited_fields,
    derived_fields,
)
from pydantic import ValidationError

from compliance_copilot.corpus.lexicon import load_lexicon
from compliance_copilot.corpus.loader import default_corpus
from compliance_copilot.models import (
    ClauseType,
    EvidenceType,
    Modality,
    Requirement,
    RequirementContext,
    requirement_context,
)

# --- QA gate 0: the three named rejections ---------------------------------


def test_gate0_cited_requirement_with_required_modality_on_a_standard_is_rejected(
    context: RequirementContext,
) -> None:
    fields = cited_fields(clause_type=ClauseType.STANDARD, modality=Modality.REQUIRED)

    with pytest.raises(ValidationError, match=r"164\.306\(d\)") as excinfo:
        Requirement.model_validate(fields, context=context)
    assert "only valid on an implementation_specification" in str(excinfo.value)


def test_gate0_derived_requirement_missing_implication_id_is_rejected(
    context_with_cited: RequirementContext,
) -> None:
    fields = derived_fields()
    del fields["implication_id"]

    with pytest.raises(ValidationError, match="needs implication_id"):
        Requirement.model_validate(fields, context=context_with_cited)


def test_gate0_requirement_with_no_evidence_type_is_rejected(
    context: RequirementContext,
) -> None:
    fields = cited_fields()
    del fields["evidence_type"]

    with pytest.raises(ValidationError) as excinfo:
        Requirement.model_validate(fields, context=context)
    errors = excinfo.value.errors()
    assert [(e["loc"], e["type"]) for e in errors] == [(("evidence_type",), "missing")]


# --- QA gate 2: check 5, scope ---------------------------------------------

HEALTH_DATA_SENTENCE = "implement comprehensive audit logging for all health data"
INSIDE_AUDIT_CONTROLS = (
    "Record and examine activity in information systems that contain or use "
    "electronic protected health information."
)


def _shipped_context() -> RequirementContext:
    corpus = default_corpus()
    return RequirementContext.build(
        clauses=corpus.clauses,
        declarations=corpus.declarations,
        lexicon=load_lexicon(),
    )


def test_gate2_health_data_citing_audit_controls_is_rejected() -> None:
    fields = cited_fields(text=HEALTH_DATA_SENTENCE)

    with pytest.raises(ValidationError, match="health data") as excinfo:
        Requirement.model_validate(fields, context=_shipped_context())
    message = str(excinfo.value)
    assert "check 5" in message
    assert "electronic protected health information" in message


def test_gate2_wording_inside_audit_controls_terms_is_accepted() -> None:
    fields = cited_fields(text=INSIDE_AUDIT_CONTROLS)

    requirement = Requirement.model_validate(fields, context=_shipped_context())

    assert requirement.citation == AUDIT_CONTROLS_ID
    assert requirement.text == INSIDE_AUDIT_CONTROLS


# --- valid requirements are accepted ---------------------------------------


def test_cited_requirement_on_a_standard_is_accepted(context: RequirementContext) -> None:
    requirement = Requirement.model_validate(cited_fields(), context=context)

    assert requirement.evidence_type is EvidenceType.CITED
    assert requirement.clause_type is ClauseType.STANDARD
    assert requirement.modality is None


def test_constructor_validates_against_the_active_context(
    context: RequirementContext,
) -> None:
    with requirement_context(context):
        requirement = Requirement(**cited_fields())

    assert requirement.citation == AUDIT_CONTROLS_ID


def test_cited_requirement_on_a_graded_specification_is_accepted(
    context: RequirementContext,
) -> None:
    fields = cited_fields(
        citation=GRADED_SPEC_ID,
        clause_type=ClauseType.IMPLEMENTATION_SPECIFICATION,
        modality=Modality.REQUIRED,
    )

    assert Requirement.model_validate(fields, context=context).modality is Modality.REQUIRED


def test_cited_requirement_in_an_ungraded_framework_is_accepted(
    context: RequirementContext,
) -> None:
    fields = cited_fields(citation=UNGRADED_ID, clause_type=None, modality=None)

    assert Requirement.model_validate(fields, context=context).clause_type is None


def test_derived_requirement_is_accepted(context_with_cited: RequirementContext) -> None:
    requirement = Requirement.model_validate(derived_fields(), context=context_with_cited)

    assert requirement.evidence_type is EvidenceType.DERIVED


# --- check 1: citation resolves --------------------------------------------


@pytest.mark.parametrize("build", [cited_fields, derived_fields], ids=["cited", "derived"])
def test_unresolvable_citation_is_rejected(
    build: object, context_with_cited: RequirementContext
) -> None:
    fields = build(citation="45-CFR-999.999-z")  # type: ignore[operator]

    with pytest.raises(ValidationError, match=r"does not resolve to a clause.*check 1"):
        Requirement.model_validate(fields, context=context_with_cited)


# --- check 2: cited shape and framework declaration ------------------------


@pytest.mark.parametrize(
    "extra",
    [
        {"rationale": "Some reasoning."},
        {"derived_from": "req_other"},
        {"implication_id": "notification_deadline_implies_identification"},
    ],
    ids=["rationale", "derived_from", "implication_id"],
)
def test_cited_requirement_with_a_derived_only_field_is_rejected(
    extra: dict[str, str], context: RequirementContext
) -> None:
    with pytest.raises(ValidationError, match="cited requirement must not carry"):
        Requirement.model_validate(cited_fields(**extra), context=context)


def test_cited_clause_type_must_match_the_corpus(context: RequirementContext) -> None:
    fields = cited_fields(
        clause_type=ClauseType.IMPLEMENTATION_SPECIFICATION, modality=Modality.ADDRESSABLE
    )

    with pytest.raises(ValidationError, match="does not match the corpus value"):
        Requirement.model_validate(fields, context=context)


def test_cited_modality_left_off_a_graded_specification_is_rejected(
    context: RequirementContext,
) -> None:
    fields = cited_fields(
        citation=GRADED_SPEC_ID,
        clause_type=ClauseType.IMPLEMENTATION_SPECIFICATION,
        modality=None,
    )

    with pytest.raises(ValidationError, match="extraction failure"):
        Requirement.model_validate(fields, context=context)


def test_cited_requirement_in_an_undeclared_framework_is_rejected(
    context: RequirementContext,
) -> None:
    fields = cited_fields(citation=UNDECLARED_ID, clause_type=None, modality=None)

    with pytest.raises(ValidationError, match="cannot ship"):
        Requirement.model_validate(fields, context=context)


# --- check 3: derived shape and resolution ---------------------------------


@pytest.mark.parametrize("missing", ["rationale", "derived_from", "implication_id"])
def test_derived_requirement_missing_a_required_field_is_rejected(
    missing: str, context_with_cited: RequirementContext
) -> None:
    fields = derived_fields()
    del fields[missing]

    with pytest.raises(ValidationError, match=f"needs {missing}"):
        Requirement.model_validate(fields, context=context_with_cited)


def test_derived_requirement_with_modality_is_rejected(
    context_with_cited: RequirementContext,
) -> None:
    with pytest.raises(ValidationError, match="must not carry modality"):
        Requirement.model_validate(
            derived_fields(modality=Modality.REQUIRED), context=context_with_cited
        )


def test_derived_from_must_resolve_to_a_requirement(
    context_with_cited: RequirementContext,
) -> None:
    with pytest.raises(ValidationError, match="does not resolve to a requirement"):
        Requirement.model_validate(
            derived_fields(derived_from="req_missing"), context=context_with_cited
        )


def test_derived_from_must_point_at_a_cited_requirement(
    context_with_cited: RequirementContext,
) -> None:
    first = Requirement.model_validate(derived_fields(), context=context_with_cited)
    context = context_with_cited.with_requirement(first)

    with pytest.raises(ValidationError, match="must point at a cited requirement"):
        Requirement.model_validate(
            derived_fields(id="req_second", derived_from=first.id), context=context
        )


def test_implication_id_must_be_in_the_list(context_with_cited: RequirementContext) -> None:
    with pytest.raises(ValidationError, match="not in the list of implications"):
        Requirement.model_validate(
            derived_fields(implication_id="made_up_implication"),
            context=context_with_cited,
        )


# --- check 4: evidence_type has no default ---------------------------------


def test_null_evidence_type_is_rejected(context: RequirementContext) -> None:
    with pytest.raises(ValidationError, match="evidence_type"):
        Requirement.model_validate(cited_fields(evidence_type=None), context=context)


# --- check 6: styling cannot be set ----------------------------------------


@pytest.mark.parametrize("name", ["render_style", "style", "clause_text"])
def test_fields_outside_the_schema_are_rejected(
    name: str, context: RequirementContext
) -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        Requirement.model_validate(cited_fields(**{name: "anything"}), context=context)


# --- timing ----------------------------------------------------------------


def test_applies_at_scale_is_not_a_timing_value(context: RequirementContext) -> None:
    with pytest.raises(ValidationError, match="timing"):
        Requirement.model_validate(cited_fields(timing="applies_at_scale"), context=context)


def test_timing_has_no_default(context: RequirementContext) -> None:
    fields = cited_fields()
    del fields["timing"]

    with pytest.raises(ValidationError, match="timing"):
        Requirement.model_validate(fields, context=context)


# --- the checks cannot be bypassed -----------------------------------------


def test_requirement_without_a_context_is_rejected() -> None:
    with pytest.raises(ValidationError, match="no RequirementContext"):
        Requirement(**cited_fields())


def test_model_construct_is_disabled() -> None:
    with pytest.raises(TypeError, match="skips validation"):
        Requirement.model_construct(**cited_fields())


def test_requirement_is_immutable(context: RequirementContext) -> None:
    requirement = Requirement.model_validate(cited_fields(), context=context)

    with pytest.raises(ValidationError, match="frozen"):
        requirement.modality = Modality.REQUIRED  # type: ignore[misc]
    with pytest.raises(TypeError, match="skips validation"):
        requirement.model_copy(update={"modality": Modality.REQUIRED})


def test_duplicate_clause_ids_in_a_context_are_rejected(
    context: RequirementContext,
) -> None:
    clause = context.clauses[AUDIT_CONTROLS_ID]

    with pytest.raises(ValueError, match="duplicate clause id"):
        RequirementContext.build(
            clauses=[clause, clause],
            declarations=context.declarations.values(),
            lexicon=context.lexicon,
        )

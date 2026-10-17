"""Field states, the stated facts, the determination and the derived block."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from pydantic import StrictBool, ValidationError

from compliance_copilot.models import (
    AmbiguityCause,
    Applicability,
    ComplianceContextObject,
    CoveredEntityStatus,
    DerivedFacts,
    Determination,
    EntryPath,
    Field,
    FieldSource,
    FieldState,
    Framework,
    FrameworkSummaryEntry,
    HipaaSituation,
    StatedFacts,
    SummaryCategory,
)

BILLING_PATH = "stated.hipaa_situation.customers_bill_insurers_electronically"
CUSTOMERS_PATH = "stated.hipaa_situation.customer_types"

# --- Field -----------------------------------------------------------------


def test_unknown_to_user_is_a_real_answer_with_no_value() -> None:
    field = Field[StrictBool](source=FieldSource.QA_ANSWER, state=FieldState.UNKNOWN_TO_USER)

    assert field.state is FieldState.UNKNOWN_TO_USER
    assert field.value is None


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"state": "answered", "source": "qa_answer"}, "needs a value"),
        ({"state": "answered", "value": True}, "needs a source"),
        ({"state": "unknown_to_user", "source": "qa_answer", "value": False}, "must not carry a value"),
        ({"state": "skipped", "source": "qa_answer", "value": True}, "must not carry a value"),
        ({"state": "not_asked", "source": "qa_answer"}, "must not name a source"),
        ({"state": "unknown_to_user"}, "needs a source"),
    ],
)
def test_field_state_must_match_value_and_source(fields: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Field[StrictBool].model_validate(fields)


@pytest.mark.parametrize("value", ["yes", "true", 1])
def test_boolean_answers_are_not_coerced(value: object) -> None:
    with pytest.raises(ValidationError, match="bool"):
        Field[StrictBool].model_validate(
            {"value": value, "source": "qa_answer", "state": "answered"}
        )


def test_field_state_has_no_default() -> None:
    with pytest.raises(ValidationError, match="state"):
        Field[StrictBool].model_validate({})


# --- stated facts ----------------------------------------------------------


def stated(**hipaa: Any) -> dict[str, Any]:
    return {
        "product": {
            "description": {"value": "A product", "source": "qa_answer", "state": "answered"}
        },
        "hipaa_situation": hipaa,
    }


def test_unstated_hipaa_fields_default_to_not_asked() -> None:
    situation = HipaaSituation()

    for name in HipaaSituation.model_fields:
        assert getattr(situation, name).state is FieldState.NOT_ASKED


def test_product_description_must_be_answered() -> None:
    data = stated()
    data["product"]["description"] = {"source": "qa_answer", "state": "skipped"}

    with pytest.raises(ValidationError, match="must be answered"):
        StatedFacts.model_validate(data)


def test_answered_customer_types_cannot_be_empty() -> None:
    with pytest.raises(ValidationError, match="at least 1"):
        StatedFacts.model_validate(
            stated(customer_types={"value": [], "source": "qa_answer", "state": "answered"})
        )


def test_subcontractor_customer_type_is_accepted() -> None:
    facts = StatedFacts.model_validate(
        stated(
            customer_types={
                "value": ["companies_handling_patient_data_for_providers"],
                "source": "qa_answer",
                "state": "answered",
            }
        )
    )

    assert facts.hipaa_situation.customer_types.value is not None


def test_unknown_stated_field_is_rejected() -> None:
    with pytest.raises(ValidationError, match="Extra inputs are not permitted"):
        StatedFacts.model_validate(stated(is_business_associate={"state": "not_asked"}))


# --- determination ---------------------------------------------------------


def test_ambiguous_determination_carries_cause_and_questions() -> None:
    determination = Determination(
        value=CoveredEntityStatus.AMBIGUOUS,
        derived_from=(BILLING_PATH,),
        ambiguity_cause=AmbiguityCause.MISSING_FACT,
        unresolved_questions=("Do your clinic customers bill insurers electronically?",),
    )

    assert determination.applicability is Applicability.AMBIGUOUS
    assert determination.hipaa_category is SummaryCategory.UNRESOLVED


@pytest.mark.parametrize(
    ("fields", "message"),
    [
        ({"value": "ambiguous", "unresolved_questions": ["q"]}, "needs an ambiguity_cause"),
        ({"value": "ambiguous", "ambiguity_cause": "missing_fact"}, "at least one unresolved question"),
        ({"value": "neither", "ambiguity_cause": "missing_fact"}, "must not carry an ambiguity_cause"),
        ({"value": "covered_entity", "unresolved_questions": ["q"]}, "must not carry unresolved"),
    ],
)
def test_determination_ambiguity_must_be_consistent(fields: dict[str, Any], message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Determination.model_validate({"derived_from": [BILLING_PATH], **fields})


@pytest.mark.parametrize(
    ("path", "message"),
    [
        ("stated.hipaa_situation", "ends at a group"),
        ("stated.hipaa_situation.is_covered", "not a field of HipaaSituation"),
        ("derived.covered_entity_status", "String should match pattern"),
    ],
)
def test_derived_from_paths_must_name_a_stated_field(path: str, message: str) -> None:
    with pytest.raises(ValidationError, match=message):
        Determination(value=CoveredEntityStatus.NEITHER, derived_from=(path,))


def test_derived_from_cannot_be_empty_or_repeat() -> None:
    with pytest.raises(ValidationError, match="at least 1"):
        Determination(value=CoveredEntityStatus.NEITHER, derived_from=())
    with pytest.raises(ValidationError, match="repeats paths"):
        Determination(value=CoveredEntityStatus.NEITHER, derived_from=(BILLING_PATH, BILLING_PATH))


# --- framework summary -----------------------------------------------------


def test_not_assessed_entry_has_nothing_to_trace() -> None:
    with pytest.raises(ValidationError, match="derived_from must be empty"):
        FrameworkSummaryEntry(
            framework=Framework.HBNR,
            category=SummaryCategory.NOT_ASSESSED,
            derived_from=(CUSTOMERS_PATH,),
            reason="Not in the prototype corpus.",
        )


def test_assessed_entry_must_trace_to_intake() -> None:
    with pytest.raises(ValidationError, match="must name the intake answers"):
        FrameworkSummaryEntry(
            framework=Framework.HIPAA,
            category=SummaryCategory.OUT_OF_SCOPE,
            reason="Neither a covered entity nor a business associate.",
        )


def full_summary(hipaa: SummaryCategory) -> tuple[FrameworkSummaryEntry, ...]:
    entries = [
        FrameworkSummaryEntry(
            framework=Framework.HIPAA,
            category=hipaa,
            derived_from=(CUSTOMERS_PATH,),
            reason="From the determination.",
        )
    ]
    entries += [
        FrameworkSummaryEntry(
            framework=f, category=SummaryCategory.NOT_ASSESSED, reason="Not in the prototype."
        )
        for f in Framework
        if f is not Framework.HIPAA
    ]
    return tuple(entries)


def neither() -> Determination:
    return Determination(value=CoveredEntityStatus.NEITHER, derived_from=(CUSTOMERS_PATH,))


def test_derived_block_accepts_a_complete_consistent_summary() -> None:
    derived = DerivedFacts(
        covered_entity_status=neither(),
        framework_applicability=full_summary(SummaryCategory.OUT_OF_SCOPE),
    )

    assert len(derived.framework_applicability) == len(Framework)


def test_summary_missing_a_framework_is_rejected() -> None:
    with pytest.raises(ValidationError, match="missing from the summary: PCI_DSS"):
        DerivedFacts(
            covered_entity_status=neither(),
            framework_applicability=full_summary(SummaryCategory.OUT_OF_SCOPE)[:-1],
        )


def test_summary_listing_a_framework_twice_is_rejected() -> None:
    summary = full_summary(SummaryCategory.OUT_OF_SCOPE)

    with pytest.raises(ValidationError, match="more than once: HBNR"):
        DerivedFacts(
            covered_entity_status=neither(), framework_applicability=(*summary, summary[1])
        )


def test_hipaa_category_must_follow_the_determination() -> None:
    with pytest.raises(ValidationError, match="puts it in 'out_of_scope'"):
        DerivedFacts(
            covered_entity_status=neither(),
            framework_applicability=full_summary(SummaryCategory.IN_SCOPE),
        )


def test_summary_without_a_determination_is_rejected() -> None:
    with pytest.raises(ValidationError, match="needs covered_entity_status"):
        DerivedFacts(framework_applicability=full_summary(SummaryCategory.OUT_OF_SCOPE))


def test_context_object_starts_with_an_empty_derived_block() -> None:
    cco = ComplianceContextObject(
        id="cco-1",
        created_at=datetime(2026, 10, 17, tzinfo=UTC),
        entry_path=EntryPath.NO_PRD,
        stated=StatedFacts.model_validate(stated()),
    )

    assert cco.derived.covered_entity_status is None
    assert cco.derived.framework_applicability == ()


def test_context_object_needs_a_timezone_aware_timestamp() -> None:
    with pytest.raises(ValidationError, match="timezone"):
        ComplianceContextObject(
            id="cco-1",
            created_at=datetime(2026, 10, 17),
            entry_path=EntryPath.NO_PRD,
            stated=StatedFacts.model_validate(stated()),
        )

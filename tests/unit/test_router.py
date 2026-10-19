"""Each covered-entity rule branch, including skipped, not_asked, and unknown_to_user."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest

from compliance_copilot.config import load_settings
from compliance_copilot.log import configure_logging
from compliance_copilot.models import (
    AmbiguityCause,
    CoveredEntityStatus,
    CustomerType,
    Field,
    FieldSource,
    FieldState,
    HipaaSituation,
    Product,
    StatedFacts,
    TraceAction,
)
from compliance_copilot.router import RunError, determine, run_determination
from compliance_copilot.router.paths import (
    BILLS,
    CARE,
    CLINICAL,
    CUSTOMERS,
    CUSTOMERS_BILL,
    RECEIVES,
)

T0 = datetime(2026, 10, 18, 15, 0, tzinfo=UTC)
Status = CoveredEntityStatus
Cause = AmbiguityCause


def answered(value: object) -> Field[object]:
    return Field(value=value, source=FieldSource.QA_ANSWER, state=FieldState.ANSWERED)


def gap(state: FieldState) -> Field[object]:
    if state is FieldState.NOT_ASKED:
        return Field.not_asked()
    return Field(source=FieldSource.QA_ANSWER, state=state)


def facts(**fields: Field[object]) -> StatedFacts:
    return StatedFacts(
        product=Product(description=answered("A test product")),
        hipaa_situation=HipaaSituation(**fields),
    )


def status_of(**fields: Field[object]) -> tuple[CoveredEntityStatus, AmbiguityCause | None, tuple[str, ...]]:
    decision = determine(facts(**fields))
    determination = decision.determination
    return determination.value, determination.ambiguity_cause, determination.derived_from


def questions_of(**fields: Field[object]) -> tuple[str, ...]:
    return determine(facts(**fields)).determination.unresolved_questions


def test_providing_care_and_billing_is_a_covered_entity() -> None:
    status, cause, paths = status_of(
        provides_care_directly=answered(True),
        bills_insurers_electronically=answered(True),
    )

    assert status is Status.COVERED_ENTITY
    assert cause is None
    assert paths == (CARE, BILLS)


def test_billing_alone_is_not_a_covered_entity() -> None:
    status, cause, paths = status_of(
        provides_care_directly=answered(False),
        bills_insurers_electronically=answered(True),
        customer_types=answered((CustomerType.CONSUMERS,)),
        receives_patient_data_from_others=answered(False),
    )

    assert status is Status.NEITHER
    assert cause is None
    assert CARE in paths
    assert BILLS not in paths


def test_own_covered_entity_status_wins_over_a_business_associate_result() -> None:
    status, _, paths = status_of(
        provides_care_directly=answered(True),
        bills_insurers_electronically=answered(True),
        customer_types=answered((CustomerType.CLINICS,)),
        customers_bill_insurers_electronically=answered(True),
        receives_patient_data_from_others=answered(True),
        receives_clinical_information=answered(True),
    )

    assert status is Status.COVERED_ENTITY
    assert paths == (CARE, BILLS)


def test_a_false_rules_out_covered_entity_even_when_the_other_fact_is_unknown() -> None:
    status, cause, paths = status_of(
        provides_care_directly=gap(FieldState.UNKNOWN_TO_USER),
        bills_insurers_electronically=answered(False),
        customer_types=answered((CustomerType.CONSUMERS,)),
        receives_patient_data_from_others=answered(False),
    )

    assert status is Status.NEITHER
    assert cause is None
    assert paths == (CUSTOMERS, RECEIVES, BILLS)


@pytest.mark.parametrize(
    ("state", "fragment"),
    [
        (FieldState.UNKNOWN_TO_USER, "You don't know whether you bill insurers"),
        (FieldState.SKIPPED, "whether you bill insurers electronically was skipped"),
        (FieldState.NOT_ASKED, "We did not ask whether you bill insurers"),
    ],
)
def test_an_open_billing_fact_is_missing_when_care_is_yes(state: FieldState, fragment: str) -> None:
    status, cause, paths = status_of(
        provides_care_directly=answered(True),
        bills_insurers_electronically=gap(state),
        customer_types=answered((CustomerType.CONSUMERS,)),
        receives_patient_data_from_others=answered(False),
    )

    assert (status, cause, paths) == (Status.AMBIGUOUS, Cause.MISSING_FACT, (CARE, BILLS))
    assert fragment in questions_of(
        provides_care_directly=answered(True),
        bills_insurers_electronically=gap(state),
        customer_types=answered((CustomerType.CONSUMERS,)),
        receives_patient_data_from_others=answered(False),
    )[0]


def test_clinics_that_bill_and_clinical_data_make_a_business_associate() -> None:
    status, cause, paths = status_of(
        customer_types=answered((CustomerType.CLINICS,)),
        customers_bill_insurers_electronically=answered(True),
        receives_patient_data_from_others=answered(True),
        receives_clinical_information=answered(True),
    )

    assert status is Status.BUSINESS_ASSOCIATE
    assert cause is None
    assert paths == (CUSTOMERS, CUSTOMERS_BILL, RECEIVES, CLINICAL)


def test_clinical_information_not_asked_does_not_block_a_business_associate() -> None:
    status, _, paths = status_of(
        customer_types=answered((CustomerType.CONSUMERS, CustomerType.CLINICS)),
        customers_bill_insurers_electronically=answered(True),
        receives_patient_data_from_others=answered(True),
        bills_insurers_electronically=answered(False),
    )

    assert status is Status.BUSINESS_ASSOCIATE
    assert CLINICAL not in paths
    assert BILLS not in paths


def test_scheduling_details_only_make_a_business_associate() -> None:
    fields = dict(
        customer_types=answered((CustomerType.CLINICS,)),
        customers_bill_insurers_electronically=answered(True),
        receives_patient_data_from_others=answered(True),
        receives_clinical_information=answered(False),
    )
    status, cause, paths = status_of(**fields)
    decision = determine(facts(**fields))

    assert (status, cause) == (Status.BUSINESS_ASSOCIATE, None)
    assert paths == (CUSTOMERS, CUSTOMERS_BILL, RECEIVES, CLINICAL)
    assert "health information includes information that relates to the provision of health care" in decision.rationale
    assert "individually identifiable health information" in decision.rationale
    assert "A diagnosis is not required" in decision.rationale
    assert decision.clauses.index("45-CFR-160.103-def-health-information") < decision.clauses.index(
        "45-CFR-160.103-def-individually-identifiable-health-information"
    )
    assert "45-CFR-160.103-def-protected-health-information" in decision.clauses


@pytest.mark.parametrize(
    ("state", "fragment"),
    [
        (FieldState.UNKNOWN_TO_USER, "You don't know"),
        (FieldState.SKIPPED, "was skipped"),
        (FieldState.NOT_ASKED, "We did not ask"),
    ],
)
def test_clinic_billing_states_stay_distinct(state: FieldState, fragment: str) -> None:
    fields = dict(
        customer_types=answered((CustomerType.CLINICS,)),
        customers_bill_insurers_electronically=gap(state),
        receives_patient_data_from_others=answered(True),
        receives_clinical_information=answered(True),
    )
    status, cause, paths = status_of(**fields)

    assert (status, cause) == (Status.AMBIGUOUS, Cause.MISSING_FACT)
    assert paths == (CUSTOMERS, CUSTOMERS_BILL, RECEIVES)
    assert CLINICAL not in paths
    question = questions_of(**fields)[0]
    assert fragment in question
    assert "either directly or through a billing company" in question


@pytest.mark.parametrize("state", [FieldState.NOT_ASKED, FieldState.SKIPPED, FieldState.UNKNOWN_TO_USER])
def test_a_health_plan_does_not_read_the_clinic_billing_field(state: FieldState) -> None:
    status, cause, paths = status_of(
        customer_types=answered((CustomerType.INSURERS,)),
        customers_bill_insurers_electronically=gap(state),
        receives_patient_data_from_others=answered(True),
    )

    assert (status, cause) == (Status.BUSINESS_ASSOCIATE, None)
    assert paths == (CUSTOMERS, RECEIVES)
    if state is FieldState.NOT_ASKED:
        assert "clinic-billing question is not asked" in determine(
            facts(
                customer_types=answered((CustomerType.INSURERS,)),
                receives_patient_data_from_others=answered(True),
            )
        ).rationale


def test_an_answered_clinic_billing_field_is_ignored_for_a_health_plan_only_customer() -> None:
    _, _, paths = status_of(
        customer_types=answered((CustomerType.INSURERS,)),
        customers_bill_insurers_electronically=answered(False),
        receives_patient_data_from_others=answered(True),
    )

    assert CUSTOMERS_BILL not in paths


def test_a_health_plan_customer_settles_business_associate_when_clinic_billing_is_unknown() -> None:
    status, cause, paths = status_of(
        customer_types=answered((CustomerType.CLINICS, CustomerType.INSURERS)),
        customers_bill_insurers_electronically=gap(FieldState.UNKNOWN_TO_USER),
        receives_patient_data_from_others=answered(True),
        receives_clinical_information=answered(True),
    )

    assert status is Status.BUSINESS_ASSOCIATE
    assert cause is None
    assert CUSTOMERS_BILL not in paths
    assert CLINICAL in paths


def test_unknown_clinic_billing_wins_over_scheduling_only_data() -> None:
    status, cause, paths = status_of(
        customer_types=answered((CustomerType.CLINICS,)),
        customers_bill_insurers_electronically=gap(FieldState.UNKNOWN_TO_USER),
        receives_patient_data_from_others=answered(True),
        receives_clinical_information=answered(False),
    )

    assert (status, cause) == (Status.AMBIGUOUS, Cause.MISSING_FACT)
    assert CLINICAL not in paths


@pytest.mark.parametrize("state", [FieldState.UNKNOWN_TO_USER, FieldState.SKIPPED])
def test_an_open_clinical_fact_does_not_block_a_business_associate(state: FieldState) -> None:
    fields = dict(
        customer_types=answered((CustomerType.CLINICS,)),
        customers_bill_insurers_electronically=answered(True),
        receives_patient_data_from_others=answered(True),
        receives_clinical_information=gap(state),
    )

    status, cause, paths = status_of(**fields)
    assert (status, cause) == (Status.BUSINESS_ASSOCIATE, None)
    assert CLINICAL not in paths
    assert "scheduling details" not in determine(facts(**fields)).rationale


@pytest.mark.parametrize("state", [FieldState.UNKNOWN_TO_USER, FieldState.SKIPPED])
def test_an_open_clinical_fact_does_not_change_the_subcontractor_cause(
    state: FieldState,
) -> None:
    status, cause, paths = status_of(
        customer_types=answered((CustomerType.COMPANIES_HANDLING_PATIENT_DATA_FOR_PROVIDERS,)),
        receives_patient_data_from_others=answered(True),
        receives_clinical_information=gap(state),
    )

    assert (status, cause) == (Status.AMBIGUOUS, Cause.REQUIRES_DOCUMENT_WE_CANNOT_SEE)
    assert CLINICAL not in paths


def test_a_subcontractor_customer_needs_a_document_the_tool_cannot_see() -> None:
    status, cause, paths = status_of(
        customer_types=answered((CustomerType.COMPANIES_HANDLING_PATIENT_DATA_FOR_PROVIDERS,)),
        receives_patient_data_from_others=answered(True),
        receives_clinical_information=answered(True),
    )

    assert (status, cause) == (Status.AMBIGUOUS, Cause.REQUIRES_DOCUMENT_WE_CANNOT_SEE)
    assert paths == (CUSTOMERS, RECEIVES, CLINICAL)
    assert "contracts" in questions_of(
        customer_types=answered((CustomerType.COMPANIES_HANDLING_PATIENT_DATA_FOR_PROVIDERS,)),
        receives_patient_data_from_others=answered(True),
        receives_clinical_information=answered(True),
    )[0]


def test_a_settled_covered_customer_is_a_business_associate_despite_a_subcontractor() -> None:
    status, cause, _ = status_of(
        customer_types=answered(
            (CustomerType.INSURERS, CustomerType.COMPANIES_HANDLING_PATIENT_DATA_FOR_PROVIDERS)
        ),
        receives_patient_data_from_others=answered(True),
    )

    assert (status, cause) == (Status.BUSINESS_ASSOCIATE, None)


def test_no_patient_data_rules_out_a_business_associate_before_clinic_billing() -> None:
    status, cause, paths = status_of(
        customer_types=answered((CustomerType.CLINICS,)),
        customers_bill_insurers_electronically=gap(FieldState.UNKNOWN_TO_USER),
        receives_patient_data_from_others=answered(False),
        bills_insurers_electronically=answered(False),
    )

    assert (status, cause) == (Status.NEITHER, None)
    assert CUSTOMERS_BILL not in paths


def test_clinics_that_do_not_bill_are_not_covered_entities() -> None:
    status, cause, paths = status_of(
        customer_types=answered((CustomerType.CLINICS,)),
        customers_bill_insurers_electronically=answered(False),
        receives_patient_data_from_others=answered(True),
        receives_clinical_information=answered(True),
        bills_insurers_electronically=answered(False),
    )

    assert (status, cause) == (Status.NEITHER, None)
    assert paths == (CUSTOMERS, CUSTOMERS_BILL, RECEIVES, BILLS)


def test_employers_are_not_read_as_covered_entities() -> None:
    status, cause, paths = status_of(
        customer_types=answered((CustomerType.EMPLOYERS,)),
        receives_patient_data_from_others=answered(True),
        bills_insurers_electronically=answered(False),
    )

    assert (status, cause) == (Status.NEITHER, None)
    assert CUSTOMERS in paths
    assert RECEIVES in paths


@pytest.mark.parametrize(
    "agreements",
    [
        answered(True),
        answered(False),
        gap(FieldState.UNKNOWN_TO_USER),
        gap(FieldState.SKIPPED),
        gap(FieldState.NOT_ASKED),
    ],
)
def test_a_signed_agreement_does_not_change_the_determination(agreements: Field[object]) -> None:
    shared = dict(
        customer_types=answered((CustomerType.CLINICS,)),
        customers_bill_insurers_electronically=answered(True),
        receives_patient_data_from_others=answered(True),
        receives_clinical_information=answered(True),
    )
    baseline = determine(facts(**shared))
    varied = determine(facts(**shared, has_signed_agreements_with_healthcare_orgs=agreements))

    assert varied.determination == baseline.determination


def test_unasked_customer_types_leave_business_associate_status_unresolved() -> None:
    status, cause, paths = status_of(bills_insurers_electronically=answered(False))

    assert (status, cause) == (Status.AMBIGUOUS, Cause.MISSING_FACT)
    assert CUSTOMERS in paths
    assert "We did not ask who your customers are" in questions_of(
        bills_insurers_electronically=answered(False)
    )[0]


def test_unasked_own_status_leaves_a_consumer_app_unresolved() -> None:
    status, cause, _ = status_of(
        customer_types=answered((CustomerType.CONSUMERS,)),
        receives_patient_data_from_others=answered(False),
    )

    assert (status, cause) == (Status.AMBIGUOUS, Cause.MISSING_FACT)
    question = " ".join(
        questions_of(
            customer_types=answered((CustomerType.CONSUMERS,)),
            receives_patient_data_from_others=answered(False),
        )
    )
    assert "did not ask whether you provide care" in question
    assert "did not ask whether you bill insurers" in question


def test_nothing_asked_is_a_missing_fact() -> None:
    status, cause, paths = status_of()

    assert (status, cause) == (Status.AMBIGUOUS, Cause.MISSING_FACT)
    assert paths == (CUSTOMERS, CARE, BILLS)


@pytest.mark.parametrize(
    ("state", "fragment"),
    [
        (FieldState.UNKNOWN_TO_USER, "You don't know who your customers are"),
        (FieldState.SKIPPED, "who your customers are was skipped"),
    ],
)
def test_an_open_customer_list_is_a_missing_fact(state: FieldState, fragment: str) -> None:
    status, cause, paths = status_of(customer_types=gap(state))

    assert (status, cause, paths) == (Status.AMBIGUOUS, Cause.MISSING_FACT, (CUSTOMERS,))
    assert fragment in questions_of(customer_types=gap(state))[0]


@pytest.mark.parametrize(
    ("state", "fragment"),
    [
        (FieldState.UNKNOWN_TO_USER, "You don't know whether your product receives patient data"),
        (FieldState.SKIPPED, "whether your product receives patient data from someone else was skipped"),
        (FieldState.NOT_ASKED, "We did not ask whether your product receives patient data"),
    ],
)
def test_an_open_receives_fact_stays_distinct_for_a_health_plan(
    state: FieldState, fragment: str
) -> None:
    fields = dict(
        customer_types=answered((CustomerType.INSURERS,)),
        receives_patient_data_from_others=gap(state),
    )

    status, cause, paths = status_of(**fields)
    assert (status, cause, paths) == (Status.AMBIGUOUS, Cause.MISSING_FACT, (CUSTOMERS, RECEIVES))
    assert fragment in questions_of(**fields)[0]


def test_an_unknown_customer_list_is_marked_unknown_in_the_trace() -> None:
    stated = facts(customer_types=gap(FieldState.UNKNOWN_TO_USER))
    run = run_determination(stated, analysis_id="customers-unknown", at=T0)

    assert [step.action for step in run.trace.steps] == [
        TraceAction.MARKED_UNKNOWN,
        TraceAction.DETERMINED_UNRESOLVED,
    ]


def test_run_logs_intake_then_router(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    monkeypatch.setenv("LOG_LEVEL", "INFO")
    configure_logging(load_settings())

    run_determination(
        facts(
            customer_types=answered((CustomerType.INSURERS,)),
            receives_patient_data_from_others=answered(True),
        ),
        analysis_id="G-06",
        at=T0,
    )

    payloads = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert [payload["stage"] for payload in payloads] == ["intake", "router"]
    assert payloads[1]["covered_entity_status"] == "business_associate"
    assert payloads[1]["ambiguity_cause"] is None
    assert payloads[1]["run_id"] == "G-06"


def test_a_naive_timestamp_is_rejected() -> None:
    with pytest.raises(RunError, match="timezone-aware"):
        run_determination(
            facts(customer_types=gap(FieldState.NOT_ASKED)),
            analysis_id="naive",
            at=datetime(2026, 10, 18, 15, 0),
        )


def test_the_product_description_is_not_read() -> None:
    situation = HipaaSituation(
        customer_types=answered((CustomerType.INSURERS,)),
        receives_patient_data_from_others=answered(True),
    )
    first = determine(
        StatedFacts(product=Product(description=answered("One description")), hipaa_situation=situation)
    )
    second = determine(
        StatedFacts(product=Product(description=answered("Another description")), hipaa_situation=situation)
    )

    assert first.determination == second.determination

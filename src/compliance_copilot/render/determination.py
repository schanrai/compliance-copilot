"""Terminal rendering of a covered-entity determination and its reasoning.

The action names from the trace are not shown (PRD §13.2). A signed agreement,
when the intake recorded one, is shown as unused.
"""

from __future__ import annotations

from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from compliance_copilot.models import (
    AmbiguityCause,
    CoveredEntityStatus,
    CustomerType,
    Field,
    FieldState,
    StatedFacts,
)
from compliance_copilot.router.determine import CoveredEntityDecision
from compliance_copilot.router.paths import FIELD_LABELS, customer_phrase, field_at

_STATUS = {
    CoveredEntityStatus.COVERED_ENTITY: ("Covered entity", "green"),
    CoveredEntityStatus.BUSINESS_ASSOCIATE: ("Business associate", "green"),
    CoveredEntityStatus.NEITHER: ("Neither a covered entity nor a business associate", "white"),
    CoveredEntityStatus.AMBIGUOUS: ("Ambiguous — unresolved", "yellow"),
}

_CAUSE = {
    AmbiguityCause.MISSING_FACT: "Missing a fact",
    AmbiguityCause.CONTESTED_QUESTION: "A genuinely contested question",
    AmbiguityCause.REQUIRES_DOCUMENT_WE_CANNOT_SEE: "It turns on a document we cannot see",
}

_ADVISORY = (
    "Advisory only. This reports what the intake answers support under 45 CFR 160.103. "
    "It is not legal advice."
)

# Every intake answer, in the order the founder is asked. Includes fields the
# determination does not use, so a not-asked question is visible.
_CLINIC_BILLING_QUESTION = (
    "Does the clinic you sell to bill insurers electronically, "
    "either directly or through a billing company?"
)

_INTAKE_FIELDS = (
    ("customer_types", FIELD_LABELS["stated.hipaa_situation.customer_types"]),
    ("customers_bill_insurers_electronically", _CLINIC_BILLING_QUESTION),
    (
        "receives_patient_data_from_others",
        FIELD_LABELS["stated.hipaa_situation.receives_patient_data_from_others"],
    ),
    (
        "receives_clinical_information",
        FIELD_LABELS["stated.hipaa_situation.receives_clinical_information"],
    ),
    (
        "has_signed_agreements_with_healthcare_orgs",
        "Whether you have a signed agreement with a healthcare organization",
    ),
    (
        "bills_insurers_electronically",
        FIELD_LABELS["stated.hipaa_situation.bills_insurers_electronically"],
    ),
    ("provides_care_directly", FIELD_LABELS["stated.hipaa_situation.provides_care_directly"]),
)


def intake_panel(stated: StatedFacts, *, case_id: str, title: str) -> Panel:
    """The use case and every intake answer, including questions that were not asked."""

    description = stated.product.description.value
    body: list[Text] = [
        Text("Product", style="bold"),
        Text(description if isinstance(description, str) else ""),
        Text(""),
        Text("Intake", style="bold"),
    ]
    for name, label in _INTAKE_FIELDS:
        field = getattr(stated.hipaa_situation, name)
        body.append(Text(f"• {_intake_line(stated, name, label, field)}"))
    return Panel(Group(*body), title=f"{case_id} — {title}", title_align="left")


def _intake_line(stated: StatedFacts, name: str, label: str, field: Field[object]) -> str:
    """One intake row. The clinic-billing question is only worded that way for clinics."""

    if name != "customers_bill_insurers_electronically" or _customers_include_clinics(stated):
        return f"{label}: {_format_value(field)}"
    customers = stated.hipaa_situation.customer_types
    if (
        customers.state is FieldState.ANSWERED
        and customers.value is not None
        and field.state is FieldState.NOT_ASKED
    ):
        return (
            "Whether your customers bill insurers electronically: not asked, "
            f"because your customers are {customer_phrase(customers.value)}"
        )
    return f"Whether your customers bill insurers electronically: {_format_value(field)}"


def _customers_include_clinics(stated: StatedFacts) -> bool:
    customers = stated.hipaa_situation.customer_types
    return (
        customers.state is FieldState.ANSWERED
        and customers.value is not None
        and CustomerType.CLINICS in customers.value
    )


def determination_panel(stated: StatedFacts, decision: CoveredEntityDecision) -> Panel:
    """The determination, the answers it used, and what would settle it."""

    determination = decision.determination
    label, style = _STATUS[determination.value]
    body: list[Text] = [
        Text(label, style=f"bold {style}"),
        Text(""),
        Text(decision.rationale),
        Text(""),
        Text("Answers this used", style="bold"),
    ]
    for path in determination.derived_from:
        body.append(Text(f"• {FIELD_LABELS[path]}: {_format_value(field_at(stated, path))}"))
    agreements = stated.hipaa_situation.has_signed_agreements_with_healthcare_orgs
    if agreements.state is not FieldState.NOT_ASKED:
        body.append(Text(""))
        body.append(
            Text(
                f"The signed-agreement answer ({_format_value(agreements)}) was not used. "
                "It does not decide this status.",
                style="dim",
            )
        )
    cause = determination.ambiguity_cause
    if cause is not None:
        body.extend(
            [
                Text(""),
                Text(f"Why it is unresolved: {_CAUSE[cause]}", style="bold"),
                Text("What would settle it", style="bold"),
            ]
        )
        for question in determination.unresolved_questions:
            body.append(Text(f"• {question}"))
    body.extend([Text(""), Text(_ADVISORY, style="dim")])
    return Panel(Group(*body), title="Covered-entity determination", title_align="left")


def _format_value(field: Field[object]) -> str:
    if field.state is FieldState.UNKNOWN_TO_USER:
        return "you don't know"
    if field.state is FieldState.SKIPPED:
        return "skipped"
    if field.state is FieldState.NOT_ASKED:
        return "not asked"
    value = field.value
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, tuple) and all(isinstance(item, CustomerType) for item in value):
        return customer_phrase(value)
    return str(value)

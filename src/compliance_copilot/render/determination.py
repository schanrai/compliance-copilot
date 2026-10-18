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
from compliance_copilot.router.paths import FIELD_LABELS, customer_phrase, field_at
from compliance_copilot.router.run import CoveredEntityRun

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


def determination_panel(stated: StatedFacts, run: CoveredEntityRun) -> Panel:
    """The determination, the answers it used, and what would settle it."""

    determination = run.decision.determination
    label, style = _STATUS[determination.value]
    body: list[Text] = [
        Text(label, style=f"bold {style}"),
        Text(""),
        Text(run.decision.rationale),
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

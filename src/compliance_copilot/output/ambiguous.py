"""The ambiguous deliverable: components 1, 2, 3, 4 and 6.

Component 5 is specified and not produced. It is present as "next" so it cannot
disappear. No specialist runs. These words come from the determination.
"""

from __future__ import annotations

from typing import Self

from pydantic import model_validator

from compliance_copilot.models import (
    AmbiguityCause,
    CoveredEntityStatus,
    StatedFacts,
)
from compliance_copilot.models._base import ImmutableModel, NonBlankStr
from compliance_copilot.router.determine import CoveredEntityDecision
from compliance_copilot.router.paths import BILLS, CARE, CUSTOMERS

_WHY = {
    AmbiguityCause.MISSING_FACT: (
        "Missing a fact. The intake does not contain an answer that would settle this."
    ),
    AmbiguityCause.CONTESTED_QUESTION: (
        "A genuinely contested question. The facts are known, and the law is not settled."
    ),
    AmbiguityCause.REQUIRES_DOCUMENT_WE_CANNOT_SEE: (
        "It turns on a document we cannot see. Another intake question cannot settle it."
    ),
}

_NEXT = "Specified, next. What to build regardless is not produced in this prototype."


class AmbiguousOutput(ImmutableModel):
    """Components 1–4 and 6, plus component 5 marked as next."""

    what_is_unresolved: NonBlankStr
    why_unresolved: NonBlankStr
    facts_that_would_settle_it: tuple[NonBlankStr, ...]
    if_you_are: NonBlankStr
    if_you_are_not: NonBlankStr
    build_regardless: NonBlankStr
    counsel_question: NonBlankStr

    @model_validator(mode="after")
    def _is_deliverable(self) -> Self:
        problems: list[str] = []
        if "?" not in self.what_is_unresolved:
            problems.append("component 1 must be stated as a question")
        if not self.facts_that_would_settle_it:
            problems.append("component 3 needs at least one fact that would settle it")
        if "next" not in self.build_regardless.lower():
            problems.append("component 5 must be shown as next, not left out")
        if "?" not in self.counsel_question or "45 CFR 160.103" not in self.counsel_question:
            problems.append(
                "component 6 must be a question that cites 45 CFR 160.103, pasteable as written"
            )
        if problems:
            raise ValueError("; ".join(problems))
        return self

    @property
    def present_components(self) -> tuple[int, ...]:
        """The components this prototype fills. Component 5 is next, not filled."""

        return (1, 2, 3, 4, 6)


def ambiguous_output(
    stated: StatedFacts, decision: CoveredEntityDecision
) -> AmbiguousOutput | None:
    """The deliverable for an ambiguous determination. None when the status is settled.

    A settled determination does not get this output, and no specialist runs on
    the strength of an unresolved one.
    """

    determination = decision.determination
    if determination.value is not CoveredEntityStatus.AMBIGUOUS:
        return None
    cause = determination.ambiguity_cause
    if cause is None:
        raise ValueError("an ambiguous determination has no cause")
    subject = _subject(determination.derived_from)
    description = stated.product.description.value
    if not isinstance(description, str):
        raise ValueError("product description is missing")
    detail = " ".join(determination.unresolved_questions)
    return AmbiguousOutput(
        what_is_unresolved=f"Are you a {subject}?",
        why_unresolved=_WHY[cause],
        facts_that_would_settle_it=determination.unresolved_questions,
        if_you_are=(
            f"If you are a {subject}, HIPAA is in scope. The Security Rule applies "
            "to you, including its standards."
        ),
        if_you_are_not=(
            f"If you are not a {subject}, HIPAA does not apply to you on these facts. "
            "The other frameworks in this prototype stay not assessed."
        ),
        build_regardless=_NEXT,
        counsel_question=(
            f"We are building this product: {description} Under 45 CFR 160.103, "
            f"are we a {subject}? {detail} Expect about 30 minutes with a healthcare "
            "privacy lawyer."
        ),
    )


def _subject(paths: tuple[str, ...]) -> str:
    """Who the open question is about. The founder's company and the customer differ."""

    named = set(paths)
    about_customer = CUSTOMERS in named
    about_self = CARE in named or BILLS in named
    if about_customer and not about_self:
        return "business associate"
    if about_self and not about_customer:
        return "covered entity"
    return "covered entity or a business associate"

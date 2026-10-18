"""Covered-entity determination. Plain Python over `hipaa_situation`. No model.

The rules follow 45 CFR 160.103, narrowed to the facts the prototype asks.

A covered entity, here, is a health care provider who transmits health
information electronically in a covered transaction: `provides_care_directly`
and `bills_insurers_electronically` are both yes. One no is enough to rule
that out. Billing alone is not enough. The prototype does not decide
clearinghouses, or a founder who is themselves a health plan.

A business associate handles patient data on behalf of a covered entity, so
the customer's status has to be settled first.

- Clinic customers are covered entities only when
  `customers_bill_insurers_electronically` is yes. The question's wording
  already includes billing through a billing company. There is no separate
  rule for that.
- Health-plan customers (`insurers`) are covered entities by definition.
  Their row does not read the clinic-billing field, whatever state it is in.
- A customer that handles patient data for providers is a subcontractor
  question. When no customer is a settled covered entity, that is ambiguous
  because it turns on contracts the founder is not a party to.
- Consumers and employers are not covered entities. An employer is not read
  as a group health plan.

`receives_clinical_information` is read only after a covered-entity customer
and received patient data are both established. Yes cites the field. No is
the contested protected-health-information question (scheduling details
only). Not asked does not block: G-03 and G-06 are business associates
without it. Skipped and unknown_to_user are missing facts, and they are not
collapsed into no.

When more than one cause is present, missing_fact wins, then a document the
tool cannot see, then a contested question. A settled covered entity or
business associate is reported as that status. An open question on the other
branch does not downgrade it: a determined result cannot carry an unresolved
question. The founder's own covered-entity status wins when it applies, so
a company that both provides care and acts for a clinic is a covered entity.

Signed agreements are not read.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from compliance_copilot.models import (
    AmbiguityCause,
    CoveredEntityStatus,
    CustomerType,
    Determination,
    FieldState,
    HipaaSituation,
    StatedFacts,
)
from compliance_copilot.router.paths import (
    BILLS,
    CARE,
    CLINICAL,
    CUSTOMERS,
    CUSTOMERS_BILL,
    RECEIVES,
    customer_phrase,
    ordered,
)

_PROVIDER = CustomerType.CLINICS
_HEALTH_PLAN = CustomerType.INSURERS
_SUBCONTRACTOR = CustomerType.COMPANIES_HANDLING_PATIENT_DATA_FOR_PROVIDERS
_NOT_COVERED_CUSTOMERS = frozenset({CustomerType.CONSUMERS, CustomerType.EMPLOYERS})

_CLINIC_BILLING = (
    "whether your clinic customers bill insurers electronically, "
    "either directly or through a billing company"
)
_CAUSE_RANK = {
    AmbiguityCause.MISSING_FACT: 0,
    AmbiguityCause.REQUIRES_DOCUMENT_WE_CANNOT_SEE: 1,
    AmbiguityCause.CONTESTED_QUESTION: 2,
}


class DeterminationError(Exception):
    """The rules could not produce a determination from these facts."""


class _Kind(StrEnum):
    APPLIES = "applies"
    DOES_NOT = "does_not"
    NOT_CONSIDERED = "not_considered"
    OPEN = "open"


@dataclass(frozen=True, slots=True)
class _Fact:
    path: str
    state: FieldState
    value: bool | None


@dataclass(frozen=True, slots=True)
class _Branch:
    kind: _Kind
    paths: tuple[str, ...] = ()
    cause: AmbiguityCause | None = None
    questions: tuple[str, ...] = ()
    rationale: str = ""


@dataclass(frozen=True, slots=True)
class CoveredEntityDecision:
    """A determination and the founder-facing reasoning that produced it."""

    determination: Determination
    rationale: str


def determine(stated: StatedFacts) -> CoveredEntityDecision:
    """The covered-entity status of `stated`, with the field paths behind it.

    The product description is not read. The rules use `hipaa_situation` only.
    """

    situation = stated.hipaa_situation
    own = _own_covered_entity(situation)
    associate = _business_associate(situation)
    if own.kind is _Kind.APPLIES:
        return _decided(CoveredEntityStatus.COVERED_ENTITY, own)
    if associate.kind is _Kind.APPLIES:
        return _decided(CoveredEntityStatus.BUSINESS_ASSOCIATE, associate)

    opens = [branch for branch in (own, associate) if branch.kind is _Kind.OPEN]
    if opens:
        return _open_decision(opens)
    if own.kind is _Kind.DOES_NOT and associate.kind is _Kind.DOES_NOT:
        return _neither(own, associate)
    if own.kind is _Kind.DOES_NOT and associate.kind is _Kind.NOT_CONSIDERED:
        return _customers_were_not_asked(own)
    if own.kind is _Kind.NOT_CONSIDERED and associate.kind is _Kind.DOES_NOT:
        return _own_status_was_not_asked(associate)
    if own.kind is _Kind.NOT_CONSIDERED and associate.kind is _Kind.NOT_CONSIDERED:
        return _nothing_was_asked()
    raise DeterminationError(
        f"unhandled branches: own={own.kind}, business_associate={associate.kind}"
    )


def _own_covered_entity(situation: HipaaSituation) -> _Branch:
    """Provider who transmits: both facts yes. One no rules it out."""

    care = _bool_fact(situation, CARE)
    bills = _bool_fact(situation, BILLS)
    falses = [fact for fact in (care, bills) if _is_no(fact)]
    if falses:
        return _Branch(
            _Kind.DOES_NOT,
            paths=tuple(fact.path for fact in falses),
            rationale=_own_negative_rationale(falses),
        )
    if _is_yes(care) and _is_yes(bills):
        return _Branch(
            _Kind.APPLIES,
            paths=(CARE, BILLS),
            rationale=(
                "You provide care directly and you bill insurers electronically, so "
                "you are a health care provider transmitting health information in "
                "electronic form in connection with a covered transaction "
                "(45 CFR 160.103). You are a covered entity."
            ),
        )
    if care.state is FieldState.NOT_ASKED and bills.state is FieldState.NOT_ASKED:
        return _Branch(_Kind.NOT_CONSIDERED)
    gaps = [fact for fact in (care, bills) if not _is_yes(fact)]
    return _Branch(
        _Kind.OPEN,
        paths=(CARE, BILLS),
        cause=AmbiguityCause.MISSING_FACT,
        questions=tuple(_gap_question(fact) for fact in gaps),
        rationale=(
            "Whether you are a covered entity depends on both providing care and "
            "billing insurers electronically. The intake does not settle that, so "
            "this determination is unresolved."
        ),
    )


def _business_associate(situation: HipaaSituation) -> _Branch:
    """On behalf of a covered entity, which requires the customer's status."""

    customers = situation.customer_types
    if customers.state is FieldState.NOT_ASKED:
        return _Branch(_Kind.NOT_CONSIDERED)
    if customers.state in (FieldState.SKIPPED, FieldState.UNKNOWN_TO_USER):
        return _gap(
            (CUSTOMERS,),
            _customer_gap_question(customers.state),
            "Who your customers are is not in the intake, so whether you act for "
            "a covered entity is unresolved.",
        )

    types = customers.value
    if types is None:
        raise DeterminationError("answered customer_types has no value")
    receives = _bool_fact(situation, RECEIVES)
    if _is_no(receives):
        return _Branch(
            _Kind.DOES_NOT,
            paths=(CUSTOMERS, RECEIVES),
            rationale=(
                f"Your customers are {customer_phrase(types)}. You do not receive "
                "patient data from them, so you are not creating, receiving, "
                "maintaining, or transmitting protected health information on their "
                "behalf. You are not a business associate."
            ),
        )
    if set(types) <= _NOT_COVERED_CUSTOMERS:
        # `receives` no already returned above. Yes is cited and does not make
        # a consumer or employer a covered entity. Not asked is left out.
        paths = (CUSTOMERS, RECEIVES) if receives.state is FieldState.ANSWERED else (CUSTOMERS,)
        received = (
            " Receiving patient data from them does not change that."
            if _is_yes(receives)
            else ""
        )
        return _Branch(
            _Kind.DOES_NOT,
            paths=paths,
            rationale=(
                f"Your customers are {customer_phrase(types)}. Consumers and employers "
                "are not covered entities, so you are not a business associate of them."
                f"{received}"
            ),
        )
    if not _is_yes(receives):
        return _gap(
            (CUSTOMERS, RECEIVES),
            _gap_question(receives),
            "Your customers may be covered entities. Whether you receive patient "
            "data from them is not in the intake, so business-associate status is "
            "unresolved.",
        )

    settled_covered_entity, unresolved_clinics, clinics_are_not = _customer_status(
        situation, types
    )
    if settled_covered_entity:
        return _on_behalf_of_covered_entity(
            situation, types, clinics_are_covered=not clinics_are_not and _PROVIDER in types
        )
    if unresolved_clinics:
        return _gap(
            (CUSTOMERS, CUSTOMERS_BILL, RECEIVES),
            _clinic_billing_question(situation.customers_bill_insurers_electronically.state),
            "You receive patient data from clinic customers. Whether those clinics "
            "are covered entities depends on whether they bill insurers "
            "electronically, either directly or through a billing company. That "
            "fact is not in the intake, so this determination is unresolved.",
        )
    if _SUBCONTRACTOR in types:
        return _subcontractor(situation)
    paths = [CUSTOMERS, RECEIVES]
    if _PROVIDER in types:
        paths.append(CUSTOMERS_BILL)
    return _Branch(
        _Kind.DOES_NOT,
        paths=tuple(paths),
        rationale=(
            "Your clinic customers do not bill insurers electronically, so they "
            "are not covered entities under this rule. You are not their business "
            "associate."
        ),
    )


def _customer_status(
    situation: HipaaSituation, types: tuple[CustomerType, ...]
) -> tuple[bool, bool, bool]:
    """(a customer is a settled covered entity, clinic billing is open, clinics are not).

    A health plan is settled without reading the clinic-billing field. Clinic
    billing is open only when that field was skipped, unknown, or not asked,
    and no health plan has already settled the customer side.
    """

    health_plan = _HEALTH_PLAN in types
    if _PROVIDER not in types:
        return health_plan, False, False
    billing = situation.customers_bill_insurers_electronically
    if billing.state is not FieldState.ANSWERED:
        return health_plan, not health_plan, False
    if billing.value:
        return True, False, False
    return health_plan, False, True


def _on_behalf_of_covered_entity(
    situation: HipaaSituation,
    types: tuple[CustomerType, ...],
    *,
    clinics_are_covered: bool,
) -> _Branch:
    """The customer is a covered entity and the product receives their data.

    Clinical information is consulted here and not before. Not asked is left
    out of `derived_from`. No is the contested question. Yes is cited.
    """

    paths = [CUSTOMERS]
    if clinics_are_covered and _is_yes(_bool_fact(situation, CUSTOMERS_BILL)):
        paths.append(CUSTOMERS_BILL)
    paths.append(RECEIVES)
    clinical = _bool_fact(situation, CLINICAL)
    if clinical.state is FieldState.ANSWERED and clinical.value is False:
        paths.append(CLINICAL)
        return _Branch(
            _Kind.OPEN,
            paths=tuple(paths),
            cause=AmbiguityCause.CONTESTED_QUESTION,
            questions=(
                "Whether names, appointment times, and provider identity, without "
                "diagnoses, clinical notes, or test results, are protected health "
                "information under 45 CFR 160.103. The facts are known, and this "
                "legal question is not settled.",
            ),
            rationale=_contested_rationale(types),
        )
    if clinical.state in (FieldState.SKIPPED, FieldState.UNKNOWN_TO_USER):
        paths.append(CLINICAL)
        return _gap(
            tuple(paths),
            _gap_question(clinical),
            "You receive patient data from a covered entity. Whether that data is "
            "clinical information or only scheduling details is not in the intake, "
            "so this determination is unresolved.",
        )
    if _is_yes(clinical):
        paths.append(CLINICAL)
    return _Branch(
        _Kind.APPLIES,
        paths=tuple(paths),
        rationale=_associate_rationale(
            types, clinics_are_covered=clinics_are_covered, clinical_yes=_is_yes(clinical)
        ),
    )


def _subcontractor(situation: HipaaSituation) -> _Branch:
    """No settled covered entity, and the customer type is the subcontractor."""

    paths = [CUSTOMERS, RECEIVES]
    clinical = _bool_fact(situation, CLINICAL)
    if clinical.state in (FieldState.SKIPPED, FieldState.UNKNOWN_TO_USER):
        paths.append(CLINICAL)
        return _gap(
            tuple(paths),
            _gap_question(clinical),
            "You receive patient data for a customer that handles patient data for "
            "providers. Whether that data is clinical information is not in the "
            "intake, so this determination is unresolved.",
        )
    if clinical.state is FieldState.ANSWERED:
        paths.append(CLINICAL)
    data = "clinical information" if _is_yes(clinical) else "patient data"
    return _Branch(
        _Kind.OPEN,
        paths=tuple(paths),
        cause=AmbiguityCause.REQUIRES_DOCUMENT_WE_CANNOT_SEE,
        questions=(
            "Whether your customer is a business associate of the providers it "
            "serves depends on that customer's contracts with those providers. You "
            "are not a party to those contracts, and another intake question cannot "
            "settle it.",
        ),
        rationale=(
            f"You receive {data} for a customer that handles patient data for "
            "providers. Whether that customer is a business associate depends on "
            "its contracts with those providers. You are not a party to those "
            "contracts, and another intake question cannot settle it, so this "
            "determination is unresolved."
        ),
    )


def _own_negative_rationale(falses: list[_Fact]) -> str:
    sentences = []
    if any(fact.path == CARE for fact in falses):
        sentences.append(
            "You do not provide care directly, so you are not a covered health care "
            "provider under 45 CFR 160.103."
        )
    if any(fact.path == BILLS for fact in falses):
        sentences.append(
            "You do not bill insurers electronically, so you do not transmit health "
            "information in a covered transaction."
        )
    return " ".join(sentences)


def _associate_rationale(
    types: tuple[CustomerType, ...], *, clinics_are_covered: bool, clinical_yes: bool
) -> str:
    sentences: list[str] = []
    if clinics_are_covered:
        sentences.append(
            "Your customers include clinics that bill insurers electronically, "
            "either directly or through a billing company, so those clinics are "
            "covered entities."
        )
    if _HEALTH_PLAN in types:
        if clinics_are_covered:
            sentences.append(
                "Your customers also include a health plan, which is a covered "
                "entity by definition."
            )
        else:
            sentences.append(
                "Your customers include a health plan. A health plan is a covered "
                "entity under 45 CFR 160.103, so the clinic-billing question is "
                "not asked."
            )
    if clinical_yes:
        sentences.append(
            "You receive patient data from them, including clinical information, "
            "so you handle protected health information on their behalf."
        )
    else:
        sentences.append(
            "You receive patient data from them and handle it on their behalf."
        )
    sentences.append("You are a business associate under 45 CFR 160.103.")
    return " ".join(sentences)


def _contested_rationale(types: tuple[CustomerType, ...]) -> str:
    parts: list[str] = []
    if _PROVIDER in types:
        parts.append(
            "your clinic customers bill insurers electronically, so they are covered entities"
        )
    if _HEALTH_PLAN in types:
        parts.append("your customer includes a health plan, which is a covered entity")
    lead = ", and ".join(parts)
    return (
        f"{lead[0].upper()}{lead[1:]}, and you receive patient data from them. "
        "That data is scheduling details only: names, appointment times, and "
        "provider identity, not diagnoses, clinical notes, or test results. "
        "Whether that is protected health information under 45 CFR 160.103 is "
        "not settled, so this determination is unresolved."
    )


def _gap(paths: tuple[str, ...], question: str, rationale: str) -> _Branch:
    return _Branch(
        _Kind.OPEN,
        paths=paths,
        cause=AmbiguityCause.MISSING_FACT,
        questions=(question,),
        rationale=rationale,
    )


def _gap_question(fact: _Fact) -> str:
    subject, settles = _GAP_COPY[fact.path]
    return _question_for(fact.state, subject, settles)


def _customer_gap_question(state: FieldState) -> str:
    return _question_for(
        state,
        "who your customers are",
        "whether any customer is a covered entity you could act for",
    )


def _clinic_billing_question(state: FieldState) -> str:
    return _question_for(
        state,
        _CLINIC_BILLING,
        "whether those clinics are covered entities",
    )


def _question_for(state: FieldState, subject: str, settles: str) -> str:
    if state is FieldState.UNKNOWN_TO_USER:
        return f"You don't know {subject}. Finding that out would settle {settles}."
    if state is FieldState.SKIPPED:
        return f"The question of {subject} was skipped. Answering it would settle {settles}."
    if state is FieldState.NOT_ASKED:
        return f"We did not ask {subject}. That answer would settle {settles}."
    raise DeterminationError(f"no gap question for state '{state}' on {subject}")


_GAP_COPY: dict[str, tuple[str, str]] = {
    CARE: (
        "whether you provide care directly",
        "whether you are a health care provider under 45 CFR 160.103",
    ),
    BILLS: (
        "whether you bill insurers electronically",
        "whether you transmit health information in a covered transaction",
    ),
    RECEIVES: (
        "whether your product receives patient data from someone else",
        "whether you handle protected health information on a customer's behalf",
    ),
    CLINICAL: (
        "whether your product receives clinical information, such as diagnoses, "
        "clinical notes, or test results, or only scheduling details",
        "whether the data is protected health information or a contested question",
    ),
}


def _open_decision(opens: list[_Branch]) -> CoveredEntityDecision:
    """One cause. missing_fact, then a document, then a contested question."""

    cause = min((branch.cause for branch in opens), key=_CAUSE_RANK.__getitem__)
    chosen = [branch for branch in opens if branch.cause is cause]
    paths: list[str] = []
    questions: list[str] = []
    rationales: list[str] = []
    for branch in chosen:
        paths.extend(branch.paths)
        questions.extend(branch.questions)
        if branch.rationale:
            rationales.append(branch.rationale)
    return _ambiguous(cause, ordered(paths), tuple(dict.fromkeys(questions)), " ".join(rationales))


def _neither(own: _Branch, associate: _Branch) -> CoveredEntityDecision:
    return _decided(
        CoveredEntityStatus.NEITHER,
        _Branch(
            _Kind.DOES_NOT,
            paths=ordered((*associate.paths, *own.paths)),
            rationale=f"{own.rationale} {associate.rationale}",
        ),
    )


def _customers_were_not_asked(own: _Branch) -> CoveredEntityDecision:
    return _ambiguous(
        AmbiguityCause.MISSING_FACT,
        ordered((*own.paths, CUSTOMERS)),
        (
            _question_for(
                FieldState.NOT_ASKED,
                "who your customers are",
                "whether you act on behalf of a covered entity",
            ),
        ),
        own.rationale
        + " Who your customers are was not asked, so business-associate status "
        "is unresolved.",
    )


def _own_status_was_not_asked(associate: _Branch) -> CoveredEntityDecision:
    return _ambiguous(
        AmbiguityCause.MISSING_FACT,
        ordered((*associate.paths, CARE, BILLS)),
        (
            _question_for(*_paired(CARE)),
            _question_for(*_paired(BILLS)),
        ),
        associate.rationale
        + " Whether you yourself provide care and bill insurers was not asked, "
        "so covered-entity status is unresolved.",
    )


def _paired(path: str) -> tuple[FieldState, str, str]:
    subject, settles = _GAP_COPY[path]
    return FieldState.NOT_ASKED, subject, settles


def _nothing_was_asked() -> CoveredEntityDecision:
    return _ambiguous(
        AmbiguityCause.MISSING_FACT,
        ordered((CUSTOMERS, CARE, BILLS)),
        (
            _question_for(
                FieldState.NOT_ASKED,
                "who your customers are",
                "whether you act on behalf of a covered entity",
            ),
            _question_for(*_paired(CARE)),
            _question_for(*_paired(BILLS)),
        ),
        "The intake has not asked who your customers are, whether you provide "
        "care, or whether you bill insurers. There is not enough to determine "
        "covered-entity or business-associate status.",
    )


def _decided(status: CoveredEntityStatus, branch: _Branch) -> CoveredEntityDecision:
    if not branch.rationale.strip():
        raise DeterminationError(f"'{status}' has no rationale")
    return CoveredEntityDecision(
        determination=Determination(
            value=status,
            derived_from=ordered(branch.paths),
        ),
        rationale=branch.rationale,
    )


def _ambiguous(
    cause: AmbiguityCause,
    paths: tuple[str, ...],
    questions: tuple[str, ...],
    rationale: str,
) -> CoveredEntityDecision:
    if not rationale.strip():
        raise DeterminationError(f"'{cause}' has no rationale")
    return CoveredEntityDecision(
        determination=Determination(
            value=CoveredEntityStatus.AMBIGUOUS,
            derived_from=paths,
            ambiguity_cause=cause,
            unresolved_questions=questions,
        ),
        rationale=rationale,
    )


def _bool_fact(situation: HipaaSituation, path: str) -> _Fact:
    name = path.removeprefix("stated.hipaa_situation.")
    field = getattr(situation, name)
    return _Fact(path=path, state=field.state, value=field.value)


def _is_yes(fact: _Fact) -> bool:
    return fact.state is FieldState.ANSWERED and fact.value is True


def _is_no(fact: _Fact) -> bool:
    return fact.state is FieldState.ANSWERED and fact.value is False

"""Requirements and the deterministic checks that guard them (PRD §8.2, §8.6).

Checks 1–4 and 6 run when a `Requirement` is built, so an invalid one cannot
exist. Check 5 (scope, via the broadening lexicon) arrives in Phase 2.

Checks 1–3 need the corpus. It is passed in as a `RequirementContext`, either
as Pydantic validation context or with `requirement_context(...)`. With no
context, the requirement is rejected: the checks cannot be skipped.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType
from typing import Callable, Self, TypeVar

from pydantic import ValidationInfo, model_validator

from compliance_copilot.models._base import Identifier, ImmutableModel, NonBlankStr
from compliance_copilot.models.clause import (
    Clause,
    ClauseId,
    ClauseType,
    FrameworkDeclaration,
    Modality,
)


class EvidenceType(StrEnum):
    CITED = "cited"
    DERIVED = "derived"


class OutputType(StrEnum):
    BUILD = "build"
    OPERATE = "operate"
    IMPLIED_BUILD = "implied_build"


class Timing(StrEnum):
    """Two values only. There is no scale tag (PRD §8.2, decision 2026-10-17)."""

    APPLIES_NOW = "applies_now"
    DESIGN_TRIGGERED = "design_triggered"


_DERIVED_ONLY_FIELDS: tuple[str, ...] = ("rationale", "derived_from", "implication_id")

KeyT = TypeVar("KeyT")
ItemT = TypeVar("ItemT")


def _index(
    items: Iterable[ItemT], key: Callable[[ItemT], KeyT], kind: str
) -> Mapping[KeyT, ItemT]:
    indexed: dict[KeyT, ItemT] = {}
    for item in items:
        item_key = key(item)
        if item_key in indexed:
            raise ValueError(f"duplicate {kind} id in RequirementContext: {item_key}")
        indexed[item_key] = item
    return MappingProxyType(indexed)


@dataclass(frozen=True, slots=True)
class RequirementContext:
    """What a requirement is checked against: the corpus and the analysis so far."""

    clauses: Mapping[str, Clause]
    declarations: Mapping[str, FrameworkDeclaration]
    implication_ids: frozenset[str]
    requirements: Mapping[str, Requirement]

    @classmethod
    def build(
        cls,
        *,
        clauses: Iterable[Clause],
        declarations: Iterable[FrameworkDeclaration],
        implication_ids: Iterable[str] = (),
        requirements: Iterable[Requirement] = (),
    ) -> RequirementContext:
        return cls(
            clauses=_index(clauses, lambda c: c.id, "clause"),
            declarations=_index(declarations, lambda d: d.framework, "framework"),
            implication_ids=frozenset(implication_ids),
            requirements=_index(requirements, lambda r: r.id, "requirement"),
        )

    def with_requirement(self, requirement: Requirement) -> RequirementContext:
        """A new context that also knows `requirement`, so a derived one can point at it."""

        return RequirementContext.build(
            clauses=self.clauses.values(),
            declarations=self.declarations.values(),
            implication_ids=self.implication_ids,
            requirements=(*self.requirements.values(), requirement),
        )


_active_context: ContextVar[RequirementContext | None] = ContextVar(
    "requirement_context", default=None
)


@contextmanager
def requirement_context(context: RequirementContext) -> Iterator[RequirementContext]:
    """Make `context` the one `Requirement(...)` validates against inside the block."""

    token = _active_context.set(context)
    try:
        yield context
    finally:
        _active_context.reset(token)


def _resolve_context(info: ValidationInfo) -> RequirementContext:
    candidate = info.context if info.context is not None else _active_context.get()
    if not isinstance(candidate, RequirementContext):
        raise ValueError(
            "no RequirementContext available, so checks 1–3 cannot run and the "
            "requirement is rejected. Pass context=RequirementContext to "
            "model_validate, or build it inside `with requirement_context(...)`"
        )
    return candidate


class Requirement(ImmutableModel):
    """One requirement, cited or derived (PRD §8.6).

    There is no field for clause text: the renderer resolves it from
    `citation`. There is no styling field either: the renderer picks styling
    from `evidence_type`, and unknown fields are rejected (check 6).
    `derived_from` here is the id of the cited requirement a derived one
    started from, not a field path.
    """

    id: Identifier
    evidence_type: EvidenceType
    text: NonBlankStr
    output_type: OutputType
    timing: Timing
    citation: ClauseId
    clause_type: ClauseType | None = None
    modality: Modality | None = None
    rationale: NonBlankStr | None = None
    derived_from: Identifier | None = None
    implication_id: Identifier | None = None

    @model_validator(mode="after")
    def _run_checks(self, info: ValidationInfo) -> Self:
        problems = self._shape_problems()
        if not problems:
            problems = self._corpus_problems(_resolve_context(info))
        if problems:
            raise ValueError(f"requirement {self.id} rejected: " + "; ".join(problems))
        return self

    def _shape_problems(self) -> list[str]:
        """Checks 2 and 3, the parts that need no corpus."""

        problems: list[str] = []
        if self.evidence_type is EvidenceType.CITED:
            present = [f for f in _DERIVED_ONLY_FIELDS if getattr(self, f) is not None]
            if present:
                problems.append(
                    f"a cited requirement must not carry {', '.join(present)} "
                    "(check 2)"
                )
            if (
                self.modality is not None
                and self.clause_type is not ClauseType.IMPLEMENTATION_SPECIFICATION
            ):
                problems.append(
                    f"modality '{self.modality}' is only valid on an "
                    f"implementation_specification, not on clause_type "
                    f"'{self.clause_type}'. Standards carry no Required/Addressable "
                    "label (45 CFR 164.306(d)); they are mandatory under 164.306(c) "
                    "(check 2)"
                )
        else:
            missing = [f for f in _DERIVED_ONLY_FIELDS if getattr(self, f) is None]
            if missing:
                problems.append(
                    f"a derived requirement needs {', '.join(missing)} (check 3)"
                )
            if self.modality is not None:
                problems.append(
                    "a derived requirement must not carry modality: the clause's "
                    "modality describes the clause, not the inference (check 3)"
                )
            if self.clause_type is not None:
                problems.append(
                    "a derived requirement must not carry clause_type; it is "
                    "cited-only (check 3)"
                )
            if self.derived_from == self.id:
                problems.append("a derived requirement cannot derive from itself")
        return problems

    def _corpus_problems(self, context: RequirementContext) -> list[str]:
        """Check 1, the declaration part of check 2, and the resolution part of check 3."""

        clause = context.clauses.get(self.citation)
        if clause is None:
            return [
                f"citation '{self.citation}' does not resolve to a clause in the "
                "corpus (check 1)"
            ]

        problems: list[str] = []
        if self.evidence_type is EvidenceType.CITED:
            declaration = context.declarations.get(clause.framework)
            if declaration is None:
                problems.append(
                    f"framework '{clause.framework}' has no clause-type/modality "
                    "declaration; a framework without one cannot ship (check 2)"
                )
            else:
                problems.extend(
                    f"{p} (check 2)"
                    for p in declaration.violations(self.clause_type, self.modality)
                )
            if self.clause_type != clause.clause_type:
                problems.append(
                    f"clause_type '{self.clause_type}' does not match the corpus "
                    f"value '{clause.clause_type}' for {clause.id} (check 2)"
                )
            if self.modality != clause.modality:
                problems.append(
                    f"modality '{self.modality}' does not match the corpus value "
                    f"'{clause.modality}' for {clause.id} (check 2)"
                )
        else:
            source = context.requirements.get(self.derived_from or "")
            if source is None:
                problems.append(
                    f"derived_from '{self.derived_from}' does not resolve to a "
                    "requirement in this analysis (check 3)"
                )
            elif source.evidence_type is not EvidenceType.CITED:
                problems.append(
                    f"derived_from '{self.derived_from}' must point at a cited "
                    "requirement (check 3)"
                )
            if self.implication_id not in context.implication_ids:
                problems.append(
                    f"implication_id '{self.implication_id}' is not in the list of "
                    "implications (check 3)"
                )
        return problems

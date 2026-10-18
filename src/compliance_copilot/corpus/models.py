"""The shipped corpus file and the `get_clauses` result (PRD §8.5, §12.2, §15.1)."""

from __future__ import annotations

from collections import Counter
from enum import StrEnum
from typing import Annotated, Self

from pydantic import Field as PydanticField
from pydantic import model_validator

from compliance_copilot.corpus.labels import LabelError, read_labels
from compliance_copilot.models import Clause, Framework, FrameworkDeclaration
from compliance_copilot.models._base import ImmutableModel, NonBlankStr


class ScopeFilter(StrEnum):
    """How `get_clauses` narrows a framework's clauses.

    Only `all` exists: the prototype corpus is small enough to pass whole.
    Narrowing filters arrive with the first framework that needs one, e.g.
    PCI scope reduction (PRD §12.2).
    """

    ALL = "all"


class CorpusFile(ImmutableModel):
    """One corpus framework's declaration and clauses, as shipped in `corpus/data/`.

    The declaration travels with its clauses, so a corpus cannot load without
    one (PRD §8.5). `summary_framework` is the v1 framework the clauses answer
    to in the framework summary; several corpus frameworks can share one.

    Each clause's labels must be the ones its heading prints. A labelled
    clause must fit the declaration. An unlabelled clause (a definition, or a
    general rule such as 164.306(c)) sits outside the hierarchy and has
    `clause_type` null.
    """

    summary_framework: Framework
    declaration: FrameworkDeclaration
    clauses: Annotated[tuple[Clause, ...], PydanticField(min_length=1)]

    @model_validator(mode="after")
    def _clauses_fit_declaration(self) -> Self:
        framework = self.declaration.framework
        problems: list[str] = []
        repeated = sorted(i for i, n in Counter(c.id for c in self.clauses).items() if n > 1)
        if repeated:
            problems.append(f"clause ids repeat: {', '.join(repeated)}")
        for clause in self.clauses:
            if clause.framework != framework:
                problems.append(
                    f"{clause.id}: framework '{clause.framework}' does not match the "
                    f"file's declaration '{framework}'"
                )
                continue
            try:
                printed = read_labels(clause.heading)
            except LabelError as exc:
                problems.append(f"{clause.id}: {exc}")
                continue
            stored = (clause.clause_type, clause.modality)
            if stored != printed:
                problems.append(
                    f"{clause.id}: stored clause_type/modality {_pair(stored)} do not "
                    f"match the labels printed in heading {clause.heading!r}, which "
                    f"read as {_pair(printed)}"
                )
                continue
            if clause.clause_type is not None:
                problems.extend(
                    f"{clause.id}: {p}"
                    for p in self.declaration.violations(clause.clause_type, clause.modality)
                )
        if problems:
            raise ValueError(f"corpus file for {framework}: " + "; ".join(problems))
        return self


def _pair(labels: tuple[object, object]) -> str:
    return "/".join("null" if v is None else str(v) for v in labels)


class ClauseSet(ImmutableModel):
    """What `get_clauses` returns. Empty only with a reason, so silence is never an answer."""

    framework: Framework
    scope_filter: ScopeFilter
    clauses: tuple[Clause, ...]
    reason: NonBlankStr | None = None

    @model_validator(mode="after")
    def _empty_needs_reason(self) -> Self:
        if not self.clauses and self.reason is None:
            raise ValueError(f"an empty clause set for {self.framework} needs a reason")
        if self.clauses and self.reason is not None:
            raise ValueError(
                f"a non-empty clause set for {self.framework} must not carry a reason"
            )
        return self

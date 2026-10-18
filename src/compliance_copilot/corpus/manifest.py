"""The ingestion manifest: which clauses the corpus holds and where each one starts and ends.

Clause boundaries are a human decision recorded here. The words come from
the eCFR response, and the labels from the printed headings.
"""

from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Annotated, Literal, Self

import yaml
from pydantic import Field as PydanticField
from pydantic import StringConstraints, ValidationError, model_validator

from compliance_copilot.models import (
    ClauseStatus,
    Framework,
    FrameworkDeclaration,
    Jurisdiction,
)
from compliance_copilot.models._base import ImmutableModel, NonBlankStr
from compliance_copilot.strict_yaml import load_strict_yaml

DEFAULT_MANIFEST_PATH = Path(__file__).parent / "sources.yaml"

SectionNumber = Annotated[str, StringConstraints(pattern=r"^\d+\.\d+$")]
"""A CFR section number, e.g. `164.312`."""

ParagraphDesignator = Annotated[str, StringConstraints(pattern=r"^(\([a-z0-9]+\))+$")]
"""A paragraph path as eCFR prints it in anchors, e.g. `(a)(2)(i)`."""


class ManifestError(Exception):
    """The manifest cannot be read or does not match its schema."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


class ParagraphSource(ImmutableModel):
    """A clause that is one paragraph of a section, with any paragraphs nested under it.

    `starts_with` must match the start of exactly one paragraph in the
    section, as printed with markup removed. With no `ends_before` the clause
    is that one paragraph. `ends_before` names the first paragraph not
    included; `to_section_end` runs to the end of the section.
    """

    kind: Literal["paragraph"]
    section: SectionNumber
    paragraph: ParagraphDesignator
    starts_with: NonBlankStr
    ends_before: NonBlankStr | None = None
    to_section_end: bool = False

    @model_validator(mode="after")
    def _one_end_marker(self) -> Self:
        if self.ends_before is not None and self.to_section_end:
            raise ValueError(
                f"{self.section}{self.paragraph}: set ends_before or to_section_end, not both"
            )
        return self


class DefinitionSource(ImmutableModel):
    """One definition in a definitions section, from its term to the next definition."""

    kind: Literal["definition"]
    section: SectionNumber
    term: NonBlankStr


ClauseSource = Annotated[
    ParagraphSource | DefinitionSource, PydanticField(discriminator="kind")
]


class FrameworkSource(ImmutableModel):
    summary_framework: Framework
    declaration: FrameworkDeclaration
    clauses: Annotated[tuple[ClauseSource, ...], PydanticField(min_length=1)]

    @property
    def output_filename(self) -> str:
        return f"{self.declaration.framework.lower()}.json"


class Manifest(ImmutableModel):
    title: Annotated[int, PydanticField(gt=0)]
    status: ClauseStatus
    jurisdiction: Jurisdiction
    frameworks: Annotated[tuple[FrameworkSource, ...], PydanticField(min_length=1)]

    @model_validator(mode="after")
    def _no_repeats(self) -> Self:
        names = Counter(f.declaration.framework for f in self.frameworks)
        repeated = sorted(n for n, count in names.items() if count > 1)
        if repeated:
            raise ValueError(f"frameworks listed more than once: {', '.join(repeated)}")
        sources = Counter(c for f in self.frameworks for c in f.clauses)
        repeated_sources = [c for c, count in sources.items() if count > 1]
        if repeated_sources:
            raise ValueError(f"clauses listed more than once: {repeated_sources}")
        return self

    @property
    def sections(self) -> tuple[SectionNumber, ...]:
        """Every section the manifest draws on, in first-use order."""

        return tuple(dict.fromkeys(c.section for f in self.frameworks for c in f.clauses))


def load_manifest(path: Path = DEFAULT_MANIFEST_PATH) -> Manifest:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ManifestError(path, f"cannot read file: {exc}") from exc
    try:
        data = load_strict_yaml(raw)
    except yaml.YAMLError as exc:
        raise ManifestError(path, f"invalid YAML: {exc}") from exc
    if not isinstance(data, dict):
        raise ManifestError(path, "top level must be a mapping")
    try:
        return Manifest.model_validate(data)
    except ValidationError as exc:
        raise ManifestError(path, str(exc)) from exc

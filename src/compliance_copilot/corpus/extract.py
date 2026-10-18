"""Turn eCFR versioner XML into `Clause` objects, following the manifest. No I/O.

Text is copied character for character from each `<P>` with markup removed.
Paragraphs in a multi-paragraph clause are joined with a newline. One eCFR
markup artifact is removed: a `$` printed before an italic paragraph
designator, as in `$(<I>1</I>)`. The rendered rule reads `(1)`.

A section clause's heading is the italic title after its designator, without
the trailing period; its text is everything after the title. A definition's
heading is its italic term, without a trailing colon; its text is the whole
definition, term included, because the term is part of the sentence.
"""

from __future__ import annotations

import re
import xml.etree.ElementTree as ET
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime

from compliance_copilot.corpus.labels import read_labels
from compliance_copilot.corpus.manifest import (
    ClauseSource,
    DefinitionSource,
    FrameworkSource,
    Manifest,
    ParagraphSource,
)
from compliance_copilot.corpus.models import CorpusFile
from compliance_copilot.models import Clause

_DESIGNATORS = re.compile(r"^(\([a-z0-9]+\))+\s*$")
_ITALIC_DESIGNATOR_ARTIFACT = "$("


class ExtractionError(ValueError):
    """The source XML does not contain what the manifest expects."""


@dataclass(frozen=True, slots=True)
class SectionSnapshot:
    """One section as the eCFR versioner API returned it."""

    title: int
    section: str
    on_date: date
    xml: str
    retrieved_at: datetime


@dataclass(frozen=True, slots=True)
class SourceParagraph:
    """One `<P>`: the text before its opening italic run, the run itself, and the whole text."""

    lead: str
    italic: str | None
    full: str

    @property
    def is_definition_start(self) -> bool:
        return self.lead == "" and self.italic is not None


def _paragraph(element: ET.Element) -> SourceParagraph:
    lead = element.text or ""
    first = element[0] if len(element) else None
    full = "".join(element.itertext())
    italic: str | None = None
    if first is not None and first.tag == "I":
        italic = "".join(first.itertext())
        if lead == _ITALIC_DESIGNATOR_ARTIFACT and italic.isdigit():
            lead, full = lead[1:], full[1:]
    if "\n" in full:
        raise ExtractionError(f"paragraph contains a line break: {full[:80]!r}")
    return SourceParagraph(lead=lead, italic=italic, full=full.strip())


def parse_section(snapshot: SectionSnapshot) -> tuple[SourceParagraph, ...]:
    try:
        root = ET.fromstring(snapshot.xml)
    except ET.ParseError as exc:
        raise ExtractionError(f"{snapshot.section}: response is not XML: {exc}") from exc
    if root.tag != "DIV8" or root.get("N") != snapshot.section:
        raise ExtractionError(
            f"expected section {snapshot.section}, got <{root.tag} N={root.get('N')!r}>"
        )
    return tuple(_paragraph(p) for p in root.findall("P"))


def _strip_trailing(text: str, marks: str) -> str:
    stripped = text.strip()
    return stripped[:-1] if stripped and stripped[-1] in marks else stripped


def _paragraph_clause_parts(
    source: ParagraphSource, paragraphs: tuple[SourceParagraph, ...]
) -> tuple[str, str]:
    starts = [i for i, p in enumerate(paragraphs) if p.full.startswith(source.starts_with)]
    if len(starts) != 1:
        raise ExtractionError(
            f"{source.section}{source.paragraph}: starts_with {source.starts_with!r} "
            f"matches {len(starts)} paragraphs; it must match exactly one"
        )
    start = starts[0]
    if source.to_section_end:
        end = len(paragraphs)
    elif source.ends_before is None:
        end = start + 1
    else:
        ends = [
            i
            for i, p in enumerate(paragraphs)
            if i > start and p.full.startswith(source.ends_before)
        ]
        if not ends:
            raise ExtractionError(
                f"{source.section}{source.paragraph}: ends_before "
                f"{source.ends_before!r} not found after the start paragraph"
            )
        end = ends[0]

    first = paragraphs[start]
    if first.italic is None or not _DESIGNATORS.match(first.lead):
        raise ExtractionError(
            f"{source.section}{source.paragraph}: the start paragraph must open with a "
            f"designator and an italic title; got {first.full[:80]!r}"
        )
    after_designator = first.full.removeprefix(first.lead.strip()).lstrip()
    if not after_designator.startswith(first.italic):
        raise ExtractionError(
            f"{source.section}{source.paragraph}: the italic title {first.italic!r} does "
            "not directly follow the designator"
        )
    heading = _strip_trailing(first.italic, ".")
    body = after_designator.removeprefix(first.italic).strip()
    text = "\n".join([body, *(p.full for p in paragraphs[start + 1 : end])]).strip()
    return heading, text


def _definition_clause_parts(
    source: DefinitionSource, paragraphs: tuple[SourceParagraph, ...]
) -> tuple[str, str]:
    starts = [
        i
        for i, p in enumerate(paragraphs)
        if p.is_definition_start and _strip_trailing(p.italic or "", ":.") == source.term
    ]
    if len(starts) != 1:
        raise ExtractionError(
            f"{source.section}: definition {source.term!r} found {len(starts)} times; "
            "it must be found exactly once"
        )
    start = starts[0]
    end = next(
        (i for i in range(start + 1, len(paragraphs)) if paragraphs[i].is_definition_start),
        len(paragraphs),
    )
    text = "\n".join(p.full for p in paragraphs[start:end])
    return source.term, text


def _slug(term: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", term.lower()).strip("-")


def clause_id(title: int, source: ClauseSource) -> str:
    """`45-CFR-164.312-a-2-i` for a paragraph; `45-CFR-160.103-def-business-associate` for a definition."""

    prefix = f"{title}-CFR-{source.section}"
    if isinstance(source, DefinitionSource):
        return f"{prefix}-def-{_slug(source.term)}"
    return f"{prefix}-" + "-".join(re.findall(r"\(([a-z0-9]+)\)", source.paragraph))


def source_url(web_base_url: str, snapshot: SectionSnapshot, source: ClauseSource) -> str:
    """The eCFR page for the ingested date, anchored to the paragraph where eCFR has an anchor.

    Definitions link to the section: their anchor format is not verified.
    """

    base = (
        f"{web_base_url.rstrip('/')}/on/{snapshot.on_date.isoformat()}"
        f"/title-{snapshot.title}/section-{snapshot.section}"
    )
    if isinstance(source, ParagraphSource):
        return f"{base}#p-{source.section}{source.paragraph}"
    return base


def build_clause(
    manifest: Manifest,
    framework: FrameworkSource,
    source: ClauseSource,
    snapshot: SectionSnapshot,
    web_base_url: str,
) -> Clause:
    paragraphs = parse_section(snapshot)
    if isinstance(source, DefinitionSource):
        heading, text = _definition_clause_parts(source, paragraphs)
    else:
        heading, text = _paragraph_clause_parts(source, paragraphs)
    clause_type, modality = read_labels(heading)
    return Clause(
        id=clause_id(manifest.title, source),
        framework=framework.declaration.framework,
        text=text,
        heading=heading,
        clause_type=clause_type,
        modality=modality,
        status=manifest.status,
        jurisdiction=manifest.jurisdiction,
        source_url=source_url(web_base_url, snapshot, source),
        retrieved_at=snapshot.retrieved_at,
    )


def build_corpus_files(
    manifest: Manifest,
    snapshots: Mapping[str, SectionSnapshot],
    web_base_url: str,
) -> tuple[CorpusFile, ...]:
    """One validated `CorpusFile` per manifest framework, built from the section snapshots."""

    missing = [s for s in manifest.sections if s not in snapshots]
    if missing:
        raise ExtractionError(f"no snapshot for sections: {', '.join(missing)}")
    return tuple(
        CorpusFile(
            summary_framework=framework.summary_framework,
            declaration=framework.declaration,
            clauses=tuple(
                build_clause(manifest, framework, source, snapshots[source.section], web_base_url)
                for source in framework.clauses
            ),
        )
        for framework in manifest.frameworks
    )

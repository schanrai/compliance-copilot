"""Extraction from eCFR XML, and the eCFR fetch, without the network."""

from __future__ import annotations

from datetime import UTC, date, datetime

import httpx
import pytest

from compliance_copilot.corpus.ecfr import EcfrFetchError, fetch_section
from compliance_copilot.corpus.extract import (
    ExtractionError,
    SectionSnapshot,
    build_clause,
    parse_section,
)
from compliance_copilot.corpus.manifest import (
    DefinitionSource,
    FrameworkSource,
    Manifest,
    ParagraphSource,
)
from compliance_copilot.models import (
    Clause,
    ClauseStatus,
    ClauseType,
    Framework,
    FrameworkDeclaration,
    Jurisdiction,
    Modality,
)

RETRIEVED_AT = datetime(2026, 10, 17, tzinfo=UTC)
ON_DATE = date(2026, 10, 15)
WEB = "https://www.ecfr.gov"

SECTION_XML = """<?xml version="1.0" encoding="UTF-8"?>
<DIV8 N="999.1" TYPE="SECTION">
<HEAD>§ 999.1 Test section.</HEAD>
<P>(a)(1) <I>Standard: First thing.</I> Do the first thing.</P>
<P>(2) <I>Implementation specifications:</I></P>
<P>(i) <I>Sub thing (Required).</I> Do the sub thing.</P>
<P>(b) <I>General rule.</I> In this subpart:</P>
<P>(1) Must do one; and</P>
<P>$(<I>2</I>) Must do two, costing $5.</P>
<P>(c) <I>Next.</I> Something else.</P>
<P><I>Widget:</I> (1) Widget means a thing.</P>
<P>(2) <I>Widget</I> excludes gadgets.</P>
<P><I>Zebra</I> means a striped thing.</P>
</DIV8>
"""

DECLARATION = FrameworkDeclaration(
    framework="TEST-Graded",
    clause_types=frozenset({ClauseType.STANDARD, ClauseType.IMPLEMENTATION_SPECIFICATION}),
    grades_specifications=True,
)


def _snapshot(xml: str = SECTION_XML, section: str = "999.1") -> SectionSnapshot:
    return SectionSnapshot(
        title=45, section=section, on_date=ON_DATE, xml=xml, retrieved_at=RETRIEVED_AT
    )


def _manifest(*sources: ParagraphSource | DefinitionSource) -> tuple[Manifest, FrameworkSource]:
    framework = FrameworkSource(
        summary_framework=Framework.HIPAA, declaration=DECLARATION, clauses=sources
    )
    manifest = Manifest(
        title=45,
        status=ClauseStatus.IN_FORCE,
        jurisdiction=Jurisdiction.FEDERAL,
        frameworks=(framework,),
    )
    return manifest, framework


def _build(source: ParagraphSource | DefinitionSource) -> Clause:
    manifest, framework = _manifest(source)
    return build_clause(manifest, framework, source, _snapshot(), WEB)


def test_single_paragraph_clause_splits_heading_from_text() -> None:
    clause = _build(
        ParagraphSource(
            kind="paragraph",
            section="999.1",
            paragraph="(a)(1)",
            starts_with="(a)(1) Standard: First thing.",
        )
    )

    assert clause.id == "45-CFR-999.1-a-1"
    assert clause.heading == "Standard: First thing"
    assert clause.text == "Do the first thing."
    assert (clause.clause_type, clause.modality) == (ClauseType.STANDARD, None)
    assert str(clause.source_url) == (
        "https://www.ecfr.gov/on/2026-10-15/title-45/section-999.1#p-999.1(a)(1)"
    )


def test_specification_reads_its_modality_from_the_title() -> None:
    clause = _build(
        ParagraphSource(
            kind="paragraph",
            section="999.1",
            paragraph="(a)(2)(i)",
            starts_with="(i) Sub thing (Required).",
        )
    )

    assert (clause.clause_type, clause.modality) == (
        ClauseType.IMPLEMENTATION_SPECIFICATION,
        Modality.REQUIRED,
    )


def test_multi_paragraph_clause_keeps_every_paragraph_and_drops_the_dollar_artifact() -> None:
    clause = _build(
        ParagraphSource(
            kind="paragraph",
            section="999.1",
            paragraph="(b)",
            starts_with="(b) General rule.",
            ends_before="(c) Next.",
        )
    )

    assert clause.text == "In this subpart:\n(1) Must do one; and\n(2) Must do two, costing $5."
    assert (clause.clause_type, clause.modality) == (None, None)


def test_definition_runs_from_its_term_to_the_next_definition() -> None:
    clause = _build(DefinitionSource(kind="definition", section="999.1", term="Widget"))

    assert clause.id == "45-CFR-999.1-def-widget"
    assert clause.heading == "Widget"
    assert clause.text == "Widget: (1) Widget means a thing.\n(2) Widget excludes gadgets."
    assert str(clause.source_url).endswith("/section-999.1")


def test_ambiguous_start_marker_is_rejected() -> None:
    with pytest.raises(ExtractionError, match=r"matches \d+ paragraphs; it must match exactly one"):
        _build(
            ParagraphSource(kind="paragraph", section="999.1", paragraph="(a)", starts_with="(")
        )


def test_missing_end_marker_is_rejected() -> None:
    with pytest.raises(ExtractionError, match="ends_before"):
        _build(
            ParagraphSource(
                kind="paragraph",
                section="999.1",
                paragraph="(b)",
                starts_with="(b) General rule.",
                ends_before="(z) Nothing.",
            )
        )


def test_response_for_another_section_is_rejected() -> None:
    with pytest.raises(ExtractionError, match="expected section 164.312"):
        parse_section(_snapshot(section="164.312"))


def _client(handler: httpx.MockTransport) -> httpx.Client:
    return httpx.Client(transport=handler, follow_redirects=False)


def test_fetch_returns_the_section_snapshot() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/api/versioner/v1/full/2026-10-15/title-45.xml"
        assert request.url.params["section"] == "164.312"
        assert request.url.params["part"] == "164"
        return httpx.Response(200, text="<DIV8/>")

    with _client(httpx.MockTransport(handler)) as client:
        snapshot = fetch_section(
            client,
            api_base_url="https://www.ecfr.gov/api/versioner/v1",
            title=45,
            section="164.312",
            on_date=ON_DATE,
            clock=lambda: RETRIEVED_AT,
        )

    assert snapshot.xml == "<DIV8/>"
    assert snapshot.retrieved_at == RETRIEVED_AT


def test_fetch_reports_a_redirect_as_a_block_and_does_not_follow_it() -> None:
    calls: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(302, headers={"location": "https://www.ecfr.gov/bot-check"})

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(
        EcfrFetchError, match="Treat this as a block"
    ):
        fetch_section(
            client,
            api_base_url="https://www.ecfr.gov/api/versioner/v1",
            title=45,
            section="164.312",
            on_date=ON_DATE,
        )
    assert len(calls) == 1


def test_fetch_reports_an_error_status_with_the_body() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(406, text="This endpoint requires response compression.")

    with _client(httpx.MockTransport(handler)) as client, pytest.raises(
        EcfrFetchError, match="HTTP 406.*compression"
    ):
        fetch_section(
            client,
            api_base_url="https://www.ecfr.gov/api/versioner/v1",
            title=45,
            section="164.312",
            on_date=ON_DATE,
        )

"""Fetch one CFR section from the eCFR versioner API.

No retries and no redirects. The eCFR website answers scripted requests with
a redirect to a bot check, so a redirect is reported as a block rather than
followed. The versioner endpoint refuses uncompressed responses (HTTP 406);
httpx asks for gzip by default.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, date, datetime

import httpx

from compliance_copilot.corpus.extract import SectionSnapshot

USER_AGENT = "compliance-copilot-corpus-ingest/0.1"


class EcfrFetchError(Exception):
    """eCFR did not return the requested section."""


def section_url(api_base_url: str, title: int, on_date: date) -> str:
    return f"{api_base_url.rstrip('/')}/full/{on_date.isoformat()}/title-{title}.xml"


def fetch_section(
    client: httpx.Client,
    *,
    api_base_url: str,
    title: int,
    section: str,
    on_date: date,
    clock: Callable[[], datetime] = lambda: datetime.now(UTC),
) -> SectionSnapshot:
    url = section_url(api_base_url, title, on_date)
    params = {"part": section.split(".", 1)[0], "section": section}
    try:
        response = client.get(url, params=params)
    except httpx.HTTPError as exc:
        raise EcfrFetchError(f"{section}: request to {url} failed: {exc}") from exc
    retrieved_at = clock()
    if response.is_redirect:
        raise EcfrFetchError(
            f"{section}: eCFR redirected to {response.headers.get('location')!r}. "
            "Treat this as a block: enter the text by hand from eCFR in a browser "
            "and cross-check Cornell LII. Do not retry."
        )
    if response.status_code != httpx.codes.OK:
        raise EcfrFetchError(
            f"{section}: HTTP {response.status_code} from {response.url}: "
            f"{response.text[:300]!r}"
        )
    return SectionSnapshot(
        title=title,
        section=section,
        on_date=on_date,
        xml=response.text,
        retrieved_at=retrieved_at,
    )

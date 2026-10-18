"""Terminal rendering of one clause: citation, heading, modality line, full text, provenance.

The full text always renders. A partial quote is a paraphrase by omission (PRD §8.6).
A standard renders as "Standard — compliance is mandatory", never as "Required" (PRD §8.5).
"""

from __future__ import annotations

import re

from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from compliance_copilot.models import Clause, ClauseType, Modality

_PARAGRAPH_ID = re.compile(r"^(?P<title>\d+)-CFR-(?P<section>\d+\.\d+)-(?P<rest>.+)$")


def citation_label(clause_id: str) -> str:
    """`45-CFR-164.312-a-2-i` → `45 CFR 164.312(a)(2)(i)`; definitions → `45 CFR 160.103`."""

    match = _PARAGRAPH_ID.match(clause_id)
    if match is None:
        return clause_id
    base = f"{match['title']} CFR {match['section']}"
    rest = match["rest"]
    if rest.startswith("def-"):
        return base
    return base + "".join(f"({part})" for part in rest.split("-"))


def modality_line(clause: Clause) -> str:
    match (clause.clause_type, clause.modality):
        case (ClauseType.STANDARD, None):
            return "Standard — compliance is mandatory (45 CFR 164.306(c))"
        case (ClauseType.IMPLEMENTATION_SPECIFICATION, Modality.REQUIRED):
            return (
                "Implementation specification — Required: must be implemented "
                "(45 CFR 164.306(d)(2))"
            )
        case (ClauseType.IMPLEMENTATION_SPECIFICATION, Modality.ADDRESSABLE):
            return (
                "Implementation specification — Addressable: assess whether it is "
                "reasonable and appropriate; implement it if so, otherwise document why "
                "not and implement an equivalent alternative if reasonable and "
                "appropriate (45 CFR 164.306(d)(3))"
            )
        case (ClauseType.IMPLEMENTATION_SPECIFICATION, None):
            return (
                "Implementation specification — not labelled Required or Addressable; "
                "this framework does not grade its specifications"
            )
        case (None, None):
            return (
                "No standard or implementation specification label in the source "
                "(definition or general rule)"
            )
    raise ValueError(
        f"clause {clause.id}: no modality line for "
        f"{clause.clause_type}/{clause.modality}"
    )


def clause_panel(clause: Clause) -> Panel:
    title = f"{citation_label(clause.id)} — {clause.heading}"
    body = Group(
        Text(modality_line(clause), style="bold"),
        Text(""),
        Text(clause.text),
        Text(""),
        Text(
            f"{clause.framework} · {clause.id}\n"
            f"Source: {clause.source_url}\n"
            f"Retrieved: {clause.retrieved_at.isoformat()}",
            style="dim",
        ),
    )
    return Panel(body, title=title, title_align="left", expand=True)

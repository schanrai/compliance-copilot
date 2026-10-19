"""Framework summary and the ambiguous deliverable.

Unresolved and not assessed use different words and different styles. One means
the tool looked. The other means it did not.
"""

from __future__ import annotations

from rich.console import Group
from rich.panel import Panel
from rich.text import Text

from compliance_copilot.models import FrameworkSummaryEntry, SummaryCategory
from compliance_copilot.output.ambiguous import AmbiguousOutput

_CATEGORY = {
    SummaryCategory.IN_SCOPE: ("In scope — we looked, and it applies", "bold green"),
    SummaryCategory.OUT_OF_SCOPE: ("Out of scope — we looked, and it does not apply", "bold white"),
    SummaryCategory.UNRESOLVED: ("Unresolved — we looked and could not settle it", "bold yellow"),
    SummaryCategory.NOT_ASSESSED: ("Not assessed — we did not look", "dim"),
}


def category_style(category: SummaryCategory) -> str:
    return _CATEGORY[category][1]


def summary_panel(entries: tuple[FrameworkSummaryEntry, ...]) -> Panel:
    """Every v1 framework, each in exactly one category."""

    body: list[Text] = []
    for entry in entries:
        if body:
            body.append(Text(""))
        label, style = _CATEGORY[entry.category]
        body.append(Text(f"{entry.framework.value}  ·  {label}", style=style))
        body.append(Text(entry.reason))
    return Panel(Group(*body), title="Framework summary", title_align="left")


def ambiguous_panel(output: AmbiguousOutput) -> Panel:
    """Components 1–4 and 6, with component 5 visible as next."""

    body = [
        Text("1  What is unresolved", style="bold"),
        Text(output.what_is_unresolved),
        Text(""),
        Text("2  Why it is unresolved", style="bold"),
        Text(output.why_unresolved),
        Text(""),
        Text("3  What would settle it", style="bold"),
    ]
    for fact in output.facts_that_would_settle_it:
        body.append(Text(f"• {fact}"))
    body.extend(
        [
            Text(""),
            Text("4  What each outcome means", style="bold"),
            Text(output.if_you_are),
            Text(output.if_you_are_not),
            Text(""),
            Text("5  What to build regardless", style="bold dim"),
            Text(output.build_regardless, style="dim"),
            Text(""),
            Text("6  Question for counsel", style="bold"),
            Text(output.counsel_question),
        ]
    )
    return Panel(Group(*body), title="Unresolved — HIPAA", title_align="left")

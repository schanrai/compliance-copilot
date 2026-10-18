"""Command-line entry. Corpus commands; demo commands arrive in Phase 8.

Run with `uv run python -m compliance_copilot.cli <command>`.
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console

from compliance_copilot.config import load_settings
from compliance_copilot.corpus.ingest import ingest_corpus
from compliance_copilot.corpus.loader import ClauseNotFoundError, default_corpus
from compliance_copilot.corpus.models import ScopeFilter
from compliance_copilot.golden.loader import GoldenCaseError, load_golden_case
from compliance_copilot.log import configure_logging
from compliance_copilot.models import Framework
from compliance_copilot.render.clause import clause_panel
from compliance_copilot.render.determination import determination_panel
from compliance_copilot.router import RunError, run_determination

app = typer.Typer(no_args_is_help=True, add_completion=False)
console = Console()


@app.callback()
def _setup() -> None:
    configure_logging(load_settings())


@app.command()
def clause(clause_id: Annotated[str, typer.Argument(help="e.g. 45-CFR-164.312-b")]) -> None:
    """Print one clause with its full text and modality line."""

    try:
        found = default_corpus().clause(clause_id)
    except ClauseNotFoundError as exc:
        console.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    console.print(clause_panel(found))


@app.command()
def clauses(
    framework: Annotated[Framework, typer.Argument(help="v1 framework, e.g. HIPAA")],
    scope_filter: Annotated[ScopeFilter, typer.Option()] = ScopeFilter.ALL,
) -> None:
    """Print every clause `get_clauses` returns for a framework, or why there are none."""

    result = default_corpus().get_clauses(framework, scope_filter)
    if result.reason is not None:
        console.print(f"[yellow]{framework.value}: {result.reason}[/yellow]")
        return
    for found in result.clauses:
        console.print(clause_panel(found))
    console.print(f"{len(result.clauses)} clauses for {framework.value}")


@app.command()
def determine(
    case: Annotated[Path, typer.Argument(help="Path to one golden-set YAML case")],
) -> None:
    """Print the covered-entity determination for a golden-set case."""

    out = Console(file=sys.stdout)
    try:
        loaded = load_golden_case(case)
        run = run_determination(loaded.stated, analysis_id=loaded.id)
    except (GoldenCaseError, RunError) as exc:
        out.print(f"[red]{exc}[/red]")
        raise typer.Exit(code=1) from exc
    out.print(determination_panel(loaded.stated, run))
    out.print(f"{loaded.id}: {run.decision.determination.value.value}")


@app.command("ingest-corpus")
def ingest_corpus_command(
    on: Annotated[
        str, typer.Option(help="eCFR point-in-time date, YYYY-MM-DD")
    ],
) -> None:
    """Fetch the manifest's sections from the eCFR versioner API and rewrite the corpus."""

    try:
        on_date = date.fromisoformat(on)
    except ValueError as exc:
        raise typer.BadParameter(f"--on must be YYYY-MM-DD, got {on!r}") from exc
    if on_date > datetime.now().date():
        raise typer.BadParameter("--on cannot be in the future")
    written = ingest_corpus(load_settings(), on_date)
    for path in written:
        console.print(f"wrote {path}")


if __name__ == "__main__":
    app()

"""The broadening lexicon (PRD §15.2) and the lookup check 5 uses.

A requirement is rejected when its wording uses a term this file marks as
broader than a lexicon term inside one of the cited clause's operative
terms. The chain is transitive: health data is broader than protected health
information, which is broader than electronic protected health information.
Health information sits at the top of the 160.103 nest.

Matches are case-insensitive. A longer term wins over a term inside it, so
"electronic protected health information" is not also a use of "protected
health information".
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from functools import cache
from pathlib import Path

from pydantic import ValidationError, model_validator

from compliance_copilot.models._base import ImmutableModel, NonBlankStr
from compliance_copilot.strict_yaml import load_strict_yaml

DEFAULT_LEXICON_PATH = Path(__file__).resolve().parent / "lexicon.yaml"


class LexiconError(Exception):
    """The lexicon file cannot be used."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


class LexiconTerm(ImmutableModel):
    """One vocabulary entry. `narrower_than` names broader terms, not aliases."""

    term: NonBlankStr
    aliases: tuple[NonBlankStr, ...] = ()
    narrower_than: tuple[NonBlankStr, ...] = ()
    note: NonBlankStr | None = None


class Lexicon(ImmutableModel):
    """The shipped broadening lexicon."""

    terms: tuple[LexiconTerm, ...]

    @model_validator(mode="after")
    def _links_resolve(self) -> Lexicon:
        problems: list[str] = []
        by_term: dict[str, LexiconTerm] = {}
        surfaces: dict[str, str] = {}
        for entry in self.terms:
            if entry.term in by_term:
                problems.append(f"duplicate term {entry.term!r}")
            by_term[entry.term] = entry
            for surface in (entry.term, *entry.aliases):
                key = surface.casefold()
                owner = surfaces.get(key)
                if owner is not None:
                    problems.append(
                        f"surface {surface!r} belongs to both {owner!r} and {entry.term!r}"
                    )
                surfaces[key] = entry.term
            if len(set(entry.narrower_than)) != len(entry.narrower_than):
                problems.append(f"{entry.term!r} repeats a narrower_than target")
        for entry in self.terms:
            for broader in entry.narrower_than:
                if broader == entry.term:
                    problems.append(f"{entry.term!r} is narrower than itself")
                elif broader not in by_term:
                    problems.append(
                        f"{entry.term!r} is narrower than {broader!r}, which is not a term"
                    )
        if not problems:
            for term, broader in _broader_than(by_term).items():
                if term in broader:
                    problems.append(f"{term!r} is in its own broader chain")
        if problems:
            raise ValueError("lexicon: " + "; ".join(problems))
        return self

    def terms_in(self, text: str) -> frozenset[str]:
        """Canonical terms used in `text`. A longer match hides a term inside it."""

        found: set[str] = set()
        claimed: list[tuple[int, int]] = []
        for surface, canonical in self._surfaces():
            for start, end in _spans(text, surface):
                if _overlaps(start, end, claimed):
                    continue
                claimed.append((start, end))
                found.add(canonical)
        return frozenset(found)

    def broader_uses(
        self, text: str, operative_terms: Iterable[str]
    ) -> list[tuple[str, str]]:
        """`(used term, operative phrase)` where `used term` is broader than a term in the phrase."""

        used = self.terms_in(text)
        pairs: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        broader = _broader_than({entry.term: entry for entry in self.terms})
        for operative in operative_terms:
            for used_term in sorted(used):
                covered = self.terms_in(operative)
                if any(used_term in broader.get(covered_term, ()) for covered_term in covered):
                    pair = (used_term, operative)
                    if pair not in seen:
                        seen.add(pair)
                        pairs.append(pair)
        return pairs

    def _surfaces(self) -> tuple[tuple[str, str], ...]:
        pairs = [
            (surface, entry.term)
            for entry in self.terms
            for surface in (entry.term, *entry.aliases)
        ]
        return tuple(sorted(pairs, key=lambda pair: len(pair[0]), reverse=True))


def _broader_than(by_term: Mapping[str, LexiconTerm]) -> dict[str, frozenset[str]]:
    """For each term, the terms it is narrower than, following the chain."""

    direct = {term: set(entry.narrower_than) for term, entry in by_term.items()}
    for parents in direct.values():
        growing = True
        while growing:
            extra = {ancestor for parent in parents for ancestor in direct.get(parent, ())}
            growing = not extra <= parents
            parents |= extra
    return {term: frozenset(parents) for term, parents in direct.items()}


def _spans(text: str, surface: str) -> list[tuple[int, int]]:
    haystack = text.casefold()
    needle = surface.casefold()
    if len(haystack) != len(text) or len(needle) != len(surface):
        raise ValueError(
            f"term {surface!r} is not ASCII, so a case-insensitive match would shift"
        )
    spans: list[tuple[int, int]] = []
    start = 0
    while True:
        found = haystack.find(needle, start)
        if found < 0:
            return spans
        end = found + len(needle)
        before_ok = found == 0 or not haystack[found - 1].isalnum()
        after_ok = end == len(haystack) or not haystack[end].isalnum()
        if before_ok and after_ok:
            spans.append((found, end))
        start = found + 1


def _overlaps(start: int, end: int, claimed: list[tuple[int, int]]) -> bool:
    return any(start < claimed_end and end > claimed_start for claimed_start, claimed_end in claimed)


def load_lexicon(path: Path = DEFAULT_LEXICON_PATH) -> Lexicon:
    """Load the lexicon at `path`. Fails on missing, invalid, or inconsistent YAML."""

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise LexiconError(path, f"cannot read file: {exc}") from exc
    try:
        data = load_strict_yaml(raw)
    except Exception as exc:
        raise LexiconError(path, f"invalid YAML: {exc}") from exc
    try:
        return Lexicon.model_validate(data)
    except ValidationError as exc:
        detail = "; ".join(error["msg"] for error in exc.errors())
        raise LexiconError(path, detail) from exc


@cache
def default_lexicon() -> Lexicon:
    """The shipped lexicon, loaded once per process."""

    return load_lexicon(DEFAULT_LEXICON_PATH)

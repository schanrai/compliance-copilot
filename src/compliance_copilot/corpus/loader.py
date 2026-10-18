"""Load the shipped corpus and serve `get_clauses(framework, scope_filter)` (PRD §12.2).

Clause access is a lookup over a clause table, not a search. The corpus is
read from the JSON files in `corpus/data/`, never from the network.
"""

from __future__ import annotations

import json
import logging
from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from types import MappingProxyType

from pydantic import ValidationError

from compliance_copilot.corpus.models import ClauseSet, CorpusFile, ScopeFilter
from compliance_copilot.log import PipelineStage, log_stage
from compliance_copilot.models import Clause, ClauseId, Framework, FrameworkDeclaration

logger = logging.getLogger(__name__)

CORPUS_SUFFIX = ".json"
DEFAULT_DATA_DIR = Path(__file__).parent / "data"


class CorpusError(Exception):
    """The corpus, or one of its files, cannot be used."""

    def __init__(self, path: Path, reason: str) -> None:
        super().__init__(f"{path}: {reason}")
        self.path = path
        self.reason = reason


class ClauseNotFoundError(KeyError):
    """A clause id does not resolve in the corpus."""

    def __init__(self, clause_id: str) -> None:
        super().__init__(clause_id)
        self.clause_id = clause_id

    def __str__(self) -> str:
        return f"clause '{self.clause_id}' is not in the corpus"


def no_corpus_reason(framework: Framework) -> str:
    return (
        f"No {framework.value} clauses are in the corpus. The prototype does not "
        f"assess {framework.value}, so there is nothing to retrieve."
    )


@dataclass(frozen=True, slots=True)
class Corpus:
    """Every loaded corpus file, indexed by clause id and summary framework."""

    files: tuple[CorpusFile, ...]
    _by_id: Mapping[ClauseId, Clause]
    _by_framework: Mapping[Framework, tuple[Clause, ...]]

    @classmethod
    def from_files(cls, files: tuple[CorpusFile, ...], origin: Path) -> Corpus:
        if not files:
            raise CorpusError(origin, "the corpus has no files")
        problems: list[str] = []
        frameworks = Counter(f.declaration.framework for f in files)
        repeated_frameworks = sorted(f for f, n in frameworks.items() if n > 1)
        if repeated_frameworks:
            problems.append(f"frameworks declared twice: {', '.join(repeated_frameworks)}")
        ids = Counter(c.id for f in files for c in f.clauses)
        repeated_ids = sorted(i for i, n in ids.items() if n > 1)
        if repeated_ids:
            problems.append(f"clause ids repeat across files: {', '.join(repeated_ids)}")
        if problems:
            raise CorpusError(origin, "; ".join(problems))

        by_framework: dict[Framework, list[Clause]] = {}
        for corpus_file in files:
            by_framework.setdefault(corpus_file.summary_framework, []).extend(
                corpus_file.clauses
            )
        return cls(
            files=files,
            _by_id=MappingProxyType({c.id: c for f in files for c in f.clauses}),
            _by_framework=MappingProxyType(
                {k: tuple(v) for k, v in by_framework.items()}
            ),
        )

    @property
    def clauses(self) -> tuple[Clause, ...]:
        return tuple(self._by_id.values())

    @property
    def declarations(self) -> tuple[FrameworkDeclaration, ...]:
        return tuple(f.declaration for f in self.files)

    def clause(self, clause_id: str) -> Clause:
        try:
            return self._by_id[clause_id]
        except KeyError:
            raise ClauseNotFoundError(clause_id) from None

    def get_clauses(
        self, framework: Framework, scope_filter: ScopeFilter = ScopeFilter.ALL
    ) -> ClauseSet:
        """The clauses `framework` answers with. A framework with no corpus returns empty with a reason."""

        with log_stage(logger, PipelineStage.CORPUS_LOOKUP) as record:
            record.add(framework=framework.value, scope_filter=scope_filter.value)
            clauses = self._by_framework.get(framework, ())
            result = ClauseSet(
                framework=framework,
                scope_filter=scope_filter,
                clauses=clauses,
                reason=None if clauses else no_corpus_reason(framework),
            )
            record.add(clause_count=len(result.clauses), empty_reason=result.reason)
            return result


def _format_validation_error(exc: ValidationError) -> str:
    lines = [
        f"  {'.'.join(str(part) for part in error['loc']) or '<root>'}: {error['msg']}"
        for error in exc.errors()
    ]
    return "file does not match the CorpusFile schema:\n" + "\n".join(lines)


def read_corpus_file(path: Path) -> CorpusFile:
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise CorpusError(path, f"cannot read file: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise CorpusError(path, f"invalid JSON: {exc}") from exc
    try:
        return CorpusFile.model_validate(data)
    except ValidationError as exc:
        raise CorpusError(path, _format_validation_error(exc)) from exc


def load_corpus(data_dir: Path = DEFAULT_DATA_DIR) -> Corpus:
    """Load every `*.json` corpus file in `data_dir`. Fails on the first bad file, or on none."""

    with log_stage(logger, PipelineStage.CORPUS_LOAD) as record:
        record.add(data_dir=str(data_dir))
        if not data_dir.is_dir():
            raise CorpusError(data_dir, "corpus directory does not exist")
        paths = sorted(data_dir.glob(f"*{CORPUS_SUFFIX}"))
        corpus = Corpus.from_files(tuple(read_corpus_file(p) for p in paths), data_dir)
        record.add(
            files_loaded=len(corpus.files),
            clauses_loaded=len(corpus.clauses),
            frameworks=[d.framework for d in corpus.declarations],
        )
        return corpus


@cache
def default_corpus() -> Corpus:
    """The shipped corpus, loaded once per process."""

    return load_corpus(DEFAULT_DATA_DIR)


def get_clauses(
    framework: Framework,
    scope_filter: ScopeFilter = ScopeFilter.ALL,
    *,
    corpus: Corpus | None = None,
) -> ClauseSet:
    """`get_clauses` over `corpus`, or over the shipped corpus when none is given."""

    return (corpus if corpus is not None else default_corpus()).get_clauses(
        framework, scope_filter
    )

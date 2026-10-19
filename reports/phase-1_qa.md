# Phase 1 QA — Corpus

**Date:** 2026-10-17
**Question:** Are the demo clauses stored verbatim as `Clause` JSON behind `get_clauses()`, with `clause_type` and `modality` read from the source? Does 164.410 read as plan risk R2 believes?
**Verdict:** Gate 1 passes. 16 clauses, verbatim against the eCFR API and Cornell LII. `uv run pytest`: 204 passed, in this tree and in a fresh directory (`uv sync --frozen`). `pip-audit`: no known vulnerabilities. Nothing installed; `pyproject.toml` and `uv.lock` unchanged.

## Gate 1

| Check | Result |
|---|---|
| Every clause's text matches eCFR verbatim | **Pass.** Text is copied by script from the eCFR versioner API (point-in-time 2026-10-15). The raw responses are kept in `corpus/data/ecfr/2026-10-15/`, and `test_corpus_verbatim.py` rebuilds the shipped JSON from them and compares field by field. Every clause was also cross-checked against Cornell LII: 16/16, every line and heading found, after normalising whitespace, quotes and dashes. Boundaries checked by reading the XML: each clause ends at its next sibling paragraph or next definition |
| 164.312(b) `standard`/`null`; (a)(2)(i) `implementation_specification`/`required`; (a)(2)(iv) `implementation_specification`/`addressable`; 164.404(b) `implementation_specification`/`null` | **Pass.** Read from the printed heading by `corpus/labels.py`; a corpus file whose stored labels differ from its headings does not load |
| Every golden-set citation resolves through `get_clauses` | **Pass.** The only citation is `45-CFR-164.312-b`. The golden `clause_type`/`modality` also match the corpus |
| A clause prints readably with full text and modality line | **Pass.** `uv run python -m compliance_copilot.cli clause 45-CFR-164.312-b`. A standard prints "Standard — compliance is mandatory (45 CFR 164.306(c))", never "Required" |

**The tests test.** Removing "or use" from 164.312(b) (the PRD §8.6 paraphrase-by-omission) fails the verbatim test. Relabelling 164.312(b) as a specification stops the corpus loading.

## Task 1 — eCFR API

The versioner API works; no hand entry needed. It answers HTTP 406 to an uncompressed request ("requires response compression"). That is not a block: httpx asks for gzip by default. Five minutes of the 30-minute box. The renderer API (`/api/renderer/...`) redirects to the website's bot check, so it was not retried or used. Ingestion follows no redirects and does not retry; a redirect is reported as a block.

## R2 — 164.410(b) and (c): verified, as believed

- (b) is the business associate's deadline: "without unreasonable delay and in no case later than 60 calendar days after discovery of a breach."
- (c)(1) requires "the identification of each individual whose unsecured protected health information has been, or is reasonably believed by the business associate to have been, accessed, acquired, used, or disclosed during the breach." (c)(2) is stored with it, so the clause is whole.
- One wording difference from the plan: the heading is "Implementation specifications: Timeliness of notification" (plural). Its labels read as `implementation_specification`/`null`.
- **For you, not done here (PRD frozen):** the plan's R2 mitigation says to log in PRD §21 that §8.6 and §11.3 use 164.404(b) on a clinic-vendor scenario, where 164.410(b) applies.

## Decisions made in this phase

1. **Three corpus frameworks, all under `HIPAA` in the framework summary:** `HIPAA-Definitions` (160.103), `HIPAA-Security` (164.306, 164.312), `HIPAA-Breach-Notification` (164.404, 164.410). The third declaration was not requested. A framework cannot ship without one, and 160.103 belongs to neither of the other two. It declares no hierarchy, so definitions have `clause_type` null.
2. **The breach-notification declaration lists `standard` and `implementation_specification`, ungraded.** The source prints "Standard" at 164.404(a) and 164.410(a). PRD §8.5 lists `implementation_specification` only, marked "Verified against eCFR". No Subpart D standard is in this corpus, so neither choice changes a result today. **Candidate PRD §21 item.**
3. **164.306(c) and (d) have `clause_type` null.** Their headings are "Standards" and "Implementation specifications", with no colon label. They are general rules about the hierarchy, not members of it. A requirement citing either would fail check 2 under the Security declaration.
4. **Text and heading conventions.** A section clause's heading is its italic title without the trailing period; its text is everything after the title, and nested paragraphs are joined by newlines. A definition's text includes its term, because the term is part of the sentence. One eCFR XML artifact is removed: `$` before an italic paragraph number in 164.306(d)(3)(ii)(B). LII confirms the rule reads "(1)".
5. **Ids and URLs.** `45-CFR-164.312-a-2-i` for paragraphs; `45-CFR-160.103-def-business-associate` for definitions. `source_url` is pinned to the ingested date (`/on/2026-10-15/...`). Definitions link to the section, because eCFR's definition anchor format could not be verified.
6. **`get_clauses(framework, scope_filter)` returns a `ClauseSet`, not a bare list** (PRD §12.2 shows `list[Clause]`). It carries a reason when empty, so an empty result always says why. `ScopeFilter` has one value, `all`. Logged as PRD §21 item 11 on 2026-10-17. The code stays.

## Deferred / for later phases

- **Phase 2:** the 164.312 lead-in ("A covered entity or business associate must, in accordance with § 164.306:") is not part of any clause's text, as in the PRD §15.1 example. Who the obligation binds lives in that lead-in.
- **Definition closure** (PRD §15, "clauses carry their definitions") was not followed, as the clause list required. Terms used but not stored include subcontractor, health care clearinghouse, individually identifiable health information, workforce, and organized health care arrangement.

### Follow-up 2026-10-19

`health information` and `individually identifiable health information` were ingested from the same 2026-10-15 160.103 snapshot so the G-04 rationale can cite them (`reports/g-04_phi.md`). The other definition-closure gaps above remain.
- **Label reader limit:** Subpart D prints standards as "Standard—", not "Standard:". If 164.404(a) or 164.410(a) were ingested, they would read as unlabelled and load as null. Fix before ingesting any Subpart D standard.
- **Phase 0b open issue 2** (the derived requirement has no cited breach requirement to point at) is still open, due before Phase 6.
- **Not started:** operative terms, lexicon, implications, requirement prose. `operative_terms` and `implications` are empty on all 16 clauses.

## How to regenerate

```bash
uv run python -m compliance_copilot.cli ingest-corpus --on 2026-10-15
uv run python -m compliance_copilot.cli clauses HIPAA
```

# Phase 4 QA — Framework summary and ambiguous output

**Date:** 2026-10-19
**Question:** Does every golden case land HIPAA in the labelled category, with every other framework not assessed, and does an ambiguous case show components 1–4 and 6 with a counsel question that can be pasted as written?
**Verdict:** Gate 4 passes. `uv run pytest`: 291 passed. No new packages. No specialist runs. Phase 6 stays cut.

## Gate 4

| Check | Result |
|---|---|
| Golden framework summaries match | **Pass.** HIPAA follows the determination. HBNR, FTC Act §5, Washington, Connecticut, Nevada, Texas and Nebraska, SOC 2, and PCI DSS are not assessed |
| Ambiguous cases have components 1–4 and 6, and the counsel question is pasteable | **Pass.** G-05 and G-07, both `missing_fact`. The question cites 45 CFR 160.103, includes the product description, and names about 30 minutes. Settled cases produce none of this. G-04 was relabelled business associate the same day (`reports/g-04_phi.md`). G-07 was relabelled from `requires_document_we_cannot_see` the same day (`reports/g-07_missing_fact.md`) |
| Unresolved and not assessed render differently | **Pass.** Unresolved says "we looked and could not settle it." Not assessed says "we did not look." The styles differ |

Component 5 is on the ambiguous panel as "Specified, next." It is not filled in.

## What the founder sees

HIPAA's summary line uses the determination's reasoning and the same intake paths. An unresolved HIPAA line is followed by the six-part deliverable. A not-assessed line has no intake path, because the tool did not look.

## Deferred

- The cited 164.312(b) requirement. Phase 5, if the remaining time covers it.
- The derived requirement. Phase 6, cut because Monday started after 9am.
- Component 5's actual build-regardless list. Specified, next (PRD §17.9).

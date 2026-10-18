# Phase 2 QA — Operative terms, lexicon, check 5

**Date:** 2026-10-18
**Question:** Are operative terms tagged on the sixteen demo clauses, is the lexicon limited to the allowed links, and does check 5 reject a requirement that widens 164.312(b) to "health data" while accepting wording that stays inside that clause's operative terms?
**Verdict:** Gate 2 passes. `uv run pytest`: 210 passed. No new packages. `implications.yaml` is still the Phase 6 placeholder. Phase 3 was not started.

## Gate 2

| Check | Result |
|---|---|
| "implement comprehensive audit logging for all health data" citing `45-CFR-164.312-b` is rejected | **Pass.** Check 5. `health data` is broader than operative term `electronic protected health information` |
| A sentence that stays inside that clause's operative terms passes | **Pass.** Fixture sentence, not the Phase 5 template: "Record and examine activity in information systems that contain or use electronic protected health information." |

The eCFR verbatim test still rebuilds clause text, headings, and labels. It ignores `operative_terms` and `implications`, which are tagged by hand after ingestion.

## Close calls, resolved 2026-10-18

1. **Drop `contain or use` on 164.312(b).** §15.1's worked example omits it. No lexicon term is wider than it. The tags stay `record and examine activity`, `information systems`, `electronic protected health information`.
2. **Drop `maintain` on 164.312(a)(1).** Same kind of joint, between the systems and the data.
3. **Keep `Other transactions that the Secretary may prescribe by regulation`.** An unlisted type counts only when the Secretary adds it by regulation. The twelve named transaction examples stay out. The opening sentence already covers a transmission that meets it, so dropping one example does not change who the definition covers.

## Lexicon

`corpus/lexicon.yaml`. `narrower_than` is only the 160.103 nest and the known widening `health data`. No `weaker_than`. The addressable/required row is not in the file.

- `electronic protected health information` (aliases `ePHI`, `electronic PHI`) is narrower than `protected health information`.
- `protected health information` (alias `PHI`) is narrower than `individually identifiable health information` and `health data`.

Check 5 follows that chain. A longer term hides a term inside it, so the fixture sentence's `electronic protected health information` is not also a use of `protected health information`.

## Implications

`notification_deadline_implies_identification` is set on `45-CFR-164.404-b` and `45-CFR-164.410-b` only. Provisional Option A, for Phase 6. No implication entry was written. The matching decision stays open. No other clause is tagged.

## Does the clause imply engineering it never states?

Recorded from review. No new implication entries.

| Clause | Answer |
|---|---|
| `45-CFR-164.312-b` | **No.** A manual process can meet it. The clause allows a procedural mechanism |
| `45-CFR-164.312-a-1` | **No.** A technical policy or procedure can be physical or manual |
| `45-CFR-164.312-a-2-i` | **Yes.** A unique number can be assigned by hand. Identifying and tracking that identity needs an electronic system. The example given was a patient number; the clause's user is the person or program on the system |
| `45-CFR-164.312-a-2-iv` | **Yes.** There is no manual way to encrypt and decrypt |
| `45-CFR-164.306-c` | Determining whether there is an engineering requirement requires cross-referencing the safeguard sections |
| `45-CFR-164.306-d` | **No.** No language in the paragraph implies a build. It states assess, implement, document, or substitute |
| All seven `160.103` definitions | **No.** Definitions do not have an engineering requirement. Answered on business associate, covered entity, health care provider, health plan, and protected health information, then applied to the rest |
| `45-CFR-164.404-b` and `45-CFR-164.410-b` | **No.** The duty is to provide a notification. A phone call can be that notification |
| `45-CFR-164.410-c` | **No.** The notification can be a manual phone call or a list |

## Deferred

- The implication list entry for `notification_deadline_implies_identification`, and how a clause's tag is matched. Phase 6. The matching decision stays open.
- The Phase 5 template. The passing check 5 sentence is a fixture.
- Full Security Rule, the rest of Breach Notification, and the other v1 frameworks. Not this prototype.

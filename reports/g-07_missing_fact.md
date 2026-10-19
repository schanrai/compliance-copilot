# G-07 — Subcontractor customer is a missing fact

**Date:** 2026-10-19
**Question:** For software sold to a company that handles patient data for clinics, does business-associate status turn on contracts the founder is not a party to?
**Verdict:** No. The open question is whether those clinics are covered entities (they bill insurers electronically). G-07 is `missing_fact`. Relabelled the same day.

## Findings

1. **Covered-entity step.** A provider is a covered entity if they transmit health information electronically in a covered transaction. That is the billing question. It is not in the customer's contracts with the clinics.
2. **Business-associate step.** A person becomes a business associate by what they do, not by signing a contract (HHS Omnibus preamble; PRD §20, 2026-10-16). "Handles patient data for providers" is already the customer type.
3. **The tool does not read documents.** That is true of every cause. It is not a reason for a third label. `requires_document_we_cannot_see` only earns a distinct next action when asking the founder again is futile. No golden case made that true.
4. **G-05 and G-07.** Same hole. G-05: the founder doesn't know whether *their* clinic customers bill. G-07: the intake never asked whether the *end* providers bill.

## What changed

- G-07 expected cause is `missing_fact`. The founder **does not know** whether the end clinics bill (`unknown_to_user` on the billing field). The intake asks: "Do the healthcare providers your customer serves bill insurers electronically…?"
- The subcontractor rule reads that field. Yes is a business associate. No rules the end providers out as covered entities. Unknown, skipped, and not asked are `missing_fact`.
- `requires_document_we_cannot_see` stays on the model and in PRD §9. This prototype does not produce it. Logged as PRD §21 item 14.

## What stays open

- Intake has no field for "do the providers your customer serves bill?" The unresolved question is `not_asked` in substance. A dedicated field belongs in the Intake Agent loop, not this demo.
- `contested_question` is also unused after the G-04 relabel.

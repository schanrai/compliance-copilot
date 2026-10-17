# Compliance Co-pilot — Prototype Implementation Plan

**Date:** 2026-10-15. Calendar revised 2026-10-17.
**Demo:** Monday 19 October 2026, 5pm
**Specification:** `compliance-copilot-prd-v4.md` (frozen). Rationale for scope choices: `compliance-copilot-build-plan.md`.
**This plan supersedes the build plan's §1.5 sequence for the prototype.** The build plan remains the record of *why*; this is the record of *what, in what order, and how we know each step works*.

**Location:** `projects/compliance-copilot/docs/implementation.plan.md`. Moved here from `artifacts/module_8_ai_prds/compliance-copilot-implementation-plan.md` on 2026-10-16 (Phase 0a).

---

## 1. Locked scope

**Available time:** 21 hours from Saturday — Saturday 8h, Sunday 5h, Monday 8h ending at the 5pm demo. Friday's Phase 0a is done. Sunday afternoon is off. Monday's 8 hours assumes a 9am start; a later start cuts Phase 6 first, then Phase 5.

### In

| Item | Notes |
|---|---|
| Covered-entity determination — **three states** | covered entity · business associate · neither · ambiguous, with named cause. Plain Python rules, no model |
| Three step-3 rules | Customer status read from `customers_bill_insurers_electronically` (health plan customers need no question; `unknown_to_user` → ambiguous, `missing_fact`). Subcontractor customer type → ambiguous. Clinic using a billing company → never *neither* |
| Framework summary — four categories | Every framework lands in exactly one: in scope / out of scope / unresolved / not assessed |
| Ambiguous output — components 1–4 and 6 | Component 5 is out (PRD §17.9) |
| One **cited** requirement | 164.312(b), produced by **template** |
| One **derived** requirement | `notification_deadline_implies_identification`, from the breach-notification deadline |
| Visible decision trace | Chain terminates at intake field paths (PRD §13.4) |
| One-answer flip | Wellness app → contracts with a clinic → flips to covered |
| Live `pytest` run in the demo | Golden set + validator checks |

### Out — shown in the demo as *not assessed* or "next"

HBNR · Washington MHMDA · FTC §5 · CT, NV, TX/NE · SOC 2 · PCI · full Security Rule corpus · component 5 · interactive intake (golden-set cases are fixtures) · UI · database.

### Stretch — not in this demo

**Claude writes the cited user story** in place of the template, behind the same function (Phase S). There is no Monday evening. The template ships. The model stays unchosen.

---

## 2. Decisions logged 2026-10-15

1. **PRD v4 is frozen.** A spec issue is fixed only if it blocks the current phase; otherwise it goes in PRD §21. Once code exists, the Pydantic models are the source of truth for schemas.
2. **Template first, Claude as stretch.** The validators, trace and rendering must work with no model in the loop. The model call slots in behind the same interface.
3. **Corpus is the demo clauses only**, not the full Security Rule (§4 Phase 1).
4. **HBNR and Washington cut** from the prototype. The wellness app's *not covered* result shows HIPAA out of scope with its reasons and everything else *not assessed*. Diagram Example B is shown on the diagram, not run live.
5. **Golden-set cases are fixtures**, not an interactive intake. Named runs from the command line.
6. **Rendering is built per phase**, not at the end. Each phase's QA gate includes "it prints readably."
7. **Nothing new in the last 90 minutes of Monday.** One rehearsal, then the demo. No second rehearsal and no buffer.
8. **Golden set is time-boxed to 2.5 hours.** The user writes the labels; Claude pressure-tests them.

---

## 3. Calendar

Phase G and Phase 0b run **in parallel** on Saturday. You write the golden-set labels. The implementation chat writes the models. Sequential, the same work does not fit before 5pm Monday.

| Day | Hours | Phases | End-of-day checkpoint |
|---|---|---|---|
| **Fri 16** | done | 0a | Project installs, pytest passes, dependencies pinned. Models and golden-set cases were not written |
| **Sat 17** | 8 | G (2.5h, you) alongside 0b–0c (3h). Then 1 (2h), 2 (1h). Start 3 with whatever time is left | Eight fixtures load and validate. Corpus matches eCFR. Operative terms tagged |
| **Sun 18** | 5 | Finish 3 (5h total, so most of Sunday). Start 4 only after gate 3 passes | **All golden-set determination assertions pass.** If not → Phase 6 is cut, and Monday is 4, 5, 7, and the rehearsal |
| **Mon 19** | 8, stop 5pm | Finish 4 · 5 (2h) · 7 (1h) · 8 plus one rehearsal (2h). Phase 6 (2h) only if 4 and 5 are done by early afternoon | One clean rehearsal. Demo at 5pm. Nothing new in the last 90 minutes |

---

## 4. Phases

Each phase ends at a **QA gate**: named checks that must pass before the next phase starts. A failed gate is fixed before moving on, not carried forward. Each gate writes a short note to `reports/phase-<n>_qa.md` — what was checked, result, anything deferred. Five lines is enough.

### Phase G — Golden set (Fri, 2.5h)

**Goal:** the ground truth every later gate tests against.

**The user writes the golden-set cases and expected labels; Claude pressure-tests them.** The labels are a healthcare judgement.

**Slots.** The scenario sketches below come from decisions already made; the expected outcomes are drafts to confirm or correct in this session.

| ID | Scenario | Draft expectation | Why it's in |
|---|---|---|---|
| G-01 | Software sold to clinics; creates and stores patient records on their behalf; clinics bill insurance electronically; signed agreements | Business associate · HIPAA in scope · cited 164.312(b) | Diagram Example A. Clean *applies* |
| G-02 | Consumer wellness app; sold direct; tracks symptoms and medications; user entry + wearable; no clinic contracts, no patient data received, bills no insurer | Neither · HIPAA out of scope · HBNR *not assessed* | Diagram Example B intake. Clean *does not apply*; demo moment 1 |
| G-03 | G-02 with one answer changed: contracts with a clinic to handle patient data (clinic billing answered) | Business associate · HIPAA in scope | The one-answer flip |
| G-04 | Scheduling tool sold to clinics; names, appointment times, provider identity; no clinical notes; contract unseen | Ambiguous · `requires_document_we_cannot_see` or `contested_question` — decide which | PRD §9.1 worked example |
| G-05 | Clinic-facing tool; clinics' insurance billing `unknown_to_user` | Ambiguous · `missing_fact` | Second ambiguity cause |
| G-06 | Clinic customer bills through a billing company | Covered path or ambiguous — **never neither** | Adversarial: proxy-question trap |
| G-07 | Customer is a company that handles patient data for providers (subcontractor case) | Ambiguous | Prototype rule from step 3 |
| G-08 | Founder's company provides care directly and bills insurers electronically | Covered entity · HIPAA in scope | The third determined state |

**Every case also asserts:** the four-category framework summary (all non-HIPAA frameworks *not assessed* in the prototype), `derived_from` field paths, and that every trace chain terminates at intake.

**Ambiguous cases also assert:** components 1, 2, 3, 4 and 6 present; component 5 absent and labelled as next.

**Deferred:** the differential eval pair (PRD §10 layer 4) needs a one-word corpus variant. Scheduled as build plan §5 item 8, with the Module 10 golden-set work.

**Fixture format — one YAML file per case** in `tests/golden/cases/`:

```yaml
id: G-01
title: Records platform sold to clinics
stated:                       # subset of PRD §7.2, Field{value, source, state}
  hipaa_situation:
    customer_types: {value: [clinics], source: qa_answer, state: answered}
    customers_bill_insurers_electronically: {value: true, source: qa_answer, state: answered}
    # ...
expected:
  covered_entity_status: business_associate
  ambiguity_cause: null
  derived_from: [stated.hipaa_situation.customer_types, ...]
  framework_summary: {HIPAA: in_scope, HBNR: not_assessed, ...}
  requirements:
    - {citation: 45-CFR-164.312-b, evidence_type: cited, clause_type: standard, modality: null}
  ambiguous_components: null  # or [1, 2, 3, 4, 6]
```

**QA gate G**
- [ ] 8 cases written, each with every expected field filled
- [ ] Each ambiguous case names one cause, and the causes differ across cases
- [ ] Claude pressure-test done; disagreements resolved or logged
- [ ] Fixtures validate against the Phase 0 models (checked at the end of Phase 0)

---

### Phase 0 — Project setup and models (Fri, 4.5h)

**Goal:** a project that installs, runs, tests and logs, with the schemas that everything else builds on.

#### 0a. Infrastructure — file structure, libraries, environment

**Project location:** `projects/compliance-copilot/` in this repo, as its own git repository. *Default — change it here if you want it elsewhere.*

```
compliance-copilot/
├── pyproject.toml            # uv-managed; exact pinned versions
├── uv.lock                   # committed; hashes for reproducible installs
├── .python-version           # 3.12+
├── .env.example              # ANTHROPIC_API_KEY (stretch only), LOG_LEVEL
├── .gitignore                # .env, .venv, __pycache__, reports/scratch
├── README.md                 # how to install, run the demo, run the tests
├── docs/
│   └── implementation.plan.md   # this file, moved here
├── reports/                  # phase-<n>_qa.md notes
├── src/compliance_copilot/
│   ├── config.py             # settings from env; no hard-coded values
│   ├── log.py                # structured logging setup
│   ├── models/               # clause, requirement, trace, context, determination
│   ├── corpus/
│   │   ├── loader.py         # get_clauses(framework, scope_filter)
│   │   ├── data/             # clause JSON per framework
│   │   ├── lexicon.yaml      # broadening lexicon
│   │   └── implications.yaml # list of implications (one entry)
│   ├── router/               # covered-entity rules, framework summary
│   ├── output/               # ambiguous output builder
│   ├── specialists/          # HIPAA requirement producer (template → model)
│   ├── amender/              # implication match → derived requirement
│   ├── trace/                # append-only trace writer
│   ├── render/               # terminal rendering
│   └── cli.py                # `run <case>`
└── tests/
    ├── golden/cases/         # G-01 … G-08 YAML
    ├── golden/test_golden.py # parametrised over the cases
    └── unit/                 # validators, rules, loader
```

**Libraries — candidates; verify the current version of each at install time and pin exactly:**

| Need | Candidate |
|---|---|
| Schemas and validators | `pydantic` |
| Tests | `pytest` |
| Fixture and corpus files | `pyyaml` |
| Terminal rendering | `rich` |
| CLI | `typer` |
| Env vars | `python-dotenv` |
| HTTP (eCFR fetch, Phase 1) | `httpx` |
| Model calls (**stretch only**) | `anthropic` |

**Dependency security (global rule, non-negotiable):** check each package before install (PyPI, repo activity, maintainer); pin exact versions — no `>=`; **run `pip-audit` after every install** (e.g. `uv export --format requirements-txt | uvx pip-audit -r /dev/stdin`, or the equivalent); stop and flag on any vulnerability. `uv.lock` carries hashes.

#### 0b. Models

- `Field` wrapper: `value`, `source`, `state` — `unknown_to_user` is a first-class state (PRD §7.1)
- `ComplianceContextObject` — **only the parts the determination reads**: `hipaa_situation` (including `customers_bill_insurers_electronically` and the subcontractor customer type), the product description, and the `derived` block. Not the full schema
- `Clause` — PRD §15.1, including `clause_type`, `modality`, `operative_terms`, `implications`
- `Requirement` — PRD §8.6, with **checks 1–4 and 6 as Pydantic validators**, so an invalid requirement cannot be constructed. Check 5 (scope) arrives in Phase 2. `timing` is `applies_now` or `design_triggered` only (PRD §8.2). Every prototype requirement is `applies_now`. Do not branch on `design_triggered`, and do not add `applies_at_scale`
- `TraceStep` / `Trace` — PRD §13.1, with the §13.2 action enum. Append-only
- `Determination` and `FrameworkSummaryEntry`

#### 0c. Harness

- `pytest` runs; one trivial test passes
- The golden-set loader reads every YAML case into the models; malformed fixtures fail loudly
- Logging writes one structured line per pipeline stage

**QA gate 0**
- [ ] Fresh clone → `uv sync` → `pytest` passes
- [ ] `pip-audit` clean; every version pinned exactly
- [ ] All 8 golden cases load and validate against the models
- [ ] Unit tests: a cited requirement with `modality: required` on a `standard` is **rejected**; a derived requirement missing `implication_id` is **rejected**; a requirement with no `evidence_type` is **rejected**
- [ ] No hard-coded paths or keys; config comes from env

---

### Phase 1 — Corpus (Sat, 2h)

**Goal:** the clauses the demo touches, stored as `Clause` JSON behind `get_clauses()`.

**Clause list:**

| Source | Clauses | Why |
|---|---|---|
| 45 CFR 160.103 | Definitions: business associate (including the subcontractor wording), covered entity, health care provider, health plan, protected health information, electronic protected health information, transaction | The determination is built from these |
| 45 CFR 164.306 | (c), (d) | Standards are mandatory; the Required/Addressable scheme. Drives rendering |
| 45 CFR 164.312 | (a)(1) standard; (a)(2)(i) a *Required* spec; (a)(2)(iv) an *Addressable* spec; (b) standard | 164.312(b) is the cited requirement. The others give the validator all three clause-type/modality states |
| 45 CFR 164.404 | (b) | Breach notification deadline — covered entity. Derived requirement source |
| 45 CFR 164.410 | (b), (c) | Breach notification — **business associate** to covered entity. See risk R2 |

**Tasks**
1. **30-minute check:** can a script fetch these from the eCFR API (`ecfr.gov/api/versioner/v1/...`)? eCFR's website blocked automated fetches on 15 Oct. If the API also blocks → enter by hand from eCFR in a browser, cross-checked against Cornell LII
2. Read `clause_type` and `modality` **from the source text** — "Standard:" in the heading; "(Required)" / "(Addressable)" after a spec's title. Never infer
3. `get_clauses(framework, scope_filter)` returns the whole set for HIPAA; *not assessed* frameworks return empty with a reason
4. Record `source_url` and `retrieved_at` on every clause

**QA gate 1**
- [ ] Every clause's text matches eCFR verbatim (spot-check every one — the corpus is small enough)
- [ ] 164.312(b) is `standard` / `null`; (a)(2)(i) `implementation_specification` / `required`; (a)(2)(iv) `implementation_specification` / `addressable`; 164.404(b) `implementation_specification` / `null`
- [ ] Every citation in the golden set resolves through `get_clauses`
- [ ] A clause prints readably with its full text and modality line

---

### Phase 2 — Operative terms and lexicon (Sat, 1h)

**Goal:** trigger-fidelity data, and §8.6 check 5.

**Tasks**
1. Tag `operative_terms` on every clause by hand, following PRD §15.1. Copy phrases verbatim. Include a phrase only when dropping it or widening it would change the obligation. Leave out means the clause leaves open. Use the same test on the 160.103 definitions and on 164.306(c) and (d). A close call is copied and noted, then resolved after the sitting
2. Write `lexicon.yaml` from the recurring vocabulary — ePHI ⊂ PHI ⊂ health information, and the rest (PRD §15.2)
3. Add check 5 (scope) to the `Requirement` validator
4. Tag `implications` on 164.404(b) and 164.410(b). **Provisional:** the prototype uses Option A only to attach the one implication Phase 6 needs. The matching decision stays open (PRD §8.7)
5. While tagging, note every clause that looks like it implies engineering it never states, and the implication it suggests. Do not write new entries yet. The notes are evidence for two open decisions: how implications are matched (PRD §8.7) and how the list grows (PRD §17.11)

**QA gate 2**
- [ ] *"implement comprehensive audit logging for all health data"* citing 164.312(b) is **rejected** (the PRD §8.6 example)
- [ ] The wording of the 164.312(b) template requirement **passes**

---

### Phase 3 — Covered-entity determination (Sat–Sun, 5h)

**Goal:** the branch the reviewer will probe hardest. Plain Python, no model.

**Tasks**
1. Rules from 160.103 over `hipaa_situation`: covered entity (provides care **and** transmits electronically in a covered transaction); business associate (acts on behalf of a covered entity — which requires the **customer's** status); neither; ambiguous with a named cause
2. The three locked rules:
   - Provider customers → read `customers_bill_insurers_electronically`. Health plan customers are covered entities with no question. `unknown_to_user` → ambiguous, `missing_fact`
   - Subcontractor customer type → ambiguous
   - Billing company → never *neither*
3. Every result carries `derived_from` field paths and `unresolved_questions[]`
4. Write the intake and router trace steps
5. Render the determination and its reasoning readably

**QA gate 3 — the critical checkpoint**
- [ ] Every golden case's `covered_entity_status`, `ambiguity_cause` and `derived_from` match
- [ ] G-02 → G-03: one field changed, determination flips
- [ ] G-06 never returns *neither*
- [ ] Unit tests cover each rule branch, including `skipped` vs `not_asked` vs `unknown_to_user`
- [ ] **If this gate fails at end of Sunday → Phase 6 is cut on Monday**

---

### Phase 4 — Routing, framework summary, ambiguous output (Sun–Mon, 3h)

**Goal:** what the founder sees at Gate 2.

**Tasks**
1. Framework summary: HIPAA from the determination; every other v1 framework *not assessed* with a plain reason
2. Ambiguous determination → HIPAA *unresolved*; no specialist runs (PRD §9)
3. Ambiguous output components 1, 2, 3, 4 and 6, built from the determination and its `unresolved_questions`. Component 5 shown as "specified, next" — never silently missing
4. Render both

**QA gate 4**
- [ ] Golden framework summaries match
- [ ] Every ambiguous case has components 1–4 and 6; the counsel question is pasteable as written
- [ ] *Unresolved* and *not assessed* render visibly differently

---

### Phase 5 — Cited requirement, template (Mon, 2h). Next cut after Phase 6 if Monday starts after 9am.

**Goal:** one cited requirement out of the HIPAA branch, with its trace.

**Tasks**
1. A HIPAA specialist function: in scope → `get_clauses` → produce the 164.312(b) requirement **from a template**, filling company-specific wording
2. **The function's interface is what the stretch model call implements later** — same inputs, same `Requirement` output, same validators
3. Specialist trace step (`received_clause_set`, `emitted_requirement`)
4. Render as a user story: full clause text, *"Standard — compliance is mandatory (45 CFR 164.306(c))"*, never "Required"

**QA gate 5**
- [ ] G-01, G-03, G-08 produce the requirement; G-02 and ambiguous cases do not
- [ ] The trace chain runs intake → router → specialist and terminates at intake field paths

---

### Phase 6 — Derived requirement (Mon, 2h, only if gates 3, 4 and 5 have passed by early afternoon)

**Goal:** demo moment 2 — the requirement that appears nowhere in the regulation.

**Tasks**
1. Load `notification_deadline_implies_identification` from `implications.yaml`
2. Look up which clause carries the tag for the determination: covered entity → 164.404(b); business associate → 164.410(b) (risk R2)
3. Produce the derived requirement: `evidence_type: derived`, `citation`, `rationale`, `derived_from`, `implication_id`; no modality
4. Amender trace steps (`classified_output_type`, `derived_via_implication`)
5. Render with the *Derived — not stated in the regulation* marker and the full source clause

**QA gate 6**
- [ ] Derived requirement present on the in-scope cases, absent elsewhere
- [ ] Validators reject it if `implication_id` or `rationale` is removed
- [ ] Derived count ≤ cited count (PRD §10.1)

---

### Phase 7 — Golden set wired end to end (Mon, 1h)

**Goal:** the test run shown live in the demo.

**Tasks**
1. `test_golden.py` parametrised over all 8 cases, asserting per stage: determination, summary, requirements, trace termination, ambiguous components
2. Readable test names, so the live run reads as a list of claims

**QA gate 7**
- [ ] All green
- [ ] Breaking a rule on purpose (e.g. G-06 returns *neither*) turns a test red — the tests are actually testing

---

### Phase S — Stretch: not in this demo

There is no Monday evening. The cited requirement ships from the template. Phase S moves to after the demo, with the model still unchosen.

**Tasks**
1. **Choose the model.** Check the current Claude model line-up, pricing and structured-output support at the time (use the `claude-api` reference, not memory). Not decided now
2. Implement the Phase 5 interface with a model call — structured output into `Requirement`; the model supplies a clause **identifier**, never clause text (PRD §8.6)
3. **On any failure** (validation, timeout, API error) → fall back to the template, log it, and record a trace step. The demo never breaks because of the model
4. Log tokens and latency per call
5. Add the API key via `.env`; `pip-audit` after installing `anthropic`

**QA gate S**
- [ ] Golden tests still all green with the model on
- [ ] Forced failure falls back to the template cleanly
- [ ] Deferred. Do not start this phase before the demo. The template ships on Monday

---

### Phase 8 — Demo commands (Mon, before 5pm, 1h plus one rehearsal)

**Tasks**
1. `run <case>` for the named golden-set cases — at least `records-platform` (G-01), `wellness-app` (G-02), `scheduling-tool` (G-04)
2. The flip as its own command (`run wellness-app --contracts-with-clinic`, or G-03 as a named run). No live file edits
3. A demo script: order of runs, what to say at each, where the *not assessed* list makes the honesty point

**QA gate 8**
- [ ] One rehearsal, start to finish, including the live `pytest` run, with no edits during it. It happens in the last 90 minutes before 5pm

---

## 5. Risks

| # | Risk | Mitigation |
|---|---|---|
| R1 | eCFR blocks scripted fetches | Hand entry from the browser, cross-checked against Cornell LII. Corpus is ~15 clauses |
| R2 | **The derived example's clause depends on the branch.** 164.404(b) is a *covered entity's* deadline to notify individuals. A *business associate* notifies the covered entity under **164.410** — believed (b) timeliness, (c) content including identification of each affected individual. Unverified | Verify 164.410 in Phase 1. If it reads as believed, it is a *better* source for the BA case. Log PRD §8.6 / §11.3 (which use 164.404(b) on a clinic-vendor scenario) in PRD §21 |
| R3 | Phase 3 overruns — it is the hardest logic | Sunday checkpoint cuts Phase 6. Golden set written first makes "done" unambiguous |
| R4 | Golden-set session overruns | Hard 2.5h stop. Unlabelled cases are dropped, not rushed |
| R5 | Production-quality standards vs a 21h budget | Quality applies to what is built; scope is what flexes. Phase 6, then Phase 5. No shortcuts inside a phase |

---

## 6. What the demo will say is next

- Claude writing requirements (if Phase S didn't land)
- Component 5 — specified; production method open (PRD §17.9)
- HBNR and the *not covered* branch's obligations (diagram Example B)
- State laws, SOC 2, PCI — v1 scope, not prototype
- The full Security Rule corpus
- Counsel review of the golden set

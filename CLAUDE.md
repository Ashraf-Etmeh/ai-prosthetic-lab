# CLAUDE.md — AI Prosthetic Lab

A working local prototype of a decision-support tool for prosthetics
specialists (Flask, RAG: local bge-m3 search plus cloud-model summaries,
Gemini free tier or Claude API, backed by checked quotes, English/Arabic pages).
Extend it; don't rebuild it. Before changing anything, read
`docs/SYSTEM_DESCRIPTION.md` (what it does and how it is built), `README.md`
(how to run it, and the folder layout), `docs/FUTURE_WORK.md` (decisions,
measurements, open items) and `docs/design/SYSTEM_DESIGN.md` (the target
system the owner designed, with its screens in `docs/design/`; where the two
differ it says where the build is heading, and this file still sets the rules).

## Principles that never change

1. **It supports the specialist's decision; it never makes it.** No output
   may diagnose, prescribe, choose a component, rank components, or say
   whether a patient is ready for fitting. Pages show information next to
   what the sources say, and the specialist decides.
2. **Every sentence is backed by the source's own words.** Every quote and
   grade shown is copied word for word from a catalogued document, with its
   page. The summary sentences are written by a language model, labelled as
   AI, and each carries such a quote, which code checks word for word
   against its passage before it is shown; a sentence whose quote fails is
   removed. No clinical sentence is written by the code. Whether a statement
   applies to a case follows only from the source's own wording.
3. **Search stays local; one cloud language model writes the summaries.**
   Retrieval uses the local embedding model. One cloud language model,
   behind one swap point (`reasoning/writer.py`), writes the summary
   sentences from the retrieved passages: the Gemini API's free tier, or
   the Claude API (`LLM_PROVIDER` in `shared/config.py`); no other cloud
   service. Without it the app still works and shows the passages without
   summaries. (Owner's decisions: 2026-10-11, replacing "no language model
   and no cloud service"; 2026-10-13, Gemini's free tier by default.)
4. **Fake test data only.** Never collect or store patient identifiers
   (name, date of birth, address, record numbers). Part of each case is
   sent to the cloud model with the passages (its amputation level, side
   and recorded K-level, never what was typed: `case_for_prompt` in
   `prosthetics/rag.py`, since 2026-10-16; an orthotic case: condition, side
   and months since onset, `orthotics/rag.py`, but only once the owner sets
   `ORTHOTIC_CLOUD_AI`, off since 2026-10-23), which makes this doubly
   important: on Gemini's free tier Google uses what is sent to improve its
   products and human reviewers may read it.
5. **Two interface languages: English and Arabic (right to left).** Quotes
   and citations stay in the language of their source and are never
   translated.

## Working rules for every change

- **All tests keep passing** (`python -m unittest`). A change that breaks a
  test is not finished.
- **Every quote is checked word for word** against its page in
  `data/knowledge/extracted/<doc_id>.txt`. Quotes in the AI summaries are checked at
  run time by `reasoning/quote_check.py` before they are shown (that check
  has its own tests). Statements added to
  `prosthetics/component_guide.py` or `prosthetics/fitting_guide.py` are covered
  by `prosthetics/tests/test_component_guide.py` (quote on its page, list items in
  order, VA/DoD grade as printed); quotes kept anywhere else need an
  equivalent test. These tests skip when `data/knowledge/extracted/` is missing:
  generate it (`python -m knowledge.ingest`) so a skip is never mistaken
  for a pass.
- **Every new interface text gets its Arabic entry** in `shared/i18n.py`.
  `shared/tests/test_i18n.py` enforces it; a key built at runtime (e.g.
  `'section.' ~ key`) must also be added to its expected-keys test.
- **The review log is append-only.** Lines in `data/records/review_log.jsonl` are
  never edited or removed. Any change to the shape of a log entry raises
  `LOG_VERSION` in `review/decision_log.py`, and everything that reads the
  log must still read lines from earlier versions.
- **Clinical judgements come only from the owner.** A knowledge item's
  evidence layer, evidence tag and confidence are set only from the owner's
  rule table (`data/knowledge/evidence_rules.csv`) or values the owner
  gives, and the item records which (`assigned_by`: a rule id such as R1,
  or "manual"); population and limitations only from the owner's values
  (rules never set them). Code applies them and never infers, normalises or
  fills them in; neither does Claude, and neither edits the rule table.
  Copying a grade exactly as the source prints it is allowed (and tested,
  as `grade_as_printed`); anything without an owner's rule or value stays
  "unassigned" or empty. Clinic rules (hard stops so far) are likewise the
  owner's: `data/knowledge/clinic_rules.csv` holds each rule's status (draft
  or approved), version, owner and approval date (`knowledge/clinic_rules.py`);
  the code applies a rule by its id and shows its status from that file, a
  draft as a draft. Neither code nor Claude approves a rule or edits the file.
- **Held-out golden cases stay held out.** The cases in
  `data/quality/golden_cases_held_out/` are frozen (content hashes in
  `data/quality/golden_cases_held_out.json`, checked by
  `quality/tests/test_golden_cases.py`). Never edit them, never tune the search,
  topics, prompt or settings on their results, and run them (`--held-out`)
  only when the owner asks, recording each run in `docs/FUTURE_WORK.md`. Tuning
  and its measurements use `data/quality/golden_cases/` only.
- **The yardstick asks first.** Claude Code asks the owner before Claude
  edits the golden cases, the held-out manifest, the two guides, the rule
  table, the clinic rules or the review logs (`.claude/hooks/protect_yardstick.py`, in
  `.claude/settings.json`); such a prompt is intended, not an error.
- **Ask the owner first** before committing, pushing (the owner decides
  when to push), adding a dependency, deleting data, or starting the next
  roadmap item.
- **Everything lives in its part's folder** (owner's decision, 2026-10-24;
  README.md, "Folder layout"): one package per part of the system (`shared/`,
  `knowledge/`, `reasoning/`, `review/`, `quality/`, and one per clinical
  domain: `prosthetics/`, `orthotics/`), each with its own `templates/<part>/`
  and `tests/`; the data likewise under `data/knowledge/`, `data/quality/`,
  `data/records/`. A domain has the same files as the others (`case.py`,
  `fields.py`, `topics.py`, `rag.py`, `intake.py`, `nav.py`, ...), and shared
  code reaches it through `shared/domains.py`, never by naming it
  (`shared/tests/test_domains.py` checks both). What every domain's screens
  share is built once (SYSTEM_DESIGN.md §5): the page pieces in
  `shared/templates/ui_macros.html` and the forms in `ui_forms.html`, the
  header in `ui_header.html` (each domain's words in its `nav.py`), the
  building blocks in `shared/requirements.py`, `shared/followup.py`,
  `shared/hard_stops.py` and `shared/fitting.py`, and the module pages'
  form reading and saving in `shared/forms.py` and `shared/module_pages.py`.
  Both domains have module pages after the intake (`<domain>/plan.py`,
  `hard_stops.py`, `modules.py`; prosthetics since 2026-10-24).

## Roadmap (in this order, by track)

**RAG (owner's decision, 2026-10-11).** The review page is produced by
retrieval plus a cloud language model, with checked quotes. The 59 hand-written statements
no longer produce the page; they are the answer key the RAG is measured
against (`python -m quality.golden_cases --rag`).

**Trial readiness**
1. Stabilise the app for a specialist trial (candidates: the known
   limitations in `docs/SYSTEM_DESCRIPTION.md` §7 and `docs/FUTURE_WORK.md`).
2. Trial tooling, then a trial with a real prosthetist, measured through the
   reviewers' marks in the review log.

**Evidence**
3. Knowledge-item and evidence fields (their clinical values are filled in
   by the team; see the judgement rule above).
4. A golden-case benchmark.

**Product**
5. Smart search, use case 05 (can build on `knowledge/retrieval.py`).
6. Split `Case` into a shared core plus one section per domain. Core done
   2026-10-17: `CaseCore` in `shared/case_schema.py`, read back with
   `case_from_dict`; a dict without "domain" is a prosthetics case, so saved
   cases, log lines and the golden cases read unchanged. Since 2026-10-24
   each domain's section is in its own package (`prosthetics/case.py` `Case`,
   `orthotics/case.py` `OrthoticCase`).
7. Orthotics, use case 03, stroke AFO first. (Owner's decision, 2026-10-16:
   started before the trial, replacing "only after the trial results are
   in".) Its intake fields and which are critical, its topics, answer key
   and golden cases come from the owner; Claude may propose, not decide.
   Built 2026-10-22 from Claude's proposal as drafts, at the owner's
   request (`orthotics/`, branch `orthotics`): they stay marked as awaiting
   the owner's and an orthotist's review until the owner confirms them.
   2026-10-23: modules 1-6 from the owner's design (analysis, requirements,
   design options with materials and parts, digital design workflow, fit
   and tune, follow-up; `orthotics/plan.py`, `fit.py`, `followup.py`,
   `modules.py`); every value on them is the orthotist's, never the tool's.
   The design's four hard stops are draft rules awaiting the owner
   (`orthotics/hard_stops.py`; owner, 2026-10-24).

## Commands

```
python -m unittest            # all tests (every <part>/tests/), about 1.5 min, no model needed
python app.py                 # app at http://127.0.0.1:5000
python -m knowledge.ingest    # rebuild data/knowledge/extracted/ and the search index
python -m knowledge.evaluate  # search quality (hit@1 / hit@5)
                              # --orthotics: the orthotic topic searches (data/knowledge/eval/orthotic_topics.json)
python -m knowledge.items     # knowledge items, owner's rules applied -> data/knowledge/
                              # (python -m knowledge.evidence_rules does the same)
python -m quality.golden_cases # development golden cases vs the app (--no-search: no model needed)
                              # --rag: live RAG coverage of the hand-written statements
                              # (calls the cloud model: free-tier quota or money, ask first)
                              # --held-out: the frozen held-out cases instead (only when the owner asks)
python -m quality.retrieval_misses  # why expected statements miss the writer: development cases,
                              # real search, no AI (--json FILE keeps every record)
python scripts/verify_all.py  # the 0-2 checks and the golden cases (--with-model: real search)
```

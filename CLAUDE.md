# CLAUDE.md — AI Prosthetic Lab

A working local prototype of a decision-support tool for prosthetics
specialists (Flask, rule-based, local bge-m3 search, English/Arabic pages).
Extend it; don't rebuild it. Before changing anything, read
`SYSTEM_DESCRIPTION.md` (what it does and how it is built), `README.md`
(how to run it) and `FUTURE_WORK.md` (decisions, measurements, open items).

## Principles that never change

1. **It supports the specialist's decision; it never makes it.** No output
   may diagnose, prescribe, choose a component, rank components, or say
   whether a patient is ready for fitting. Pages show information next to
   what the sources say, and the specialist decides.
2. **Only the sources speak.** Every reason, statement and grade shown to
   the user is copied word for word from a catalogued document, with its
   page. No clinical sentence is written by the code or by Claude. Whether a
   statement applies to a case follows only from the source's own wording.
3. **No language model and no cloud service** at runtime. Search uses the
   local embedding model; reasoning is rules.
4. **Fake test data only.** Never collect or store patient identifiers
   (name, date of birth, address, record numbers).
5. **Two interface languages: English and Arabic (right to left).** Quotes
   and citations stay in the language of their source and are never
   translated.

## Working rules for every change

- **All tests keep passing** (`python -m unittest`). A change that breaks a
  test is not finished.
- **Every new quote gets a word-for-word test** against its page in
  `data/extracted/<doc_id>.txt`. Statements added to
  `reasoning/component_guide.py` or `reasoning/fitting_guide.py` are covered
  by `tests/test_component_guide.py` (quote on its page, list items in
  order, VA/DoD grade as printed); quotes kept anywhere else need an
  equivalent test. These tests skip when `data/extracted/` is missing:
  generate it (`python -m knowledge.ingest`) so a skip is never mistaken
  for a pass.
- **Every new interface text gets its Arabic entry** in `shared/i18n.py`.
  `tests/test_i18n.py` enforces it; a key built at runtime (e.g.
  `'section.' ~ key`) must also be added to its expected-keys test.
- **The review log is append-only.** Lines in `data/review_log.jsonl` are
  never edited or removed. Any change to the shape of a log entry raises
  `LOG_VERSION` in `review/decision_log.py`, and everything that reads the
  log must still read lines from earlier versions.
- **Clinical judgements are the team's, not the code's or Claude's.**
  Evidence level, the population a statement applies to, and confidence are
  never inferred, normalised or filled in by code or by Claude. Copying a
  grade exactly as the source prints it is allowed (and tested); anything
  else is left empty for the team to fill in.
- **Ask the owner first** before committing, pushing (the owner decides
  when to push), adding a dependency, deleting data, or starting the next
  roadmap item.

## Roadmap (in this order, by track)

**Trial readiness**
1. Stabilise the app for a specialist trial (candidates: the known
   limitations in `SYSTEM_DESCRIPTION.md` §7 and `FUTURE_WORK.md`).
2. Trial tooling, then a trial with a real prosthetist, measured through the
   reviewers' marks in the review log.

**Evidence**
3. Knowledge-item and evidence fields (their clinical values are filled in
   by the team; see the judgement rule above).
4. A golden-case benchmark.

**Product**
5. Smart search, use case 05 (can build on `knowledge/retrieval.py`).
6. Split `Case` into a shared core plus one section per domain.
7. Orthotics, use case 03 — only after the trial results are in.

## Commands

```
python -m unittest            # all tests, ~1 s, no model needed
python app.py                 # app at http://127.0.0.1:5000
python -m knowledge.ingest    # rebuild data/extracted/ and the search index
python -m knowledge.evaluate  # search quality (hit@1 / hit@5)
```

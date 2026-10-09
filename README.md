# AI Prosthetic Lab — v1 prototype

First prototype of **AI Prosthetic Lab**, a specialised AI system for
prosthetics, orthotics and rehabilitation (see the visual brief, 09/2026).

This prototype covers the start of the brief's prosthetics domain:

> **Use case 01 — analyse an amputation case and identify the information
> still needed before specialist evaluation.**
>
> **Use case 02 — support component selection based on the functional
> data:** the functional level (K-level) and what the guidelines in the
> source library say about each prosthetic component for the case.
>
> **Design and fitting:** what the sources say about readiness for
> fitting, a preparatory or definitive prosthesis, the fitting steps and
> alignment, next to what the case recorded.

It is **decision support, not a replacement** for the specialist. It lists
missing information and quotes guideline and manual statements word for
word with their own grade of evidence, if they give one; it does not
diagnose, prescribe, choose or rank components, or judge whether a patient
is ready for fitting. The final decision always stays with the specialist.

Fake/test data only. No patient identifiers (name, date of birth, address,
record numbers) are collected.

## How it follows the brief's reasoning pathway

| Brief pathway step          | Module                              | Status in v1                       |
|-----------------------------|-------------------------------------|------------------------------------|
| 01 Case data                | `intake/`, `shared/case_schema.py`  | Working: form (incl. prior prostheses), schema, validation |
| 02 Information analysis     | `knowledge/`                        | Working: extraction, chunking, multilingual search (en/ar; German ingested, not searched) |
| 03 Specialised reasoning    | `reasoning/gap_analysis.py`, `reasoning/component_support.py`, `reasoning/fitting_support.py` | Working: rule-based; every gap cites a checkable passage or says none was found; component and fitting statements come from `reasoning/component_guide.py` and `reasoning/fitting_guide.py` |
| 04 Assistive output         | `reasoning/models.py`               | Working: gap list, functional level, statements per component, and design and fitting statements, all quoted with their source |
| 05 Specialist review        | `review/`                           | Working: approve / edit / reject, needed / not needed per gap, relevant / not relevant per component or fitting statement |
| 06 Documentation            | `review/decision_log.py`            | Working: each decision appended to `data/review_log.jsonl` |

The prosthetics domain's three parts (evaluate, choose components, design
and fit) now each have a first version; the rest of the brief (orthotics,
gait analysis, rehabilitation, follow-up) is planned but not started — see
[FUTURE_WORK.md](FUTURE_WORK.md#path-to-the-full-system).

## Running it

Requires Python 3.12+ (developed on 3.14).

```
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000. The first case you submit takes about
10 seconds while the search model loads; later cases take well under a
second. Build the search index first (below), or the review page will
warn that no sources were searched.

Each case is saved as `data/cases/<case id>.json` (not in git), so its
review page still works after the server is restarted. The files hold the
case as entered (no patient identifiers), the passages found and the gap
list.

## Languages

The pages are in English (default) or Arabic, right to left. The link at
the top of each page switches language; the browser remembers the choice
(a cookie). On the intake form it keeps what has been typed so far. Headings, labels, choices, buttons, messages, the disclaimer
and each gap's explanation are translated. Quotes and citations stay in
the source's own language, and what the user types is shown as typed.

All translations are in `shared/i18n.py`, so one file can be checked by an
Arabic-reading specialist. The tests fail if a text, a gap field or a
drop-down choice has no Arabic version.

## Knowledge sources

The source PDFs are not in git. `data/sources/catalog.json` lists each one
with its DOI or web address; download them into the folders it names (see
`data/sources/README.md`). Then build the search index:

```
python -m knowledge.ingest
```

This extracts each document's text to `data/extracted/<id>.txt` (open those
files to see exactly what the system reads), cuts it into chunks of about
800 characters, and turns each chunk into a vector with the multilingual
model `BAAI/bge-m3` (about 2.3 GB, downloaded on the first run into the
Hugging Face cache, outside this folder). The result goes to
`data/vector_store/`. Re-run it whenever a document, the catalog or the
model changes. Without it the app still lists gaps, but warns that no
sources were searched.

A catalogued document can be left out of the gap search but still be
quoted by the hand-written statements: `RETRIEVAL_EXCLUDED_DOCUMENTS` in
`shared/config.py` (now the ICRC gait-analysis manual; the reason is in the
comment there).

To check how well the search finds the right page, in English, Arabic and
German, with and without the German documents:

```
python -m knowledge.evaluate
```

## How a gap list is made

1. `shared/field_guide.py` lists the intake fields that can be gaps, with
   a search query and topic words (English, German, Arabic) for each.
2. For every field that is empty or recorded as unknown, retrieval
   searches the prosthetics documents for the case's limb (upper or lower).
3. The gap cites the best passage that is similar enough
   (`MIN_RELEVANCE_SCORE`) **and** mentions the field's topic, and quotes
   its sentences on that topic. If none passes, the gap says no source was
   found instead of citing a weak one.
4. The review page shows each gap with its quote, citation (title, year,
   page) and the other passages considered.

## How component statements are chosen

Not by search: `reasoning/component_guide.py` holds hand-written rules, each
with one statement copied word for word from a source (VA/DoD 2024 and
2022, CMS 2017, the ICRC gait-analysis manual 2014), its page and the
source's own grade ("Weak for", "Neither for nor against", or none given).
Each statement also shows its kind of source, so a training manual is not
mistaken for a guideline. A rule applies to a case only as far as the
source's own wording says: amputation level ("TT"/"TF" in the ICRC
manual), unilateral or bilateral, a specific K-level, or "ambulators" (not
shown for K0). Where sources differ, both are shown.

The review page shows, for the case:
1. **Functional level and goals:** the CMS description of the recorded
   K-level, what the same source says K-levels are not, and the patient's
   recorded activity and goals.
2. **Per component** (knee, foot and ankle, socket, interface, suspension;
   upper limb: type of prosthesis, control and fit): the statements that
   apply, or "no statement in the source library". Nothing is ranked.

## How design and fitting statements are chosen

The same way, from `reasoning/fitting_guide.py` (sources: the ICRC manual,
VA/DoD lower limb recommendation 5 and algorithm, VA/DoD upper limb phases
of care and tables 5-6, CMS 2017, and the WHO prosthetics and orthotics
implementation manual). The review page shows four sections:
1. **Readiness for fitting**, with what the case recorded at intake
   (wound, volume, skin, pain, sensation, comorbidities, cognition, time
   since amputation) shown as entered, next to the sources' criteria. The
   tool never says whether the patient is ready.
2. **Preparatory or definitive prosthesis.**
3. **Fitting, check-out and follow-up.**
4. **Alignment**: what it is, its steps, and, for transtibial and
   transfemoral prostheses, what the ICRC manual says an alignment error
   may cause in gait.

Socket, interface and suspension statements are listed with the components.

`tests/test_component_guide.py` checks, for both guides, that every quote
is on its page of the extracted text, that a quoted list's items follow
their heading in order, and that each VA/DoD grade is the one printed
after the recommendation. To add a statement, copy it from
`data/extracted/`, add a rule, and run the tests.

## Review log

The specialist marks each gap "Needed" or "Not needed for this case", and
each component or fitting statement "Relevant" or "Not relevant for this
case" (or leaves them unmarked), and approves, edits (with a note saying
what should change) or rejects the list. Each decision is added as one line
of JSON to `data/review_log.jsonl`, and the review page lists the decisions
logged for the case. A line holds the decision, note, time (UTC), the case
as entered, every gap with its quote, citation and full passage, the
functional level, every component and fitting statement shown with its
mark, the intake values shown next to the readiness statements, and the
search settings, so it can be checked later even after the source library
is re-ingested. Labels and explanations are logged in English whichever
language the reviewer used; `ui_language` records which one it was. Lines are never changed or removed. The file stays on this
machine (it is in `.gitignore`). The 26 lines written while building and
checking the prototype were moved, unchanged, to
`data/review_log.test.jsonl` (2026-10-09), so `data/review_log.jsonl` holds
only the trial's decisions.

## Trial tools

For the Arabic term check and the specialist trial (details in
[data/trial/README.md](data/trial/README.md)):

```
python -m shared.arabic_terms export     # every interface text -> data/trial/arabic_terms.csv
python -m shared.arabic_terms apply data/trial/arabic_terms.csv   # a prosthetist's corrections -> shared/i18n.py
python -m intake.load_trial_cases        # the 15 prepared fake cases in data/trial/cases/ -> the app
python -m review.trial_report            # counts from the review log -> data/trial/report.csv
```

## Tests

```
python -m unittest
```

## Layout

```
app.py              Flask entry point; registers the intake and review pages
shared/             Case schema, config (paths, settings, disclaimer), case store
                    (memory + data/cases/), interface text in English and Arabic (i18n.py)
intake/             Intake form -> Case -> runs knowledge + reasoning -> review page
knowledge/          Source catalog, text extraction, ingestion, search, evaluation
reasoning/          Gap analysis (what is missing, and which source says why),
                    component support (what the sources say per component) and
                    fitting support (readiness, preparatory/definitive, fitting, alignment)
review/             Specialist review page and decision log (writes data/review_log.jsonl)
tests/              unittest suite (uses a tiny fake embedder, not the real model)
data/sources/       Knowledge documents: catalog.json in git, the PDFs kept local
data/extracted/     Cleaned text per document (generated, not in git)
data/vector_store/  Chunks and their vectors (generated, not in git)
data/eval/          Retrieval evaluation queries (in git)
data/cases/         One JSON file per case entered (not in git)
data/trial/         Arabic term sheet, prepared trial cases (in git); trial report (not in git)
```

## Plan and open decisions

[FUTURE_WORK.md](FUTURE_WORK.md) tracks the build steps, open decisions and
known simplifications.

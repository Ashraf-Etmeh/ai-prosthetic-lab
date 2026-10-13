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
missing information and shows what the guidelines and manuals in its
source library say about the case: since 2026-10-11 it is a **RAG**
(retrieval-augmented generation). A local search finds the passages, and
the Claude API writes one short sentence about each, labelled as AI, with
the source's own words quoted below it. Code checks every quote word for
word against its passage and removes any sentence whose quote isn't there.
It does not diagnose, prescribe, choose or rank components, or judge
whether a patient is ready for fitting. The final decision always stays
with the specialist.

Fake/test data only. No patient identifiers (name, date of birth, address,
record numbers) are collected.

## How it follows the brief's reasoning pathway

| Brief pathway step          | Module                              | Status in v1                       |
|-----------------------------|-------------------------------------|------------------------------------|
| 01 Case data                | `intake/`, `shared/case_schema.py`  | Working: form (incl. prior prostheses), schema, validation |
| 02 Information analysis     | `knowledge/`                        | Working: extraction, chunking, multilingual search (en/ar; German ingested, not searched), one search per missing field and per RAG topic |
| 03 Specialised reasoning    | `reasoning/rag.py`, `reasoning/writer.py`, `reasoning/quote_check.py` | Working (RAG, since 2026-10-11): the Claude API summarises the passages found; every quote checked word for word; without the API, the gaps fall back to `reasoning/gap_analysis.py` and the passages are listed. The hand-written statements are the answer key |
| 04 Assistive output         | `reasoning/models.py`               | Working: gap list, functional level, statements per component, and design and fitting statements: an AI sentence each, labelled, over the source's quote |
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
10 seconds while the search model loads. Build the search index first
(below), or the review page will warn that no sources were searched.

**The AI summaries need a Claude API key** (an Anthropic account with
billing). Set it before starting the app:

```
$env:ANTHROPIC_API_KEY = "sk-ant-..."      # PowerShell; never put it in a project file
python app.py
```

Each case then makes three calls to the Claude API (`claude-opus-5-5`,
`shared/config.py`), at the same time: one for the gaps, one for the
functional level and components, one for design and fitting. **The case
as entered is sent to the API**, so enter fake test data only. Cost and
time per case are measured in `python -m intake.golden_cases --rag`
(FUTURE_WORK.md).

Without a key, or offline, the app still works: the page says why there are
no summaries, the gaps cite passages through the topic-word check, and
each section lists the passages the search found. To switch the AI off
on purpose, set `AI_PROSTHETIC_LAB_OFFLINE=1` (the tests always do).

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

## How the review page is made (the RAG)

1. **Search (local).** `knowledge/retrieval.py` searches the prosthetics
   documents for the case's limb, once per topic:
   - every intake field that is empty or recorded as unknown, with the
     field's query from `shared/field_guide.py`;
   - the functional level (lower limb), each component (knee, foot and
     ankle, pylon, socket, interface, suspension; upper limb: type of
     prosthesis, control and fit), and each fitting section (readiness,
     preparatory or definitive, fitting, alignment), with the queries in
     `reasoning/rag_topics.py`, which name the case's level, side and
     K-level.
2. **Summarise (Claude API).** `reasoning/rag.py` sends three requests at
   once (gaps; functional level and components; fitting). Each holds the
   instructions (`SYSTEM_PROMPT`, versioned by `PROMPT_VERSION`), the case
   as entered, the topics and the passages found, each with its id. The
   instructions say: use only these passages; back every sentence with a
   quote copied character for character; say whom the source says it
   applies to, in its own words; give both sides where sources differ;
   copy a grade only if the passage prints it; never advise, choose, rank
   or say whether the patient is ready. The answer must be JSON in a fixed
   shape (structured output). `reasoning/writer.py` is the one place that
   talks to the API, so a local model could replace it later.
3. **Check (code).** `reasoning/quote_check.py` keeps an item only if its
   quote is in the named passage word for word (line breaks and the print
   form of quotation marks and dashes aside), at least five words long,
   with an Arabic sentence. A grade not printed right after the quote is
   dropped. The page shows the passage's own words and the page the quote
   is on (looked up in `data/extracted/`). Everything removed is kept with
   its reason, so the misquote rate can be measured.
4. **Show.** Each gap and statement shows "AI summary — check it against
   the quote below", the AI's sentence in the page's language, then the
   quote in the source's language, its citation, grade and kind of source,
   the passage id and the full passage. The specialist marks it as before.
   Nothing is ranked.

Socket, interface and suspension are listed with the components. The
readiness section also shows what the case recorded at intake (wound,
volume, skin, pain, sensation, comorbidities, cognition, time since
amputation) as entered; the tool never says whether the patient is ready.

## The hand-written statements: the answer key

`reasoning/component_guide.py` and `reasoning/fitting_guide.py` hold 59
statements copied word for word from VA/DoD 2024 and 2022, CMS 2017, the
ICRC gait-analysis manual 2014 and the WHO implementation manual, each with
its page, the source's own grade and a rule for which cases it applies to
(level, side, K-level, "ambulators"). Until 2026-10-11 they produced the
page; now they are the answer key the RAG is measured against
(`python -m intake.golden_cases --rag`), and the knowledge items are built
from them. `tests/test_component_guide.py` still checks that every quote is
on its page of the extracted text, that a quoted list's items follow their
heading in order, and that each VA/DoD grade is the one printed after the
recommendation.

## Knowledge items

Every statement of both guides is also a *knowledge item*
(`KnowledgeItem` in `knowledge/models.py`), in the structure of the
research brief: the statement and its source, plus evidence fields
(evidence layer, evidence tag, confidence, population, limitations) and a
review state. Only the owner sets the evidence fields: evidence layer, tag
and confidence through the owner's rule table
(`data/knowledge/evidence_rules.csv`) or by hand, population and
limitations by hand. A rule applies to an item when its condition in
`knowledge/evidence_rules.py` matches (the item's document, the grade as
printed); the item then gets the rule's values, status "rule-assigned" and
the rule id. Two rules matching one item, or an invalid value in the table,
stop the run before anything is written. Export them all (re-run after
changing a guide or the rule table):

```
python -m knowledge.items     # -> data/knowledge/items.json (UTF-8, Arabic readable)
                              #    and items_to_curate.csv: the items no rule classified
```

`python -m knowledge.evidence_rules` does the same. Neither ever replaces a
file holding the team's own values (population, limitations, values set by
hand, a review, a filled-in cell of the sheet).

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
is re-ingested. Since log version 5 (the RAG) it also holds each AI
sentence (English and Arabic), the passage behind each quote, and what the
AI was asked and gave: prompt version, model, tokens, time and what the
quote check removed. Labels and explanations are logged in English whichever
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
python -m intake.golden_cases     # fake cases with the output they must give (data/eval/golden_cases/)
python -m intake.golden_cases --rag   # also measure the RAG (calls the Claude API: costs money)
```

The golden cases run through the same analysis as the intake form (one is
submitted through the Arabic form and must match its English twin). Their
statement and functional-level checks test the answer key (the hand-written
rules); without `--rag` the AI is switched off. With `--rag` they measure
how many expected statements a checked RAG quote covers, any statement the
case must not show that one covers, the gap sources, what the quote check
removed, and tokens, time and estimated cost. The tests never call the API
(`tests/__init__.py` switches it off; `tests/helpers.py` has a fake writer). Without
the search model or the vector store (or with `--no-search`) their gap
checks are skipped and the rest still run; the model is never downloaded.
A difference fails a case marked "reviewed" and warns for an "unreviewed" one.
The reviewed cases also run in `python -m unittest` (without their gap checks).

```
python scripts/verify_all.py      # the checks for prompts 0-2, then the golden cases
```

## Layout

```
app.py              Flask entry point; registers the intake and review pages
shared/             Case schema, config (paths, settings, disclaimer), case store
                    (memory + data/cases/), interface text in English and Arabic (i18n.py)
intake/             Intake form -> Case -> runs knowledge + reasoning -> review page
knowledge/          Source catalog, text extraction, ingestion, search, evaluation,
                    knowledge items (the curated statements with their evidence fields)
reasoning/          The RAG: topics, the AI writer (Claude API), the quote check, and the page's
                    shapes; gap analysis without the AI; the hand-written statements and
                    their rules (the answer key)
review/             Specialist review page and decision log (writes data/review_log.jsonl)
tests/              unittest suite (a tiny fake embedder and a fake AI writer: no model, no API)
data/sources/       Knowledge documents: catalog.json in git, the PDFs kept local
data/knowledge/     The owner's evidence rules, the knowledge items and the items to curate (in git)
data/extracted/     Cleaned text per document (generated, not in git)
data/vector_store/  Chunks and their vectors (generated, not in git)
data/eval/          Retrieval evaluation queries and golden cases (in git)
data/cases/         One JSON file per case entered (not in git)
data/trial/         Arabic term sheet, prepared trial cases (in git); trial report (not in git)
```

## Plan and open decisions

[FUTURE_WORK.md](FUTURE_WORK.md) tracks the build steps, open decisions and
known simplifications.

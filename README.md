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
a cloud language model (Gemini's free tier, or the Claude API) writes one
short sentence about each, labelled as AI, with
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
| 01 Case data                | `prosthetics/intake.py`, `prosthetics/case.py`, `shared/case_schema.py` | Working: form (incl. prior prostheses), schema, validation |
| 02 Information analysis     | `knowledge/`                        | Working: extraction, chunking, multilingual search (en/ar; German ingested, not searched), one search per missing field and per RAG topic |
| 03 Specialised reasoning    | `reasoning/rag.py`, `reasoning/writer.py`, `reasoning/quote_check.py` | Working (RAG, since 2026-10-11): a cloud language model (Gemini free tier or Claude API) summarises the passages found; every quote checked word for word; without the API, the gaps fall back to `reasoning/gap_analysis.py` and the passages are listed. The hand-written statements are the answer key |
| 04 Assistive output         | `reasoning/models.py`               | Working: gap list, functional level, statements per component, and design and fitting statements: an AI sentence each, labelled, over the source's quote |
| 05 Specialist review        | `review/`                           | Working: approve as reviewed / approve with edits / reject, needed / not needed per gap with a reason, relevant / not relevant / summary is wrong per component or fitting statement; "Sign and record" |
| 06 Documentation            | `review/decision_log.py`            | Working: each decision appended to `data/records/review_log.jsonl` |

The prosthetics domain has the design's four module pages (since
2026-10-24, below), with the review page as its specialist review.
Orthotics (use case 03, stroke
ankle-foot orthosis) has a first version as drafts awaiting the owner's and
an orthotist's review (below, "Orthotics"). The rest of the brief (gait
analysis, rehabilitation, follow-up) is planned but not started — see
[docs/FUTURE_WORK.md](docs/FUTURE_WORK.md#path-to-the-full-system); the target
system is described in [docs/design/SYSTEM_DESIGN.md](docs/design/SYSTEM_DESIGN.md).

## Running it

Requires Python 3.12+ (developed on 3.14).

```
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000: the system map, every part of the system
with its pages and what waits for the owner. The first case you submit takes about
10 seconds while the search model loads. Build the search index first
(below), or the review page will warn that no sources were searched.

**The AI summaries need a Gemini API key** (free, since 2026-10-13). Sign
in at [Google AI Studio](https://aistudio.google.com/), choose *Get API
key*, create one, and set it before starting the app:

```
$env:GEMINI_API_KEY = "..."      # PowerShell; never put it in a project file
python app.py
```

Each case then makes three calls to the Gemini API (`gemini-3.8-flash`,
`GEMINI_MODEL` in `shared/config.py`), at the same time: one for the gaps,
one for the functional level and components, one for design and fitting.
**Each case's amputation level, side and recorded K-level are sent to
Google, with the passages found** (never what was typed at intake:
`case_for_prompt` in `reasoning/rag.py`). On the free tier Google uses
prompts and answers to improve its products and human reviewers may read
them, so enter fake test data only (Google's terms allow only a paid key
for an app offered to users in the EEA, Switzerland or the UK). The free tier limits
requests per minute and per day; your project's limits are shown in AI
Studio. When they are used up, the page says so and shows the passages
without summaries until the quota resets. If they are too tight,
`GEMINI_MODEL = "gemini-3.5-flash-lite"` usually allows more requests.

To use the Claude API instead (paid): set `LLM_PROVIDER = "claude"` in
`shared/config.py` and `$env:ANTHROPIC_API_KEY = "sk-ant-..."`. Time,
tokens and (for Claude) cost per case are measured in
`python -m quality.golden_cases --rag` (docs/FUTURE_WORK.md).

Without a key, or offline, the app still works: the page says why there are
no summaries, the gaps cite passages through the topic-word check, and
each section lists the passages the search found. To switch the AI off
on purpose, set `AI_PROSTHETIC_LAB_OFFLINE=1` (the tests always do).

Each case is saved as `data/records/cases/<case id>.json` (not in git), so its
review page still works after the server is restarted. The files hold the
case as entered (no patient identifiers), the passages found and the gap
list.

### Prosthetic module pages (2026-10-24)

A prosthetic case has the four modules of the design (`docs/design/02-prosthetics/`;
`prosthetics/modules.py`), reached from the header's tabs, the review page and
the map at http://127.0.0.1:5000/prosthetics. After the intake form a new case
still opens on the review page (what the sources say, and the specialist's marks).

- **1 Assess**: the residual limb and body as recorded, each value with how it
  was measured; mobility, measured with named tests; the K-level the
  prosthetist set, with what the sources say about functional levels; goals by
  ICF level; the information still needed; three draft hard-stop checks (open
  wound or infection, changing volume, neuropathic other foot), shown as
  drafts awaiting the owner (`data/knowledge/clinic_rules.csv`). A form records
  what the intake form doesn't ask.
- **2–3 Requirements & components**: what the prosthesis must do, in the
  prosthetist's words, each tied to where it came from, with a priority and any
  conflicts; then for each component of the amputation level up to three
  options typed by the prosthetist, side by side and never ranked: marks
  against the requirements, costs, the sources linked (grade as printed), the
  payer's funding rule and the maker's weight limit as printed (next to the
  recorded weight), stock and checks at fitting. The prosthetist's
  configuration and reason go to the review log as a "design_choice".
- **4 Design & fitting**: the six steps, an observation log (seen, gait phase,
  adjustment, seen after) next to the possible causes in the sources' words,
  check-socket versions, what bears on a definitive prosthesis (the clinic's
  checklist waits for the owner), the alignment record with every version
  kept, and the fabrication sheet to print.
- **5 Follow-up**: visits, outcome measures as recorded at each, alerts in the
  clinician's words looping back to module 4, 2–3 or 1.

Every value on these pages is the prosthetist's; nothing typed there is sent to
the cloud model.

### Orthotics (drafts, 2026-10-22)

The intake form links to an orthotic case (stroke, ankle-foot orthosis) at
http://127.0.0.1:5000/intake/orthotics: the condition and affected side,
walking (gait speed with the test named, falls, deviations ticked by gait
phase), the exam (dorsiflexion with the knee extended and flexed, tone with
its scale, strength, knee in stance, foot posture, sensation, skin),
footwear, donning, earlier orthoses or FES, and what the orthosis must do
in the orthotist's own words. The review page lists the missing
information (six fields marked critical), what the sources say about an
ankle-foot orthosis or FES (side by side, never ranked) and about design
and fitting, and records the orthotist's decision in the same log.
For now no orthotic case is sent to the cloud model, whatever key is set
(owner's decision 2026-10-23, `ORTHOTIC_CLOUD_AI` in `shared/config.py`): the
orthotic pages show the passages found without summaries. When it is
switched on, the condition, side and months since onset are sent, with the
passages. The fields, critical flags, topics and prompt are Claude's
proposal, awaiting the owner and an orthotist; no live orthotic AI run has
been made yet. Only documents with the "orthotics" domain are searched, at
most three passages from one document per search. To measure that search:

```
python -m knowledge.evaluate --orthotics
```

The form leads to six module pages (2026-10-23, from the design's orthotics
screens in `docs/design/03-orthotics/`; drafts like the rest):

- **1 Analysis**: the case as recorded, each exam value with how it was
  measured, gait phase by phase, the information still needed, and the
  hard-stop checks. The review page (what the sources say, and the
  reviewer's marks) is one link away.
- **2 Requirements**: what the orthosis must do, in the orthotist's words,
  each tied to the findings it comes from, with a priority and any conflicts.
- **3 Options**: up to three design options side by side, never ranked, and
  the FES referral. Each has a device type, what it costs the patient, its
  materials and parts (each tied to a requirement and so to a finding),
  stock and checks at fitting. The orthotist marks what each option
  addresses, then chooses and gives a reason, which goes to the review log
  as a "design_choice".
- **4 Digital design**: the steps from capture to release, simulation
  results as entered, the design parameters with their basis and approval,
  every save kept as a version; the fabrication sheet to print.
- **5 Fit, tune and train**: check-out, tuning, before and after, the
  training plan, and the patient leaflet the orthotist writes in Arabic and
  English.
- **6 Follow-up**: visits, outcome measures over time, alerts that loop back
  to modules 5, 3 or 1, and a summary for the physiotherapist.

The four hard stops on the design's map are checked against what was
recorded; each is shown with its status from the owner's file
`data/knowledge/clinic_rules.csv`. All four are **draft rules awaiting the
owner's approval** there; once the owner approves one (status, version, owner,
date in that file), its pages show it as the clinic's rule. Each device type, part
and step shows the passages the local search finds about it, quoted as
printed and not summarised. Nothing on these pages is sent to the AI, and
the tool suggests no value. The module map is at
http://127.0.0.1:5000/orthotics.

## The pages

Every page has the same header (since 2026-10-23): Prosthetics / Orthotics /
Gait analysis / Rehabilitation / Knowledge layer / Reasoning and review /
Search and education / Patient record, the part's modules, and on a case's
pages a bar with the case. The prosthetics map, http://127.0.0.1:5000/prosthetics, lists the
four prosthetic modules; the orthotics map is at /orthotics.

**Knowledge layer** (2026-10-25, `docs/design/06-knowledge-layer/`) has three
pages, all read-only:
- **1 Sources** (`/knowledge`): every catalogued document with its kind,
  language, licence as recorded ("not shown" when none), what extraction did
  to its text (pages, references and headers removed, split words rejoined,
  pages with almost no text) and its status (searched, or not in the index);
  the registry's documents that are link only or not catalogued; the steps
  from document to search; what needs a curator (e.g. a manual download, or
  a search-quality test due after a new library build:
  `python -m knowledge.evaluate --record`).
- **2 Evidence** (`/knowledge/evidence`): each knowledge item's quote and
  page, its grade as printed, its evidence fields and the owner's rule that
  set them (or unassigned), why it may need a curator, and the owner's rule
  table. Nothing on it writes a value: the fields come only from the owner.
- **3 Graph and expertise** (`/knowledge/graph`): the clinic rules with
  their status, version, owner and approval date; the Arabic term sheet's
  state; and what is not built yet (the design knowledge graph, a glossary
  with a status per term, the case library, structured data).

**Search and education** (2026-10-25, `docs/design/08-search-and-education/`):
**1 Smart search** (`/search`). Ask in English or Arabic; the local search
looks through the whole library in both languages, narrowed by domain, kind
of source, language and year, and lists the passages found in order of match
(Arabic passages quoted in Arabic). "What the sources say" (AI sentences, each
over a quote checked word for word) appears only once the owner sets
`SEARCH_CLOUD_AI` in `shared/config.py`: a question is typed text, so until
then it never leaves the machine. When nothing answers, the page says so and
offers "Suggest a source to the curator" (listed on the knowledge sources
page). Each search, mark (useful / not useful / a summary is wrong) and
suggestion goes to `data/records/search_log.jsonl` on this machine, never
who asked; the quality page counts them. Pinning a passage to a case comes
later.

**2 Case-based learning** (`/learn`, use case 06). Work an invented teaching
case (`data/education/teaching_cases/`) in five steps: read what the case
records, tick what is missing, write the options you would weigh and why,
compare, then reflect and add it to the learning log. The compare step shows,
item by item, what you marked, how many of the expert panel marked it, and the
source the local search found; and, for a gap you did not mark, what the
sources say (the case's own analysis, run once and kept, as for any
prosthetic case: only its level, side and K-level go to the AI). Nothing is
graded. A teaching case's level, CPD time, status and the panel's answers are
the educator's: the three cases there now are Claude's drafts with none of
them set, so the page says the panel has not answered yet. The learning log
(`data/records/learning/log.jsonl`, one for this machine until roles and
login come) gives the cases worked, the CPD minutes recorded and a CSV
export.

**Patient record** (2026-10-27, `docs/design/09-patient-record/`, use case
07): one record per person across domains, under a code the app makes
(P-XXXXXX); the name, birth date and file number stay in the clinic's own
system. Open a record at `/record`, record the person's consent first, then
attach a case at its intake by typing the code in the form's "Person code"
field (empty: a case on its own, as before).
- **1 Record and follow-up** (`/record/<code>`): the cases, the latest
  design choice, the next review due, open alerts and the consent; the
  timeline across domains (each case's intake, signed reviews, design
  choices, socket, alignment or design versions, follow-up visits), the
  outcome measures as entered, the follow-up schedule, and hand-over notes
  that stay on this machine.
- **2 Consent and governance** (`/record/<code>/governance`): four consent
  items, each separate, shown in Arabic or English as the person chooses,
  each change a new line. A case of a person who has not agreed to the cloud
  model gets no AI summaries; one who has not agreed to quality use is left
  out of the quality counts. Also: where each piece of data goes (read from
  the code's own switches), who may see what (`data/governance/roles.csv`,
  a draft awaiting the owner, not enforced until sign-in), the retention
  period and its law (not set), the access trail (every look, who: not
  recorded until sign-in), a copy for the person, and deletion requests.

A deletion is done by the owner by hand: delete the person's case files
(`data/records/cases/<case id>.json`, the ids are in the person's file),
then cut the person's file (`data/records/people/<code>.jsonl`) down to its
`created` line and its deletion `request` line, and add one line
`{"record_version": 1, "kind": "deleted", "at": "<UTC time>"}`. The page then
says the content was deleted. The review log's lines for those cases stay
(it is append-only): see docs/FUTURE_WORK.md, "Patient record".

**Rehabilitation** (2026-10-27, `docs/design/05-rehabilitation/`): works on a
prosthetic or orthotic case (it has no intake of its own); open a case from
`/rehabilitation`, or from the "Rehabilitation" card on a case's follow-up
page. Its plan is kept with the case (case file version 5).
- **1 Plan** (`/rehabilitation/<case id>/plan`): goals agreed with the person
  by ICF level (scaled −2 to +2, with a review date), interventions with the
  goals they serve and the dose the therapist sets, each next to what the
  library says about its kind (local search on fixed wording, quoted as
  printed; an intervention of the therapist's own: "No source in the
  library"), phases and the team.
- **2 Progress**: measures by session as recorded (the shared follow-up
  form), goal attainment scored by the therapist with the person, alerts in
  the therapist's words. The smallest change that matters is the owner's,
  not set yet.
- **3 Training with the device**: tasks tied to the device's requirements
  (R1 ...) or the goals, with stage and status; the home programme in Arabic
  and English, flagged until an Arabic-reading therapist has checked it,
  printable; what was seen in training for the prosthetist or orthotist,
  shown on the case's follow-up page and answered there by the specialist.
- **4 Team record**: one timeline (the team's entries, the sessions, the
  device's versions) filtered by therapy, device or medical; the handover,
  written and signed by a person (no AI draft: the owner's open decision);
  next steps.

Nothing of a rehabilitation plan is sent to a language model. The lists of
interventions, roles and task statuses are Claude's draft, awaiting the
owner and a therapist.

**Gait analysis** (2026-10-27, `docs/design/04-gait-analysis/`): works on a
prosthetic or orthotic case, like rehabilitation (`/gait`). This app
measures nothing: the numbers come from the capture system (a phone app,
sensors, insoles or the gait lab), typed in or imported as a table
(columns measure, left, right, both; `/gait/<case id>/template.csv`). No
video reaches the app; a filmed session needs the person's consent to
filming.
- **1 Capture**: each session's source, conditions (walkway, pace, device
  state and the device version logged, footwear, aid) and quality checks
  (frame rate, trials with the whole body in frame, steps against the
  minimum, a hidden foot, the scale marker). A session is saved once.
- **2 Interpret**: the gait cycle side by side, each time-distance measure
  next to its reference band and smallest real change (the owner's, from a
  source with its page, in `data/knowledge/gait_references.csv`: none yet),
  the knee flexion curve.
- **3 Indicators**: each value past a threshold of
  `data/knowledge/gait_thresholds.csv` (Claude's drafts for the prototype,
  shown as drafts), with the session's data facts; the specialist marks it
  reviewed or dismisses it with a reason. Never a cause, diagnosis or fall
  risk.
- **4 Device and performance**: two sessions, their conditions checked, the
  device version that changed (linked to where it was logged), each
  measure's difference, "read with care", and the comparison sent to the
  case.

Measuring movement is a medical-device function: before any clinical use,
the capture system and this module need validation and regulatory advice.

**System map** (2026-10-27, `docs/design/01-system-map/`): the home page
(`/`, opened from the header's "AI Prosthetic Lab"). **1 System map**: the
four clinical parts and the four shared parts, each with its own module tabs
and a link; the brief's seven use cases and where each lives; the roll-out
proposal; the rules every part keeps; and "Waiting for the owner", counted
from the owner's files as they are now (draft clinic rules, gait thresholds,
roles and teaching cases; retention, gait reference bands and release
sign-offs not set; each part's cloud switch). **2 Architecture**
(`/architecture`): the six layers with where each lives in the code, one
answer end to end with the one step that leaves the machine and which parts
may take it, adding a domain, who owns what, and the owner's open questions
as they stand.

**Reasoning and review** (2026-10-25, `docs/design/07-reasoning-and-review/`)
has three pages:
- **1 Pathway** (`/reasoning`): the six steps every domain shares, each with
  what it produces and its guard; what the system never outputs; the checks
  every answer passes, each saying whether it is built here; where data goes,
  read from the settings (the model, the library build, each domain's cloud
  switch).
- **2 Review** (`/review`): the latest case's review page. Each AI statement
  takes Relevant / Not relevant / Summary is wrong, each gap Needed / Not
  needed with a reason kept with the case; the decision (approve as reviewed,
  approve with edits, reject the analysis) is signed and recorded once, with
  the model, prompt and library versions.
- **3 Quality and audit** (`/quality`): the development and held-out golden
  cases passing, the answer key covered, the share of AI sentences the quote
  check removed, the share of "summary is wrong" marks, the audit trail (who:
  not recorded until there is a login) and the release gate (all tests, the
  held-out result, the Arabic check, the owner's sign-off). It runs nothing:
  it reads what was recorded (`python scripts/verify_all.py --record`,
  `python -m quality.golden_cases ... --record`) and the owner's
  `data/quality/releases.csv`.

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

The source PDFs are not in git. `data/knowledge/sources/catalog.json` lists each one
with its DOI or web address; download them into the folders it names (see
`data/knowledge/sources/README.md`). Then build the search index:

```
python -m knowledge.ingest
```

This extracts each document's text to `data/knowledge/extracted/<id>.txt` (open those
files to see exactly what the system reads), cuts it into chunks of about
800 characters, and turns each chunk into a vector with the multilingual
model `BAAI/bge-m3` (about 2.3 GB, downloaded on the first run into the
Hugging Face cache, outside this folder). The result goes to
`data/knowledge/vector_store/`. Re-run it whenever a document, the catalog or the
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
     `reasoning/rag_topics.py`, which name the case's level and limb,
     "bilateral" for a bilateral case (left and right are not named), and
     the recorded K-level.
2. **Summarise (cloud model: Gemini API, or Claude API).** `reasoning/rag.py` sends three requests at
   once (gaps; functional level and components; fitting). Each holds the
   instructions (`SYSTEM_PROMPT`, versioned by `PROMPT_VERSION`), the
   case's amputation level, side and recorded K-level (nothing typed at
   intake), the topics and the passages found, each with its id. The
   instructions say: use only these passages; back every sentence with a
   quote copied character for character; say whom the source says it
   applies to, in its own words; give both sides where sources differ;
   copy a grade only if the passage prints it; never advise, choose, rank
   or say whether the patient is ready. The answer must be JSON in a fixed
   shape (structured output). `reasoning/writer.py` is the one place that
   talks to the API (`GeminiWriter` or `ClaudeWriter`, by `LLM_PROVIDER`),
   so another model, or a local one, can replace it.
3. **Check (code).** `reasoning/quote_check.py` keeps an item only if its
   quote is in the named passage word for word (line breaks and the print
   form of quotation marks and dashes aside), at least five words long,
   with an Arabic sentence. A grade not printed right after the quote is
   dropped. The page shows the passage's own words and the page the quote
   is on (looked up in `data/knowledge/extracted/`). Everything removed is kept with
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

`prosthetics/component_guide.py` and `prosthetics/fitting_guide.py` hold 59
statements copied word for word from VA/DoD 2024 and 2022, CMS 2017, the
ICRC gait-analysis manual 2014 and the WHO implementation manual, each with
its page, the source's own grade and a rule for which cases it applies to
(level, side, K-level, "ambulators"). Until 2026-10-11 they produced the
page; now they are the answer key the RAG is measured against
(`python -m quality.golden_cases --rag`), and the knowledge items are built
from them. `prosthetics/tests/test_component_guide.py` still checks that every quote is
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

The specialist marks each gap "Needed" or "Not needed for this case" (with
a reason, if they give one), and each component or fitting statement
"Relevant", "Not relevant for this case" or, for an AI summary, "Summary is
wrong" (or leaves them unmarked), then approves as reviewed, approves with
edits (with a note saying what should change) or rejects the analysis, and
signs and records it. Each decision is added as one line
of JSON to `data/records/review_log.jsonl`, and the review page lists the decisions
logged for the case. A line holds the decision, note, time (UTC), the case
as entered, every gap with its quote, citation and full passage, the
functional level, every component and fitting statement shown with its
mark, the intake values shown next to the readiness statements, and the
search settings, so it can be checked later even after the source library
is re-ingested. Since log version 5 (the RAG) it also holds each AI
sentence (English and Arabic), the passage behind each quote, and what the
AI was asked and gave: prompt version, model, tokens, time and what the
quote check removed. Labels and explanations are logged in English whichever
language the reviewer used; `ui_language` records which one it was. Since log version 11 (2026-10-25)
each decision also records the versions it was signed with (prompt, models, source library build). Lines are never changed or removed. The file stays on this
machine (it is in `.gitignore`). The 26 lines written while building and
checking the prototype were moved, unchanged, to
`data/records/review_log.test.jsonl` (2026-10-09), so `data/records/review_log.jsonl` holds
only the trial's decisions.

## Trial tools

For the Arabic term check and the specialist trial (details in
[data/quality/trial/README.md](data/quality/trial/README.md)):

```
python -m shared.arabic_terms export     # every interface text -> data/quality/trial/arabic_terms.csv
python -m shared.arabic_terms apply data/quality/trial/arabic_terms.csv   # a prosthetist's corrections -> shared/i18n.py
python -m quality.load_trial_cases        # the 15 prepared fake cases in data/quality/trial/cases/ -> the app
python -m quality.trial_report            # counts from the review log -> data/quality/trial/report.csv
                                         # (prosthetic cases; --domain orthotics -> report_orthotics.csv)
```

## Tests

```
python -m unittest
python -m quality.golden_cases     # fake cases with the output they must give (data/quality/golden_cases/)
python -m quality.golden_cases --rag   # also measure the RAG (calls the cloud model: free-tier quota or money)
python -m quality.golden_cases --held-out   # the frozen held-out cases instead (only when the owner asks)
python -m quality.retrieval_misses   # why expected statements don't reach the writer (development cases,
                                    # real search, no AI; --json FILE keeps every record)
python -m reasoning.sentence_checks # flags on stored AI sentences (data/records/cases/): measurement only
```

`reasoning.sentence_checks` flags kept AI items whose sentence has a number,
code (K0-K4, L-codes) or amputation level its quote doesn't, a negation that
differs, advice wording, or Arabic numbers or codes that differ from the
English. It removes nothing and the page doesn't show the flags; `--rag`
reports them too, so the owner can choose patterns from real output.

The golden cases, the two guides behind the answer key, the owner's rule
table, clinic rules and release sign-offs, the recorded results and the review
logs are protected in Claude Code: a project hook
(`.claude/hooks/protect_yardstick.py`) makes Claude ask before editing them.

`quality.retrieval_misses` measures the search's ceiling for `--rag`: for
each development case and expected statement, whether a passage the topic
search returns (top `RAG_TOP_K`) is from the statement's document and shares
six words in a row with it, and for each miss, why: the statement's own words
would find it (the topic query is the problem), even they don't (chunking or
embedding), or nothing can find it. The first run is in
`data/quality/baseline/2026-10-16/` and docs/FUTURE_WORK.md.

**Held-out cases (2026-10-13).** Of the 13 golden cases, 8 are for
development (`data/quality/golden_cases/`): they run by default, and the
search, topics and prompt may be tuned on them. The other 5 are held out
(`data/quality/golden_cases_held_out/`) to measure whether that tuning carries
over to cases it never saw. They are frozen: each one's content hash is in
`data/quality/golden_cases_held_out.json`, a test fails if a case changes, and
`--held-out` runs nothing until they match. They run only with `--held-out`,
when the owner asks, and each run is recorded in docs/FUTURE_WORK.md.

The golden cases run through the same analysis as the intake form (one is
submitted through the Arabic form and must match its English twin). Their
statement and functional-level checks test the answer key (the hand-written
rules); without `--rag` the AI is switched off. With `--rag` they measure
how many expected statements a checked RAG quote covers, any statement the
case must not show that one covers, the gap sources, what the quote check
removed, and tokens, time and estimated cost. The tests never call the API
(`shared/testing.py` switches it off and has a fake writer). Without
the search model or the vector store (or with `--no-search`) their gap
checks are skipped and the rest still run; the model is never downloaded.
A difference fails a case marked "reviewed" and warns for an "unreviewed" one.
The reviewed cases also run in `python -m unittest` (without their gap checks).
The three orthotic cases (`golden-ort-01..03`, unreviewed drafts) are
checked on their gaps only: there is no orthotic answer key yet.

```
python scripts/verify_all.py            # the checks for prompts 0-2, then the golden cases
python scripts/verify_all.py --record   # first the unit tests too; every result added to
                                        # data/quality/results/runs.jsonl for the quality page
```

A recorded run appends one line to `data/quality/results/runs.jsonl` (in git,
only ever added to) with the versions it ran with; `quality.golden_cases`
takes `--record` too (a held-out run only when the owner asks). The owner
signs a release off, and records who checked the Arabic texts, in
`data/quality/releases.csv` (`quality/releases.py`).

## Folder layout

One folder per part of the system (since 2026-10-24, the owner's decision),
following the parts of the target design (`docs/design/SYSTEM_DESIGN.md` §3):
the shared core, the shared parts, then one folder per clinical domain. Each
part holds its own code, its pages (`templates/<part>/`) and its tests
(`tests/`); the data is grouped the same way. Gait analysis, rehabilitation,
search and education, and the patient record will each get a folder of their
own when they are built.

```
app.py              Flask entry point: registers each part's pages
README.md, CLAUDE.md, requirements.txt

shared/             What every part uses: the case core (case_schema.py), the domain registry
                    (domains.py), the case store (store.py: memory + data/records/cases/), the forms'
                    parsers (forms.py: intake forms and every module page's tables, requirements and
                    follow-up), the module pages' helpers (module_pages.py), the field guide's mechanics,
                    the building blocks of every domain's modules (requirements.py: requirements,
                    priorities, marks, conflicts; followup.py: visits, outcome measures, alerts;
                    hard_stops.py: how a clinic rule stands for a case; fitting.py: step statuses, gait
                    phases; dates.py), the interface text in English and Arabic (i18n.py), the Arabic
                    term sheet, config (paths, settings, disclaimers)
  templates/        Every page's shared look: the header (AI Prosthetic Lab / <part>, the domain switch,
                    the numbered module tabs, EN | العربية, the case bar), the style, the base page, and the
                    screen pieces every domain reuses (ui_macros.html: measured-value status, information
                    needed, hard-stop checks with each rule's status, requirement chips, option marks,
                    evidence, the review page's statements read-only, outcome charts, alerts, loop back;
                    ui_forms.html: the requirements and conflicts forms, the follow-up forms)
  testing.py        What every part's tests share: the AI switched off, a fake writer and embedder,
                    the route-test base
  tests/
knowledge/          Knowledge layer: source catalog, text extraction, ingestion, search, search-quality
                    evaluation, knowledge items with the owner's evidence rules, the clinic rules
                    (clinic_rules.py: each rule's status, version, owner, approval date), the library's
                    build and documents as the pages show them (library.py), and the knowledge pages
                    (routes.py, nav.py: what the header shows for this shared part)
  templates/knowledge/
  tests/
reasoning/          The reasoning pathway every domain shares: pathway.py (search, AI summaries, gaps,
                    components, fitting), the RAG pipeline (rag.py, rag_topics.py), the AI writer
                    (Gemini or Claude API), the quote check, sentence checks, gap analysis without the AI,
                    the page's shapes (models.py), citations
  tests/
review/             Reasoning and review: the review page and the append-only decision log
                    (data/records/review_log.jsonl), the pathway and quality pages (nav.py: what the
                    header shows for this shared part)
  templates/review/
  tests/
search/             Search and education: smart search (engine.py: filters, the local search, the AI part
                    behind SEARCH_CLOUD_AI; log.py: the search log; routes.py, nav.py) and case-based
                    learning (learning.py: teaching cases, attempts, the learning log; learning_routes.py)
  templates/search/
  tests/
record/             Patient record and governance: each person's record (people.py: consent, cases, notes,
                    requests), the access trail (access.py), roles and retention (governance.py), the
                    timeline (timeline.py), routes.py, nav.py
  templates/record/
  tests/
rehabilitation/     Rehabilitation on a case of either domain: the plan and its vocabularies (plan.py), what the
                    sources say about each kind of intervention (sources.py), the four modules (routes.py),
                    nav.py
  templates/rehabilitation/
  tests/
gait/               Gait analysis on a case of either domain: sessions and the table import (session.py), the
                    owner's thresholds and references, indicators and comparisons (rules.py), routes.py, nav.py
  templates/gait/
  tests/
overview/           The system map, the home page (routes.py: the parts, the use cases, what waits for the owner;
                    the architecture), nav.py
  templates/overview/
  tests/
quality/            Quality and audit: the golden cases, retrieval misses, the trial report and the
                    trial-case loader, the recorded results (results.py), the owner's release sign-offs
                    (releases.py) and the quality page's measures (measures.py)
  tests/
prosthetics/        Use cases 01-02: the case (case.py), its gap fields (fields.py), topics, the AI's
                    instructions (rag.py), the hand-written statements behind the answer key
                    (component_guide.py, fitting_guide.py) and their support, the intake form (intake.py),
                    modules 1-5 (plan.py, hard_stops.py, modules.py), what the header shows for it (nav.py,
                    templates/prosthetics/case_bar.html)
  templates/prosthetics/
  tests/
orthotics/          Use case 03, stroke ankle-foot orthosis (drafts): the same files as prosthetics, plus
                    sources.py and fit.py (modules 1-6)
  templates/orthotics/
  tests/
scripts/            verify_all.py (with --record: also the unit tests, results recorded) and the checks
                    for prompts 0-2

docs/               SYSTEM_DESCRIPTION.md (what is built), FUTURE_WORK.md (decisions, measurements, open
                    items), the independent blueprint, older hand-offs and manual checks
  design/           The target system: SYSTEM_DESIGN.md and its screen designs (open index.html)

data/knowledge/     The owner's evidence rules, clinic rules and gait thresholds and references, the
                    knowledge items and the items to curate (in git)
  sources/          Knowledge documents: catalog.json and the registry in git, the PDFs kept local
  extracted/        Cleaned text per document (generated, not in git)
  vector_store/     Chunks and their vectors (generated, not in git)
  eval/             The search-quality queries and the orthotic topic searches (in git)
data/quality/       golden_cases/ and the frozen golden_cases_held_out/ with their manifest, measurement
                    baselines, trial/ (Arabic term sheet, prepared trial cases; the report not in git),
                    results/runs.jsonl (the recorded results) and releases.csv (the owner's sign-offs)
data/education/     teaching_cases/: the educator's invented teaching cases (in git; three drafts so far)
data/governance/    The owner's: roles.csv (who may see what) and retention.csv (in git)
data/records/       What the app records on this machine (not in git): cases/ (one JSON file per case),
                    the review logs, the search log, learning/ (attempts, the learning log, the
                    teaching cases' analyses), people/ (one file per person) and access_log.jsonl
```

A new clinical domain adds a package with the same files as the others (case.py,
fields.py, topics.py, rag.py, intake.py, nav.py, plan.py, hard_stops.py, modules.py)
and its name in `shared/domains.py`; shared code reaches it there, and its pages
reuse the shared header, screen pieces and forms (`shared/tests/test_domains.py`
checks the shape).

## Plan and open decisions

[docs/FUTURE_WORK.md](docs/FUTURE_WORK.md) tracks the build steps, open decisions and
known simplifications.

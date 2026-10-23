# AI Prosthetic Lab — system description (functional and structural)

State of the working tree on 2026-10-22 (the RAG, §4.8; orthotics as drafts,
§4.9, on the branch `orthotics`). Everything below runs and is tested
offline; the live run of the AI writer (Gemini's free tier since
2026-10-13, or the Claude API) is still to be measured. More history and the reasons behind each decision are in
`FUTURE_WORK.md`; how to run it is in `README.md`; principles, working
rules and the roadmap are in `CLAUDE.md`.

---

## 1. Purpose and scope

**AI Prosthetic Lab** is a local prototype of a clinical *decision-support*
tool for prosthetics specialists. It follows an Arabic visual brief ("AI
Prosthetic LAB", نموذج AI للأطراف الاصطناعية والتأهيل, 09/2026) that describes:

- four domains: prosthetics, orthotics, biomechanics/gait analysis, motor
  rehabilitation;
- a knowledge layer built on six kinds of source: scientific reference,
  protocol, professional knowledge, applied case, structured data,
  specialist expertise;
- a six-step reasoning pathway: case data → information analysis →
  specialised reasoning → assistive recommendations → specialist review →
  documented outcome;
- seven initial use cases (among them: 01 missing-information analysis,
  02 component selection support, 04 gait/motion data, 05 smart search,
  06 training and education, 07 follow-up).

**Built so far: the prosthetics domain only**, in three parts that follow
the brief's "evaluate the amputation, choose the components, design and fit":

| Part | What the specialist gets |
|---|---|
| Use case 01: information gaps | Which intake facts are missing before evaluation, each with an AI sentence on why the source says it matters, over a quote checked word for word (or "no source found") |
| Use case 02: component support | The patient's recorded functional level and what the sources say about it, and, per prosthetic component, what the passages found say for this case: an AI sentence each over a checked quote |
| Design and fitting | What the sources say on readiness for fitting, preparatory vs definitive prosthesis, fitting steps and alignment (AI sentences over checked quotes), shown next to what the case recorded |

Orthotics was started on 2026-10-16 (owner's decision, before the trial;
stroke AFO first) and built on 2026-10-22 as drafts awaiting the owner's
and an orthotist's review (§4.9): an orthotic intake at `/intake/orthotics`
(exam and gait by phase), its information gaps, what the sources say about
ankle-foot orthoses and FES, and about orthosis design and fitting, and the
orthotist's decision in the review log. On 2026-10-23 the "Orthotics Module
Design" canvas was applied (§4.9): modules 2-4 after the analysis, so the
brief's four orthotics capabilities each have a page (functional case
analysis; choosing and designing devices; linking the case to components and
materials; the digital design workflow). Gait analysis, rehabilitation and
follow-up are not started.

### Non-negotiable principles

1. **Decision support, not a replacement.** The system never diagnoses,
   prescribes, chooses or ranks components, or judges whether a patient is
   ready for fitting. The specialist decides; a disclaimer on every page
   says so.
2. **Every sentence backed by the source's own words.** Every quote and
   grade shown is word for word from a catalogued document, with its page.
   The summary sentences are written by a language model, labelled as AI,
   and each carries a quote that code finds word for word in its passage
   before it is shown. The instructions forbid advice; who a statement
   applies to comes only from the source's own wording.
3. **Search local, one cloud language model (since 2026-10-11).** The
   owner decided for a RAG: retrieval with the local embedding model, one
   cloud model for the summaries (`reasoning/writer.py`, one swap point):
   the Gemini API's free tier since 2026-10-13, or the Claude API
   (`LLM_PROVIDER`).
   The 2026-10-06 worry (LLMs often cite sources that don't support them)
   is met by the quote check and the AI label. Without the API the app
   shows the passages found.
4. **Fake data only, no patient identifiers** (no name, date of birth,
   address or record number). Cases are keyed by a random id. Part of the
   case is sent to the cloud model with the passages: the amputation level,
   side and recorded K-level (an orthotic case: condition, side and months
   since onset), never what was typed (on Gemini's free tier Google uses it
   to improve its products, and human reviewers may read it).
5. **Bilingual interface (English, Arabic right-to-left).** Quotes and
   citations stay in the source's language.

---

## 2. Technology and runtime

- Python 3.12+ (developed on 3.14), Flask 3, pypdf 6, numpy,
  sentence-transformers 6 with torch (GPU used if present, CPU works),
  anthropic 1.13 (only for the Claude API; key from `ANTHROPIC_API_KEY`).
- Language model (`LLM_PROVIDER`, three calls per case, at once):
  - `gemini` (default since 2026-10-13): `gemini-3.8-flash` on the Gemini
    API's free tier, through its REST endpoint with Python's own HTTP client
    (no SDK); key from `GEMINI_API_KEY`; structured output
    (`responseJsonSchema`); 429/500/503 tried twice more.
  - `claude`: `claude-opus-5-5`, effort medium, structured output,
    server-side fallbacks on a refusal.
- Embedding model: `BAAI/bge-m3` (multilingual, 1,024 numbers per vector,
  ~2.3 GB), pinned to one revision, loaded from the local Hugging Face cache
  (works offline).
- No database: the vector store is numpy + JSON files; each case is kept in
  memory and saved as one JSON file (`data/cases/`), so it survives a
  restart; review decisions are appended to a JSON-lines file.
- Single-user, local: `python app.py` serves http://127.0.0.1:5000. The first
  case takes ~10-30 s (model load); with the AI, each case then waits for
  the three API calls (time not yet measured live).

Commands:

```
python app.py                  # run the web app
python -m knowledge.ingest     # extract + chunk + embed all catalogued documents
python -m knowledge.evaluate   # measure retrieval quality (hit@1 / hit@5)
python -m knowledge.evaluate --orthotics  # the orthotic topic searches (data/eval/orthotic_topics.json)
python -m knowledge.items      # knowledge items with the owner's rules applied -> data/knowledge/
python -m intake.golden_cases  # development golden cases vs the app (gap checks need the model)
python -m intake.golden_cases --rag  # also measure the RAG (cloud model: free-tier quota or money)
python -m intake.golden_cases --held-out  # the frozen held-out cases (only when the owner asks)
python -m unittest             # 492 tests, about 40 s, no model, no API
python scripts/verify_all.py   # the 0-2 checks, then the golden cases
```

---

## 3. What the user does (functional walk-through)

Every page (since 2026-10-23) has the same header, from the orthotics design
canvas: a domain switch (Prosthetics / Orthotics), the domain's modules and,
on a case's pages, a case bar (the case, "test case · fake data", "the
specialist decides"). The prosthetics map (`/prosthetics`) names the brief's
five prosthetics capabilities and where each is: 01 تقييم حالات البتر (the
intake and the information gaps), 02 تحليل المتطلبات الوظيفية (functional level
and goals), 03 دعم اختيار المكونات (components), 04 دعم قرارات التصميم والتركيب
(design and fitting), all sections of the review page, which the header links
to (its one decision form marks them together); 05 المتابعة والتقييم
(follow-up) is not built. The orthotics map (`/orthotics`) does the same for
its four (§4.9).

1. **Intake form** (`GET /intake`). The user enters a test case: amputation
   level (12 levels, 6 lower and 6 upper limb) and side (left, right,
   bilateral) are required. Optional: age, body weight, cause of amputation,
   months since amputation; residual limb wound status, volume stability,
   skin, length/shape, pain, sensation; K-level (lower limb only), current
   activity, functional goals; up to three prior prostheses (or "no prior
   prosthesis"); comorbidities (one per line, "none" / "لا يوجد" = asked,
   none); contralateral limb; cognitive status; notes. Drop-downs offer an
   explicit "unknown", so "not asked" and "asked, unknown" stay different.
2. **Submit** (`POST /intake`). The case is validated (bad input → the form
   again, filled in as sent, with a message naming the field in the page's
   language, HTTP 400), then analysed: search (each missing field and each
   RAG topic), the AI's three answers, the quote check (§4.8). The result is kept in memory and in
   `data/cases/<case_id>.json`, and the browser is sent to the review page.
3. **Review page** (`GET /review/<case_id>`), top to bottom:
   - disclaimer (it opens "Research prototype, not validated for clinical
     use"); the model that wrote the AI summaries, as the provider reported
     it, with the prompt version; a warning if the source library could not
     be searched;
   - case summary;
   - every gap and statement from the AI shows "AI summary — check it
     against the quote below" and the sentence in the page's language, over
     the checked quote; a banner says why if the AI could not answer;
   - under every citation of a source whose licence is recorded in the
     catalog (Creative Commons), its authors and licence;
   - **information gaps**: each with why it is listed, the quoted sentences,
     citation (title, year, page), document language, similarity score,
     chunk id, the full passage, and the other passages considered; the
     reviewer marks each "Needed" / "Not needed for this case";
   - **functional level and goals**: the recorded K-level, what the
     passages found say about it (AI summaries over checked quotes), and the
     recorded activity and goals. Since the RAG (2026-10-11) the hand-written
     CMS descriptions and its two cautions (K-levels "should not be
     considered a functional classification"; research "has failed to
     connect" medical condition to K-level) are no longer shown here; they
     appear only if the search finds them and the AI reports them (once in
     the 7 lower-limb development cases, 2026-10-16: FUTURE_WORK);
   - **component statements** per component (knee, foot and ankle, pylon,
     socket, interface, suspension; upper limb: type of prosthesis, control
     and fit). Each shows the source's grade, the kind of source, the quote,
     extra quotes from the same document (scope, confidence, caveats) and a
     "Relevant / Not relevant for this case" mark. A section without an AI
     summary says why, as code knows it (the search found no passage, the AI
     reported nothing, or the checks removed what it gave), never what the
     sources do or don't say, and lists the passages the search found;
   - **design and fitting** (§4.5), marked the same way;
   - **decision**: note + Approve / Edit (note required) / Reject;
   - the decisions already logged for this case, with mark counts.
4. **Decision** (`POST /review/<case_id>/decision`). Validated, appended as
   one JSON line to `data/review_log.jsonl`, and the page shows a
   confirmation. An invalid submission (unknown decision, edit without note,
   a mark for a gap or statement not on the page, an unknown mark value) is
   refused with 400, nothing is logged, and the reviewer's choices are kept.
5. **Language** (`GET /language/<en|ar>?next=<path>`) sets a cookie and
   returns to the page (only local paths are accepted as `next`). On the
   intake form the language button instead posts the form
   (`switch_language`), which comes back filled in, in the other language;
   nothing is saved.

---

## 4. How each output is produced

### 4.1 Knowledge layer (pathway step 02)

**Catalog.** `data/sources/catalog.json` lists every document that is
ingested, with a permanent id, file, citation fields, `source_type` (the
brief's six), `domains`, `limbs` (lower/upper) and `language`. 19 documents:
16 English, 2 Arabic, 1 German; 9 protocol/guideline, 8 scientific
reference, 2 professional knowledge. Key ones: VA/DoD lower-limb amputation
guideline 2024, VA/DoD upper-limb guideline 2022, CMS Lower Limb Prosthetic
Workgroup consensus 2017 (K-levels), WHO standards for prosthetics and
orthotics 2017 (parts 1 and 2, in English and Arabic), German AWMF upper-limb
guideline 2024, ICRC *Prosthetic Gait Analysis for Physiotherapists* 2014,
several systematic reviews, the AAOP outcome-measures toolkit. A separate
`sources_manifest.csv` (63 rows) records acquisition of everything collected,
including sources not (yet) catalogued.

**Extraction** (`knowledge/extract.py`): pypdf, Unicode NFKC, soft hyphens
and table-of-contents dots removed, words split across lines rejoined,
reference lists cut (English, German and Arabic headings), lines repeated
on ≥40% of pages (headers/footers) dropped, literature-search syntax lines
dropped; warnings for scanned pages and broken Arabic. Output:
`data/extracted/<id>.txt` with `--- page N ---` markers (PDF-viewer page
numbers). These files are also what the quote tests check against.

**Ingestion** (`knowledge/ingest.py`): ~800-character chunks ending at
sentence ends, 150 characters of overlap, first/last page kept; each chunk
embedded with bge-m3. Store in `data/vector_store/`: `vectors.npy`,
`chunks.json` (same order), `info.json` (model and revision; retrieval
refuses a store built with another model). Now 3,468 chunks.

**Retrieval** (`knowledge/retrieval.py`): one search per missing field. The
query is the field's English query text plus the case's level and limb.
Similarity = dot product of unit vectors (cosine). Top 5 per field, with
filters: catalog domain includes "prosthetics"; language English or Arabic
(German is ingested but not searched: it added nothing and cost an Arabic
evaluation query); documents only about the other limb left out; documents
in `RETRIEVAL_EXCLUDED_DOCUMENTS` left out (now the ICRC manual: when
searched it replaced guideline quotes with page-header and table residue).
13 documents are searched for gaps.

**Evaluation** (`knowledge/evaluate.py`, `data/eval/retrieval_queries.json`):
30 hand-made queries (10 English, 8 Arabic, 5 German, 4 cross-language,
3 off-topic) each naming the pages that answer it. With the app's settings:
English 10/10 in the top 5, Arabic 7/8, cross-language 3/3. Correct answers
score ≥0.58, off-topic ≤0.44, hence the citation threshold 0.50.

### 4.2 Gap analysis (use case 01, `reasoning/gap_analysis.py`)

Since the RAG (§4.8) the AI picks each gap's passage and quote and writes
why the source says it matters. The steps below are what the page falls
back on without the AI.

`shared/field_guide.py` defines 17 fields that can be gaps (15 for an upper
limb: K-level and contralateral limb don't apply), each with a reviewer
label, a search query and per-language *topic terms* (regular expressions;
Arabic matched without vowel marks). For every field that is empty
("not recorded") or set to unknown ("recorded as unknown"), in that order:

1. take the retrieved passages, best score first;
2. cite the first one with score ≥ 0.50 **and** a topic-term match in its
   own language;
3. quote up to two of its sentences that mention the topic (≤400
   characters; an over-long "sentence", usually a table row, is cut to the
   words around the match);
4. if none passes, list the gap with "no passage found; the specialist
   judges whether it is needed".

Typical result with only level and side filled in: lower limb 17 gaps,
14-15 with a source; upper limb 15 gaps, 12 with a source. All citations
are currently English: the two Arabic documents (WHO service standards)
contain no amputee-assessment text, and Arabic matches were false senses
(e.g. الجلد as "leather"). Arabic citations wait for an Arabic clinical
source.

### 4.3 Functional level (part of use case 02)

Since the RAG the page shows the recorded K-level, activity and goals and
what the passages found say about the functional level (§4.8). The CMS
statements below are the answer key.

From CMS 2017: the description of the recorded K-level (K0-K4), two
cautions from the same document ("should not be considered a functional
classification"; research "has failed to connect" medical condition to
K-level), and all five descriptions for reference. Not shown for upper-limb
cases (K-levels describe lower-limb prostheses). Notes explain when
statements are hidden because no K-level is recorded or because K0 is.

### 4.4 Component statements (use case 02): the answer key

Since the RAG (§4.8) these no longer produce the page: they are the answer
key the RAG is measured against, and the knowledge items (§4.7) are built
from them. Hand-written, **not searched**: `reasoning/component_guide.py` holds 19
rules (plus 5 K-level descriptions and 2 cautions = 26 statements). A rule
is one statement with: id, component, source document, the source's own
grade ("Weak for", "Neither for nor against", or none), the quote and page,
and optional context quotes from the same document. Sources: VA/DoD lower
limb recommendations 15-19, VA/DoD upper limb recommendations 7-8, CMS
2017, and the ICRC manual (transtibial PTB and total-surface-bearing
sockets, transtibial suspension methods, total-contact socket conditions,
grafted skin and interface, hip flexion contracture and a lockable knee).

A rule applies to a case only as its source's wording says:

| Rule field | Meaning | Example |
|---|---|---|
| `levels` | amputation levels | knee rules: knee disarticulation, transfemoral, hip disarticulation |
| `k_levels` | shown only if one of these is recorded | CMS "at the K2 level" |
| `ambulators_only` | hidden when K0 is recorded | VA/DoD "For prosthetic ambulators, …" |
| `unilateral_only` / `bilateral_only` | side | VA/DoD UL rec 7 "unilateral"; ICRC "stubbies" for bilateral TF |

Where sources disagree (microprocessor knee at K2: VA/DoD "Weak for" for
ambulators vs CMS "may benefit"), both are shown; nothing is ranked.

### 4.5 Design and fitting (`reasoning/fitting_guide.py`, `fitting_support.py`): the answer key

Like §4.4, the answer key since the RAG. Same mechanism, 33 statements in four sections; socket, interface and
suspension stay with the components.

| Section | Statements (sources) |
|---|---|
| Readiness for fitting (8) | ICRC "ready for fitting" / "need preparatory treatment" / "cannot be fitted" lists; TT knee flexion contracture; VA/DoD LL rec 5 rigid/semi-rigid dressing after transtibial amputation ("Weak for"); VA/DoD UL "cleared … for a diagnostic socket fitting"; WHO preparatory training and decisions not to prescribe |
| Preparatory or definitive (6) | CMS: no evidence on preparatory vs definitive, no non-alignable preparatory prostheses; ICRC "A definitive socket is fitted to a stable stump"; stump shrinkage and recasting; stubbies (bilateral TF); VA/DoD UL prescription elements (starting "Design (e.g., preparatory versus definitive)") |
| Fitting, check-out, follow-up (7) | VA/DoD LL algorithm (prescription → fabrication, fitting, delivery → final check-out → does it meet goals?); ICRC fitting principles and structured process; TF check socket and length; WHO delivery check; VA/DoD UL signs that a prosthesis needs modifying |
| Alignment (12) | ICRC definition and steps; initial TT and TF alignment; for TT and TF, which alignment error may cause which gait deviation (foot angle and position, socket flexion/adduction, knee axis, knee friction); footwear/heel height; WHO "Individual customization is required for fit and alignment" |

The readiness section also lists what the case recorded for eight related
fields (time since amputation, wound, volume, skin, pain, sensation,
comorbidities, cognitive status) exactly as entered, without any judgement.
Statements never depend on these values.

Statements shown per case, for example: transtibial 22 fitting + 11
component; transfemoral K2 23 + 14; bilateral transfemoral 24 + 12; knee
or hip disarticulation, partial foot, Syme 16 fitting; upper limb 7.

### 4.6 Review log (pathway step 06, `review/decision_log.py`)

Each decision appends one self-contained JSON line (UTF-8, Arabic kept
readable), log version 5 (version 5, 2026-10-11, adds per statement
`origin`, `summary_en`, `summary_ar`, `chunk_id`, `passage`; per gap
`summary_en`, `summary_ar`; `generation` {prompt_version, writer, effort,
parts {gaps, components, fitting: status, reason, model, usage, seconds,
topics, items_kept, removed}}; the RAG settings). Version 4:

```
log_version, logged_at (UTC), case_id, decision, note, ui_language,
gaps[]:       field, label, status, why_needed, reviewer_judgement,
              source {chunk_id, citation, title, year, page, end_page, file,
                      language, score, quote, passage}  (null if no source)
components:   functional_level {lower_limb, k_level, description, cautions},
              notes[], sections[] {component, statements[]}
fitting:      recorded {field path: value as stored}, sections[]
statement:    id, doc_id, citation, quote, items[] (if a list), component,
              grade, source_type, context[] {citation, quote, items[]},
              reviewer_judgement
knowledge_warning, settings {model, revision, threshold, languages,
              domains, top_k}, case (the full case as entered)
```

Labels and explanations are logged in English whichever language was
shown. Lines are never edited or removed. The 26 lines written while
building the prototype were moved unchanged to `data/review_log.test.jsonl`;
`data/review_log.jsonl` started empty on 2026-10-09 for the trial.

### 4.7 Knowledge items and the owner's evidence rules (evidence track, roadmap item 3)

`KnowledgeItem` (`knowledge/models.py`) puts each curated statement into the
knowledge-item structure of the research brief. `knowledge/items.py` builds
one item per statement of both guides (59: 26 component, 33 fitting);
`knowledge/evidence_rules.py` applies the owner's rule table
(`data/knowledge/evidence_rules.csv`, 8 rules). `python -m knowledge.items`
(or `python -m knowledge.evidence_rules`) writes `data/knowledge/items.json`
(UTF-8, Arabic readable, the same file for the same guides and table) and
`items_to_curate.csv`, all in git.

| Fields | Filled from |
|---|---|
| `knowledge_id`, `statement`, `list_items`, `topic`, `source_id`, `grade_as_printed` | the guide: statement id, quote and the list it introduces, component or fitting section, document, grade exactly as stored ("" if none) |
| `citation`, `date`, `source_type` | the catalog: "title (year), p. N" as the review page shows it, the year, the kind of source |
| `domain` | "prosthetics" (both guides) |
| `evidence_layer`, `evidence_tag`, `confidence`, `validation_status`, `assigned_by` | the one rule whose condition matches: its three values as written (its "unassigned" too), "rule-assigned", the rule id. No rule or a "per item" rule: "unassigned", "unreviewed", "none" |
| `population`, `limitations` | "": only the owner's own values, for any item; rules never set them |

Each rule's "matches" text is a condition in `evidence_rules.py CONDITIONS`
on the catalog document, the grade as printed and, for the CMS K-level
descriptions, the knowledge ids; the owner approved each. Two rules matching
one item stop the run with nothing written, as does an invalid value in the
table; a rule never replaces evidence values set by hand or a reviewed item.
First pass (2026-10-10): R2 4, R3 4, R4 4, R5 5, R6 10, R7 4, R8 28 (R1
none); all 59 rule-assigned, 46 with the layer left unassigned by the rule,
so `items_to_curate.csv` (items no rule classified) has no rows.

The model refuses a value outside the allowed lists, an evidence value with
`assigned_by` "none", and "rule-assigned" without a rule id. The export works
the rules' values out again each time, but never replaces a file holding
what only the team can give (population or limitations, values set by hand,
a review, a filled-in cell of the sheet); `--force` does. The pages and the
review log don't use the items yet (step 3e will show "Evidence layer: not
rated by the source" where a rule left the layer unassigned).

### 4.8 The RAG: search, AI summaries, quote check (since 2026-10-11)

The owner's decision: the review page is produced by retrieval plus a
language model, not by rules (FUTURE_WORK.md, "RAG").

| Step | Where | What happens |
|---|---|---|
| Topics | `reasoning/rag_topics.py` | gaps: each missing field (field guide query); components: functional level (lower limb) and each component of `COMPONENTS` for the level (pylon: any lower limb); fitting: each section of `SECTIONS`. Queries name the level and limb, "bilateral" for a bilateral case (left or right is never named), and the recorded K-level |
| Search | `knowledge/retrieval.py` | one embed call; fields: top 5, ICRC manual left out; topics: top `RAG_TOP_K` = 6, nothing left out (`RAG_TOPIC_EXCLUDED_DOCUMENTS`) |
| Ask | `reasoning/rag.py`, `writer.py` | three calls at once (gaps; functional level and components; fitting), each with `SYSTEM_PROMPT` (`PROMPT_VERSION` rag-v3: rag-v2 plus `FAITHFULNESS`, the source's hedges and strength kept and nothing from outside the quote, and `ARABIC_TERMS`, the page's Arabic word for each thing), the case's amputation level, limb, side and recorded K-level only (`case_for_prompt`; nothing typed at intake; rag-v1 sent the whole case), the topics with passages, the passages with their ids; only topics with passages are asked; a part with none makes no call ("no passages") |
| Answer | structured output | `{"items": [{topic, passage_id, quote, sentence_en, sentence_ar, grade}]}`; topic and passage id limited to those given; grade one of five VA/DoD phrases or "" |
| Check | `reasoning/quote_check.py` | quote in the passage word for word (NFKC; whitespace, quotation marks and dashes as printed), ≥ `MIN_QUOTE_WORDS` = 5, Arabic sentence present, no repeat, ≤ 1 per gap field and ≤ `MAX_ITEMS_PER_TOPIC` = 4 per section; grade kept only if printed within 300 characters after the quote; the passage's own words are shown, the page looked up in `data/extracted/`. Then `drop_repeats` (2026-10-23): a component or fitting quote that holds or is held by one already shown under an earlier topic is not shown again (a "repeat", not a failed check; the section says so) |
| Show | `reasoning/rag.py` → `models.py` | items become `Gap` (gaps) and `CitedStatement` (origin "rag", id `rag-<topic>-<10 hex>`, the same in every case for the same topic and quote) in the existing sections, so the page, marks, log and trial report work unchanged |
| Without the AI | | no key, offline, refusal, cut off, unreadable: the part is "unavailable" with the reason (banner); gaps fall back to §4.2; sections list the passages found |

The tests never call the API (`tests/__init__.py` sets
`AI_PROSTHETIC_LAB_OFFLINE`; `tests/helpers.py` FakeWriter answers from the
passages it is given). The case file (version 2) keeps the AI's answer, so
a review page after a restart needs no new call.

**Measured so far (2026-10-11, no API):** how many of the answer key's
statements are inside a passage the search finds for the case's topics, over
the 13 golden cases (before 5 were held out on 2026-10-13; measurements for
tuning now use the 8 development cases). That is the most the RAG can cover:

| Passages per topic (`RAG_TOP_K`) | 6 (now) | 10 | 15 | 20 | 30 |
|---|---|---|---|---|---|
| Expected statements inside a retrieved passage | 129/359 (36%) | 144 (40%) | 148 (41%) | 168 (47%) | 183 (51%) |
| Distinct topic passages per case | ~46 | ~71 | ~99 | ~125 | ~169 |

At 6: functional level 8/8, foot and ankle 23/30, knee 6/9, readiness 28/69,
preparatory or definitive 18/47, fitting 14/54, alignment 10/66, socket
2/23, suspension 4/26. The four WHO statements were never found (the WHO
manual is searched, 408 passages, but never ranks in the top 6). Not yet
measured: the live answers (coverage, misquote rate, time, cost; `python -m
intake.golden_cases --rag`).

### 4.9 Orthotics: stroke ankle-foot orthosis (use case 03, drafts, 2026-10-22)

The same pipeline for a second domain. The fields, which are critical, the
topics, the prompt's rules and the golden cases are Claude's proposal,
marked on the pages as a draft awaiting the owner's and an orthotist's
review (FUTURE_WORK.md, "Orthotics").

| Part | Where | What it does |
|---|---|---|
| Intake | `orthotics/routes.py`, `/intake/orthotics` | `OrthoticCase`: condition (stroke), affected side, months since onset, goals, walking (status, aid, gait speed with its test, falls, deviations ticked by gait phase), exam (dorsiflexion with the knee extended and flexed, signed; plantarflexor tone grade with its scale; strengths; knee in stance; foot posture; sensation; proprioception; skin), footwear, donning, prior orthoses or FES, the orthotist's "what the orthosis must do" lines |
| Gaps | `shared/field_guide.py` `ORTHOTIC_FIELDS` | 23 fields; 6 marked critical (months since onset, goals, both dorsiflexion ranges, protective sensation, skin): the page marks them, hides nothing |
| Topics | `orthotics/topics.py` | devices: AFO or FES for walking, AFO types, effects and limits, cautions; design and fitting: design, fitting and check-out, timing and training, outcome measures. Each searched in its own wording (no case words: they cost right passages) |
| Search | `knowledge/retrieval.py` | only documents with the "orthotics" domain (`ORTHOTIC_RETRIEVAL_DOMAINS`), at most 3 passages per document (`ORTHOTIC_PASSAGES_PER_DOCUMENT`); prosthetic searches unchanged |
| Ask | `orthotics/rag.py` (`PROFILE`, rag-ort-v1) | three parts (gaps, devices, design and fitting); only condition, limb, side and months since onset sent; never sets angles, materials, trim lines or wearing times, never says whether this patient should have an orthosis or FES; another condition's passage only where the source says it applies to stroke |
| Show and log | `review/templates/review.html`, `decision_log.py` | the case as recorded, deviations by phase, the requirements as written, devices side by side (never ranked); `LOG_VERSION` 6 adds "domain" |

Measured (2026-10-22, `python -m knowledge.evaluate --orthotics`, two fake
cases, 13 topics each): a right passage among those the AI sees in 22 of
26 searches, up from 10 at the first build. Still missed: protective
sensation and plantarflexor tone, for which the library has little.

**After the analysis: modules 2-4 (2026-10-23, from the design canvas).**
Every value is the orthotist's (`orthotics/plan.py` `OrthoticPlan`, saved
in the case file, version 3); the tool writes, suggests and ranks nothing.

| Module (brief capability) | Page | What it holds |
|---|---|---|
| Map | `/orthotics` | the modules and the brief's capabilities they cover |
| 2 Requirements (the bridge) | `/orthotics/<id>/requirements` | what the orthosis must do, in the orthotist's words, each tied to the case findings it comes from (gait deviations by phase, exam values, goals) and given a priority; the information still missing beside it |
| 3 Options (choosing and designing devices; linking the case to components and materials) | `/orthotics/<id>/options` | up to three options side by side, never ranked: device type, materials and parts each tied to the requirements it serves (so a part leads back to a finding), the orthotist's yes/partly/no marks and notes; the choice with its required reason, appended to the review log ("design_choice", `LOG_VERSION` 7, with the whole plan); saving the options again keeps the choice only if the chosen option is still the same device with the same parts |
| 4 Digital design (the digital design workflow) | `/orthotics/<id>/design` | capture, rectify, parameters, fabricate, release: status, method and notes per step; the design parameters, every save a new version |

Next to each device type, part and step: what the source library says,
found by local search on fixed wording with topic words
(`orthotics/sources.py`), quoted as printed with its page, labelled as not
summarised and not checked to support the case. Nothing on these pages goes
to the AI. All orthotic pages share the canvas's look (header with the
modules, case bar, cards; system fonts). Not built from the canvas: modules
5-6, AI-suggested parameters and code-made judgements (principles 1-2),
hard stops (await the owner's rules), the scan viewer and simulation.

---

## 5. Structure

```
app.py                     Flask app: registers blueprints, language route, template helpers
templates/                 every page's look (2026-10-23): ui_style.html, ui_header.html (domain switch,
                           the domain's modules, case bar), ui_base.html (the map and module pages)
shared/
  case_schema.py           CaseCore (shared by every domain) + Case (prosthetics) + OrthoticCase, enums, validation, to_dict/case_from_dict
  field_guide.py           the 17 prosthetic and 23 orthotic gap fields: label, search query, topic terms (en/de/ar)
  config.py                paths, model, chunk and search settings, threshold, disclaimer
  i18n.py                  all interface text in English and Arabic
  arabic_terms.py          Arabic term sheet: export for a prosthetist, apply corrections back
  store.py                 CaseRecord store: memory + one JSON file per case in data/cases/ (version 2: with the AI's answer)
intake/
  routes.py                GET/POST /intake: form → Case → analyse_case() (search, AI, quote check) → store
  load_trial_cases.py      loads the prepared trial cases (data/trial/cases/) via analyse_case()
  golden_cases.py          runs the golden cases through analyse_case(), reports differences
  templates/intake_form.html
knowledge/
  catalog.py               loads and validates catalog.json (SourceDocument)
  extract.py               PDF/txt → cleaned text per page
  ingest.py                chunking, embedding, vector store files
  embedding.py             bge-m3 loading (local cache first) and embed_texts()
  retrieval.py             VectorStore, filtered search, one search per missing field and per RAG topic
  evaluate.py              hit@1/hit@5 evaluation
  models.py                ProtocolChunk (a retrieved passage with citation and score),
                           KnowledgeItem (a curated statement with its evidence fields)
  items.py                 one KnowledgeItem per guide statement, rules applied; export to data/knowledge/
  evidence_rules.py        loads the owner's rule table, a condition per rule, applies the rules
reasoning/
  models.py                Gap, Quote, GuidelineStatement, CitedStatement,
                           ComponentSection, FunctionalLevel, ComponentSupport, FittingSupport
  rag_topics.py            the RAG's topics per case and their search queries
  rag.py                   the RAG: prompts, schema, three parts at once, item check, page shapes
  writer.py                the one place that calls a language model (GeminiWriter, ClaudeWriter, OfflineWriter)
  quote_check.py           a quote word for word in its passage; its page in data/extracted/
  gap_analysis.py          use case 01 without the AI (the fallback), and the gap explanations
  component_guide.py       hand-written component rules + K-level statements (the answer key)
  component_support.py     picks component statements for a case; applies(); cite()
  fitting_guide.py         hand-written design and fitting rules (the answer key)
  fitting_support.py       picks fitting statements; recorded readiness values
review/
  routes.py                GET /review/<id>, POST /review/<id>/decision
  decision_log.py          validation, log entry building, append/read
  trial_report.py          counts of the reviewers' marks in the log, one domain at a time → data/trial/report.csv
  templates/review.html
orthotics/                 use case 03 (drafts): topics.py, rag.py (PROFILE), routes.py (/intake/orthotics),
                           plan.py (OrthoticPlan: modules 2-4), sources.py (passages per device, part, step),
                           modules.py (/orthotics: map, requirements, options, choice, design), templates/
tests/                     unittest suite (492 tests) + a tiny fake embedder and a fake AI writer
scripts/                   verify_prompts_0_2.py (checks for prompts 0-2), verify_all.py (that + golden cases)
data/
  sources/                 catalog.json, 00_registry/sources_manifest.csv (in git); PDFs (local only)
  knowledge/               evidence_rules.csv (the owner's), items.json, items_to_curate.csv
                           (in git; regenerate after changing a guide or the rule table)
  extracted/               cleaned text per document (generated)
  vector_store/            vectors.npy, chunks.json, info.json (generated)
  eval/retrieval_queries.json, eval/orthotic_topics.json, eval/golden_cases/golden-NN.json
                           and golden-ort-NN.json (development),
                           eval/golden_cases_held_out/golden-NN.json (held out, frozen by
                           eval/golden_cases_held_out.json)
  cases/                   one JSON file per case (local only)
  trial/                   arabic_terms.csv, cases/trial-NN.json (in git); report.csv (local only)
  review_log.jsonl         decisions (local only); review_log.test.jsonl: earlier test lines
```

### 5.1 Core data model

```
Case
  amputation_level: AmputationLevel   (required; 12 values)
  side: Side                          (required; left / right / bilateral)
  case_id, created_at                 (generated)
  age_years, body_weight_kg, etiology, months_since_amputation
  residual_limb: ResidualLimb
      wound_status (healed/healing/open/unknown), volume_stability
      (stable/fluctuating/unknown), skin_condition, length_description,
      pain, sensation, notes
  activity: ActivityProfile
      k_level (K0-K4/unknown, lower limb only), description, functional_goals
  prior_devices: None (not asked) | [] (none used) | [PriorDevice(description,
      years_used, currently_using, issues)]
  comorbidities: None | [] (none reported) | [str]
  contralateral_limb_status, cognitive_status, intake_notes
  -> unrecorded_fields(), unknown_fields(): dotted paths, skipping fields
     that don't apply (K-level and contralateral limb for upper limb)

OrthoticCase (CaseCore; dict carries "domain": "orthotics"; §4.9)
  condition (stroke), side (affected; required), months_since_onset, functional_goals
  walking: Walking(status, walking_aid, gait_speed_m_s + gait_speed_test,
      falls_last_6_months, deviations: None (not observed) | [] | [GaitDeviation], other_deviations)
  exam: OrthoticExam(dorsiflexion_knee_extended_deg, dorsiflexion_knee_flexed_deg (±90),
      plantarflexor_tone_scale + _grade + _notes, dorsiflexor_strength, knee_extensor_strength,
      knee_in_stance, foot_posture, protective_sensation, proprioception, skin_condition)
  footwear, donning, prior_orthoses: None | [] | [PriorDevice],
  implanted_electronic_device (never a gap), requirements: [str] (the orthotist's, at intake)

OrthoticPlan (orthotics/plan.py; CaseRecord.plan; case file version 3)
  requirements: [Requirement(id "R1", text, findings: [case_findings() key], priority must/should/nice)]
  options: [DesignOption(id A-C, device: DeviceType, parts: [OptionPart(part, requirement ids)],
            marks {requirement id: yes/partly/no}, notes)], chosen, choice_reason
  steps {capture|rectify|parameters|fabricate|release: StepRecord(status, method, notes)}
  parameter_versions: [ParameterVersion(number, values {parameter: text}, note, saved_at)]

Gap(field, label, status, why_needed, source_protocol_reference, evidence: ProtocolChunk, excerpt,
    summary_en, summary_ar)

Quote(page, text, end_page=None, items=())          words exactly as printed; items = a list it introduces
GuidelineStatement(id, component, doc_id, grade, quote, context: tuple[Quote])
Rule(statement, levels, k_levels=None, ambulators_only, unilateral_only, bilateral_only)
CitedStatement(statement, title, year, language, source_type,    ready to show and log
               origin ("guide"/"rag"), summary_en, summary_ar, chunk_id)
ComponentSection(component, statements: [CitedStatement])
ComponentSupport(functional: FunctionalLevel, sections, notes)
FittingSupport(sections, recorded: [(field path, value)])

CaseRecord(case, retrieved_chunks, gaps, knowledge_warning, components, fitting, generation, plan)

Generation(prompt_version, writer, effort, parts {gaps, components, fitting: Part})
Part(kind, status "ok"/"unavailable"/"no passages", reason, model, usage, seconds, topics,
     items: [Item], removed: [{topic, passage_id, quote, reason, dropped}])
Item(id, topic, chunk_id, doc_id, quote, page, end_page, sentence_en, sentence_ar, grade)

KnowledgeItem(knowledge_id, statement, list_items, domain, topic, source_id,
              citation, date, source_type, grade_as_printed,            recorded
              population, limitations, evidence_layer, evidence_tag,    the owner's
              confidence, validation_status, assigned_by)               (§4.7)
```

### 5.2 Request flow

```
POST /intake
  → _case_from_form (validation; errors → 400 + form)
  → retrieve_relevant_chunks(case)      fields and RAG topics (no vector store: a warning, no passages)
  → generate(case, chunks, writer)      three AI calls at once; each item quote-checked
  → gaps_from(), components_from(), fitting_from()   (without the AI: analyze_gaps, passages listed)
  → store.save(CaseRecord) → 302 /review/<case_id>

POST /review/<id>/decision
  → record_decision (validate → build entry → append one line) → 302 back with ?saved=1
```

### 5.3 Key settings (`shared/config.py`)

| Setting | Value |
|---|---|
| `EMBEDDING_MODEL_NAME` / revision | `BAAI/bge-m3`, pinned |
| `CHUNK_SIZE_CHARS` / `CHUNK_OVERLAP_CHARS` | 800 / 150 |
| `RETRIEVAL_TOP_K` | 5 |
| `MIN_RELEVANCE_SCORE` | 0.50 |
| `RETRIEVAL_LANGUAGES` | en, ar |
| `RETRIEVAL_DOMAINS` | prosthetics |
| `ORTHOTIC_RETRIEVAL_DOMAINS` / `ORTHOTIC_PASSAGES_PER_DOCUMENT` | orthotics / 3 (orthotic searches only) |
| `RETRIEVAL_EXCLUDED_DOCUMENTS` | the ICRC gait-analysis manual (gap search only) |
| `RAG_TOP_K` / `RAG_TOPIC_EXCLUDED_DOCUMENTS` | 6 / none |
| `MIN_QUOTE_WORDS` / `MAX_ITEMS_PER_TOPIC` | 5 / 4 (gap fields: 1) |
| `LLM_MODEL` / `LLM_EFFORT` / `LLM_FALLBACKS` | `claude-opus-5-5` / medium / on |
| `PROMPT_VERSION` | rag-v3 (2026-10-23: the source's hedges kept, the page's Arabic terms; rag-v2 2026-10-16; rag-v1 sent the whole case) |
| `OFFLINE_ENV` | `AI_PROSTHETIC_LAB_OFFLINE`: set, the AI is never called |
| `SOURCES_NOT_INGESTED` | registry, AI-safety/regulation references, datasets |

### 5.4 Languages

`shared/i18n.py` holds every interface text in English and Arabic: labels,
choices, messages, disclaimer, gap explanations, section names. Arabic pages
are `dir="rtl"` with logical CSS (start/end), user text and English
citations isolated (`<bdi>`, `dir="auto"`, Unicode isolates) so the browser
doesn't reorder them. Not translated: quotes and citations, what the user
typed, technical messages. Tests fail if any text lacks Arabic or a template
uses a missing key.

---

## 6. Quality checks

- **492 unit tests** (standard `unittest`, fake embedder, fake AI writer, no
  model load, never the API): the RAG (topics, prompt rules, schema, every
  reason an item is removed, parts, fallback, the Claude call with its SDK
  client replaced, the Gemini call with its HTTP call replaced: request,
  key in a header, unusable answers, errors, retries), the quote check (a changed word, a comma, "...", a short
  quote refused; quotation marks and Arabic handled; page lookup), and
  schema, catalog, extraction, ingestion, retrieval filters, field guide,
  gap analysis, component and fitting applicability, review log, case
  files across a simulated restart, pages (through Flask's test client,
  English and Arabic, incl. refilled forms and translated errors),
  translations, knowledge items (allowed values, one item per statement,
  exported files identical on re-export and in step with the guides and
  the rule table) and the evidence rules (the approved mapping, overlaps
  and invalid values refused, population and limitations never touched).
- **Quote test** (`tests/test_component_guide.py`): every quote and context
  quote of all 59 statements is checked word for word on its page of
  `data/extracted/`; list items must follow their heading in order; each
  VA/DoD grade must be the one printed after the recommendation. Mutation
  checks (a changed word, a wrong page, swapped list items, a wrong grade)
  were all caught.
- **Retrieval evaluation** (§4.1).
- **Golden cases** (`python -m intake.golden_cases`, `data/eval/golden_cases/`):
  fake cases with the statements, functional level and gaps they must give
  (and the statements they must not), run through the intake analysis.
  13 cases, all 52 rules decided in each: every lower-limb level,
  unilateral and bilateral, K0-K4, K-level unknown and not recorded, upper
  limb unilateral and bilateral, an empty intake (17 gaps), and one case
  submitted through the Arabic form that must match its English twin;
  0 differences (2026-10-10). Three are reviewed (transtibial K3,
  transfemoral K2, transradial) and also run in `python -m unittest`; ten
  are unreviewed drafts. Gap checks need the model and are skipped without
  it; a difference fails a reviewed case and warns for an unreviewed one.
  Since 2026-10-13, 5 of the 13 are held out (`data/eval/golden_cases_held_out/`:
  golden-06, -07, -08, -10, -11): frozen by content hash (a test fails if one
  changes), never tuned on, run only with `--held-out` when the owner asks.
  The default run and all tuning use the other 8. Three orthotic drafts
  (`golden-ort-01..03`, 2026-10-22, unreviewed) are checked on their gaps
  only, as there is no orthotic answer key; they pass with the real search.
- **Live run checks** with the real model over HTTP. Latest (2026-10-09):
  13 English and 2 Arabic cases, 1,514 page checks, 0 failed (every
  applicable statement on the page word for word, statements for other
  levels absent, no gap citing an excluded document); server log 74
  requests, no errors; screenshots checked by eye in both languages.

---

## 7. Known limitations

- Single user, single process; no login. Free-text case fields are saved
  as typed, so trial users must not type patient identifiers into them.
- "Edit" records a note; it does not edit the case or the lists.
- Switching language on the review page loses an unsent note and marks
  (the intake form keeps its input).
- Some gap quotes are table residue or start with footnote numbers; the
  topic check proves a passage *mentions* a topic, not that it says the
  information is needed.
- No Arabic clinical source, so no Arabic citations.
- RAG (2026-10-11): the search finds only 36% of the answer key's statements
  for the golden cases (§4.8), so the AI can't cover more; the live coverage,
  misquote rate, time per case and cost are not yet measured.
- The quote check proves a quote is in its passage, not that the AI's
  sentence says only what the quote says; the label asks the specialist to
  check. The AI's Arabic sentences have not been read by an Arabic-reading
  prosthetist.
- With the AI, the app depends on a cloud API (internet, a key; Gemini's
  free tier: daily limits Google doesn't publish, and Google may use and
  people may read what is sent; Claude: cost), and the passages plus the
  case's amputation level, side and recorded K-level leave the machine
  (nothing typed at intake, since 2026-10-16). Two live runs so far, both
  on golden-01 with `gemini-3.8-flash` (2026-10-23): no misquotes; 5 and
  then 6 of 34 answer-key statements covered; 137 and 240 s per case while
  Google reported high demand. In the first, three sentences said more
  than their quote; rag-v3 fixed those, and one "need to" still became
  "must" (FUTURE_WORK.md, "First live run").
- Library gaps: upper-limb terminal devices and partial-hand prostheses;
  alignment and transtibial socket text come from one training manual
  (ICRC, written for its own polypropylene technology).
- CMS 2017 is US Medicare policy; its statements are shown as written.
- Arabic clinical terms in `shared/i18n.py` have not yet been checked by an
  Arabic-reading prosthetist (or, for the orthotic pages, an orthotist).
- Orthotics (§4.9) is a draft: its fields, critical flags, topics, prompt
  and golden cases await the owner and an orthotist; it was tuned on a
  two-case yardstick with no held-out set; protective sensation and
  plantarflexor tone find little in the library (G03, the APTA/ANPT 2021
  AFO/FES guideline, needs a manual download); no live orthotic AI run yet,
  and none possible while `ORTHOTIC_CLOUD_AI` is off (owner's decision
  2026-10-23: orthotic pages show the passages without summaries).
  Modules 2-4 (2026-10-23) show passages for each device, part and step
  unsummarised and unchecked; their vocabularies are drafts; modules 5-6 of
  the canvas are not built.

---

## 8. Status and next steps

- Git: the trial-readiness fixes and trial tooling are in `053a190`
  (pushed); the knowledge items and the owner's evidence rules (§4.7) and
  the golden cases are committed on top, not pushed. The RAG (§4.8,
  2026-10-11) is in the working tree, not committed.
- RAG next: a live run on one case (needs an API key), then the golden
  cases with `--rag`, after the owner's decision on the search's 36%
  ceiling (§4.8). Evidence values (3e) apply to the hand-written statements;
  showing them next to a RAG statement that covers one is not built.
- Roadmap (in `CLAUDE.md`): trial readiness (1 stabilise — done; 2 trial
  tooling — done, then a real prosthetist trial), evidence (3 knowledge-item and
  evidence fields — structure and the first rule pass done; the owner's own
  values and showing them on the review page (3e) next; 4 golden-case
  benchmark — runner and 13 cases, 3 reviewed), product (5 smart search,
  6 split `Case` — core done 2026-10-17, 7 orthotics — started 2026-10-16
  by the owner's decision, before the trial, stroke AFO first; built as
  drafts on 2026-10-22 on the branch `orthotics`, not committed). An
  Arabic-reading prosthetist should also check the Arabic terms.
- Possible: Arabic versions of quotes from the WHO implementation manual
  (it has an Arabic edition in the library); fixing the smaller limitations.
- `Case` is split into a shared core (`CaseCore`) plus the prosthetics
  case; the orthotic case adds its own section once the owner has set its
  fields. Follow-up needs a pseudonymous link between visits; gait data
  needs its own upload path and regulatory advice (it falls outside
  non-device decision support under FDA CDS guidance, Criterion 1).

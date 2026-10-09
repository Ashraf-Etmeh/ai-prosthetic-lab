# AI Prosthetic Lab — system description (functional and structural)

State of the working tree on 2026-10-09. Everything below runs and is
tested. More history and the reasons behind each decision are in
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
| Use case 01: information gaps | Which intake facts are missing before evaluation, each with a quoted passage from the source library saying why it matters (or "no source found") |
| Use case 02: component support | The patient's functional level (K-level) as the source defines it, and, per prosthetic component, the guideline statements that apply to this case |
| Design and fitting | Statements on readiness for fitting, preparatory vs definitive prosthesis, fitting steps and alignment, shown next to what the case recorded |

Orthotics, gait analysis, rehabilitation and follow-up are not started.

### Non-negotiable principles

1. **Decision support, not a replacement.** The system never diagnoses,
   prescribes, chooses or ranks components, or judges whether a patient is
   ready for fitting. The specialist decides; a disclaimer on every page
   says so.
2. **Only the sources' own words.** Every reason, statement and grade shown
   is quoted word for word from a catalogued document, with its page. The
   system adds no clinical advice of its own. Applicability of a statement
   comes only from the source's own wording (amputation level, "unilateral",
   "at the K2 level", "ambulators", "TT"/"TF").
3. **No language model, no cloud.** Rules plus a local embedding model.
   An LLM was ruled out because it is a cloud service and because LLMs often
   cite sources that don't support their statements.
4. **Fake data only, no patient identifiers** (no name, date of birth,
   address or record number). Cases are keyed by a random id.
5. **Bilingual interface (English, Arabic right-to-left).** Quotes and
   citations stay in the source's language.

---

## 2. Technology and runtime

- Python 3.12+ (developed on 3.14), Flask 3, pypdf 6, numpy,
  sentence-transformers 6 with torch (GPU used if present, CPU works).
- Embedding model: `BAAI/bge-m3` (multilingual, 1,024 numbers per vector,
  ~2.3 GB), pinned to one revision, loaded from the local Hugging Face cache
  (works offline).
- No database: the vector store is numpy + JSON files; each case is kept in
  memory and saved as one JSON file (`data/cases/`), so it survives a
  restart; review decisions are appended to a JSON-lines file.
- Single-user, local: `python app.py` serves http://127.0.0.1:5000. The first
  case takes ~10-30 s (model load), later cases ~0.1-0.2 s.

Commands:

```
python app.py                  # run the web app
python -m knowledge.ingest     # extract + chunk + embed all catalogued documents
python -m knowledge.evaluate   # measure retrieval quality (hit@1 / hit@5)
python -m unittest             # 219 tests, ~1 s, no model needed
```

---

## 3. What the user does (functional walk-through)

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
   language, HTTP 400), then analysed: search, gap analysis, component
   support, fitting support. The result is kept in memory and in
   `data/cases/<case_id>.json`, and the browser is sent to the review page.
3. **Review page** (`GET /review/<case_id>`), top to bottom:
   - disclaimer; a warning if the source library could not be searched;
   - case summary;
   - **information gaps**: each with why it is listed, the quoted sentences,
     citation (title, year, page), document language, similarity score,
     chunk id, the full passage, and the other passages considered; the
     reviewer marks each "Needed" / "Not needed for this case";
   - **functional level and goals**: the source's description of the
     recorded K-level, what the same source says K-levels are *not*, all
     five descriptions for reference, and the recorded activity and goals;
   - **component statements** per component (knee, foot and ankle, pylon,
     socket, interface, suspension; upper limb: type of prosthesis, control
     and fit). Each shows the source's grade, the kind of source, the quote,
     extra quotes from the same document (scope, confidence, caveats) and a
     "Relevant / Not relevant for this case" mark. A component with nothing
     in the library says so;
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

From CMS 2017: the description of the recorded K-level (K0-K4), two
cautions from the same document ("should not be considered a functional
classification"; research "has failed to connect" medical condition to
K-level), and all five descriptions for reference. Not shown for upper-limb
cases (K-levels describe lower-limb prostheses). Notes explain when
statements are hidden because no K-level is recorded or because K0 is.

### 4.4 Component statements (use case 02)

Hand-written, **not searched**: `reasoning/component_guide.py` holds 19
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

### 4.5 Design and fitting (`reasoning/fitting_guide.py`, `fitting_support.py`)

Same mechanism, 33 statements in four sections; socket, interface and
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
readable), log version 4:

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

---

## 5. Structure

```
app.py                     Flask app: registers blueprints, language route, template helpers
shared/
  case_schema.py           Case data model, enums, validation, to_dict/from_dict
  field_guide.py           the 17 gap fields: label, search query, topic terms (en/de/ar)
  config.py                paths, model, chunk and search settings, threshold, disclaimer
  i18n.py                  all interface text in English and Arabic
  arabic_terms.py          Arabic term sheet: export for a prosthetist, apply corrections back
  store.py                 CaseRecord store: memory + one JSON file per case in data/cases/
intake/
  routes.py                GET/POST /intake: form → Case → analyse_case() → store
  load_trial_cases.py      loads the prepared trial cases (data/trial/cases/) via analyse_case()
  templates/intake_form.html
knowledge/
  catalog.py               loads and validates catalog.json (SourceDocument)
  extract.py               PDF/txt → cleaned text per page
  ingest.py                chunking, embedding, vector store files
  embedding.py             bge-m3 loading (local cache first) and embed_texts()
  retrieval.py             VectorStore, filtered search, one search per missing field
  evaluate.py              hit@1/hit@5 evaluation
  models.py                ProtocolChunk (a retrieved passage with citation and score)
reasoning/
  models.py                Gap, Quote, GuidelineStatement, CitedStatement,
                           ComponentSection, FunctionalLevel, ComponentSupport, FittingSupport
  gap_analysis.py          use case 01
  component_guide.py       hand-written component rules + K-level statements
  component_support.py     picks component statements for a case; applies(); cite()
  fitting_guide.py         hand-written design and fitting rules
  fitting_support.py       picks fitting statements; recorded readiness values
review/
  routes.py                GET /review/<id>, POST /review/<id>/decision
  decision_log.py          validation, log entry building, append/read
  trial_report.py          counts of the reviewers' marks in the log → data/trial/report.csv
  templates/review.html
tests/                     unittest suite (262 tests) + a tiny fake embedder
data/
  sources/                 catalog.json, 00_registry/sources_manifest.csv (in git); PDFs (local only)
  extracted/               cleaned text per document (generated)
  vector_store/            vectors.npy, chunks.json, info.json (generated)
  eval/retrieval_queries.json
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

Gap(field, label, status, why_needed, source_protocol_reference, evidence: ProtocolChunk, excerpt)

Quote(page, text, end_page=None, items=())          words exactly as printed; items = a list it introduces
GuidelineStatement(id, component, doc_id, grade, quote, context: tuple[Quote])
Rule(statement, levels, k_levels=None, ambulators_only, unilateral_only, bilateral_only)
CitedStatement(statement, title, year, language, source_type)   ready to show and log
ComponentSection(component, statements: [CitedStatement])
ComponentSupport(functional: FunctionalLevel, sections, notes)
FittingSupport(sections, recorded: [(field path, value)])

CaseRecord(case, retrieved_chunks, gaps, knowledge_warning, components, fitting)
```

### 5.2 Request flow

```
POST /intake
  → _case_from_form (validation; errors → 400 + form)
  → retrieve_relevant_chunks(case)      (if no vector store: gaps still listed, with a warning)
  → analyze_gaps(case, chunks)
  → component_support(case), fitting_support(case)
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
| `RETRIEVAL_EXCLUDED_DOCUMENTS` | the ICRC gait-analysis manual |
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

- **262 unit tests** (standard `unittest`, fake embedder, no model load):
  schema, catalog, extraction, ingestion, retrieval filters, field guide,
  gap analysis, component and fitting applicability, review log, case
  files across a simulated restart, pages (through Flask's test client,
  English and Arabic, incl. refilled forms and translated errors),
  translations.
- **Quote test** (`tests/test_component_guide.py`): every quote and context
  quote of all 59 statements is checked word for word on its page of
  `data/extracted/`; list items must follow their heading in order; each
  VA/DoD grade must be the one printed after the recommendation. Mutation
  checks (a changed word, a wrong page, swapped list items, a wrong grade)
  were all caught.
- **Retrieval evaluation** (§4.1).
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
- Library gaps: upper-limb terminal devices and partial-hand prostheses;
  alignment and transtibial socket text come from one training manual
  (ICRC, written for its own polypropylene technology).
- CMS 2017 is US Medicare policy; its statements are shown as written.
- Arabic clinical terms in `shared/i18n.py` have not yet been checked by an
  Arabic-reading prosthetist.

---

## 8. Status and next steps

- Git: design and fitting committed as `988f13f` (2026-10-09); `main` is
  4 commits ahead of GitHub (not pushed). The trial-readiness fixes (case
  files, refilled form, language switch, translated errors, separate test
  log) and the trial tooling (Arabic term sheet, 15 prepared cases and
  their loader, the trial report) are done and tested but not yet
  committed.
- Roadmap (in `CLAUDE.md`): trial readiness (1 stabilise — done; 2 trial
  tooling — done, then a real prosthetist trial), evidence (3 knowledge-item and
  evidence fields, 4 golden-case benchmark), product (5 smart search,
  6 split `Case`, 7 orthotics after the trial). An Arabic-reading
  prosthetist should also check the Arabic terms.
- Possible: Arabic versions of quotes from the WHO implementation manual
  (it has an Arabic edition in the library); fixing the smaller limitations.
- Later domains need a split of `Case` into a shared core plus one section
  per domain; follow-up needs a pseudonymous link between visits; gait data
  needs its own upload path and regulatory advice (it falls outside
  non-device decision support under FDA CDS guidance, Criterion 1).

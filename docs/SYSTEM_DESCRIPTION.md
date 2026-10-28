# AI Prosthetic Lab — system description (functional and structural)

State of the working tree on 2026-10-24 (the RAG, §4.8; orthotics as drafts,
modules 1-6, §4.9, on the branch `orthotics`). Everything below runs and is tested
offline; the live run of the AI writer (Gemini's free tier since
2026-10-13, or the Claude API) is still to be measured. More history and the reasons behind each decision are in
`docs/FUTURE_WORK.md`; how to run it is in `README.md`; principles, working
rules and the roadmap are in `CLAUDE.md`; the target system the owner
designed is `docs/design/SYSTEM_DESIGN.md`. Since 2026-10-24 the folders
follow the system's parts (§5).

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
  memory and saved as one JSON file (`data/records/cases/`), so it survives a
  restart; review decisions are appended to a JSON-lines file.
- Single-user, local: `python app.py` serves http://127.0.0.1:5000. The first
  case takes ~10-30 s (model load); with the AI, each case then waits for
  the three API calls (time not yet measured live).

Commands:

```
python app.py                  # run the web app
python -m knowledge.ingest     # extract + chunk + embed all catalogued documents
python -m knowledge.evaluate   # measure retrieval quality (hit@1 / hit@5)
python -m knowledge.evaluate --orthotics  # the orthotic topic searches (data/knowledge/eval/orthotic_topics.json)
python -m knowledge.items      # knowledge items with the owner's rules applied -> data/knowledge/
python -m quality.golden_cases  # development golden cases vs the app (gap checks need the model)
python -m quality.golden_cases --rag  # also measure the RAG (cloud model: free-tier quota or money)
python -m quality.golden_cases --held-out  # the frozen held-out cases (only when the owner asks)
python -m unittest             # 555 tests, about 2 min, no model, no API
python scripts/verify_all.py   # the 0-2 checks, then the golden cases
```

---

## 3. What the user does (functional walk-through)

Every page (since 2026-10-23) has the same header, from the orthotics design
canvas: a domain switch (Prosthetics / Orthotics), the domain's modules and,
on a case's pages, a case bar (the case, "test case · fake data", "the
prosthetist decides" or "the orthotist decides"). The prosthetics map
(`/prosthetics`) lists the design's four prosthetic modules with the brief's
capabilities they cover: 1 تقييم حالات البتر, 2–3 تحليل المتطلبات الوظيفية ·
دعم اختيار المكونات, 4 دعم قرارات التصميم والتركيب, 5 المتابعة والتقييم; since
2026-10-24 each is a page of its own (§4.10), and the review page below is
the specialist review reached from module 1. The orthotics map (`/orthotics`)
does the same for its six (§4.9). Rehabilitation (§4.16) and gait analysis
(§4.17) work on a case of either domain. Four shared parts sit next to the
domains: the knowledge
layer (§4.12), reasoning and review (§4.11), search and education (§4.13,
§4.14), and the patient record (§4.15).

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
   `data/records/cases/<case_id>.json`, and the browser is sent to the review page.
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
   - each gap's mark takes a reason kept with the case; each AI summary can
     also be marked "Summary is wrong" (since 2026-10-25, log version 11);
   - **decision**, in a side panel: Approve as reviewed / Approve with edits
     (note required) / Reject the analysis, a note, and "Sign and record",
     which keeps the case, every item as shown, the marks, and the model,
     prompt and library versions;
   - the decisions already logged for this case, with mark counts.
4. **Decision** (`POST /review/<case_id>/decision`). Validated, appended as
   one JSON line to `data/records/review_log.jsonl`, and the page shows a
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

**Catalog.** `data/knowledge/sources/catalog.json` lists every document that is
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
`data/knowledge/extracted/<id>.txt` with `--- page N ---` markers (PDF-viewer page
numbers). These files are also what the quote tests check against.

**Ingestion** (`knowledge/ingest.py`): ~800-character chunks ending at
sentence ends, 150 characters of overlap, first/last page kept; each chunk
embedded with bge-m3. Store in `data/knowledge/vector_store/`: `vectors.npy`,
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

**Evaluation** (`knowledge/evaluate.py`, `data/knowledge/eval/retrieval_queries.json`):
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
from them. Hand-written, **not searched**: `prosthetics/component_guide.py` holds 19
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

### 4.5 Design and fitting (`prosthetics/fitting_guide.py`, `fitting_support.py`): the answer key

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

Since version 11 (2026-10-25, plan Part 4) a statement's
`reviewer_judgement` may be `summary_wrong`, each gap has `reviewer_reason`
(as typed, or null), and the entry has `versions` {prompt, models, library
build}; versions 6-10 added the domain, an orthotic plan and design choices,
repeats in what the quote check removed, the design canvas's keys and a
prosthetic plan (each listed in `review/decision_log.py`).

Labels and explanations are logged in English whichever language was
shown. Lines are never edited or removed. The 26 lines written while
building the prototype were moved unchanged to `data/records/review_log.test.jsonl`;
`data/records/review_log.jsonl` started empty on 2026-10-09 for the trial.

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
| Check | `reasoning/quote_check.py` | quote in the passage word for word (NFKC; whitespace, quotation marks and dashes as printed), ≥ `MIN_QUOTE_WORDS` = 5, Arabic sentence present, no repeat, ≤ 1 per gap field and ≤ `MAX_ITEMS_PER_TOPIC` = 4 per section; grade kept only if printed within 300 characters after the quote; the passage's own words are shown, the page looked up in `data/knowledge/extracted/`. Then `drop_repeats` (2026-10-23): a component or fitting quote that holds or is held by one already shown under an earlier topic is not shown again (a "repeat", not a failed check; the section says so) |
| Show | `reasoning/rag.py` → `models.py` | items become `Gap` (gaps) and `CitedStatement` (origin "rag", id `rag-<topic>-<10 hex>`, the same in every case for the same topic and quote) in the existing sections, so the page, marks, log and trial report work unchanged |
| Without the AI | | no key, offline, refusal, cut off, unreadable: the part is "unavailable" with the reason (banner); gaps fall back to §4.2; sections list the passages found |

The tests never call the API (`shared/testing.py` sets
`AI_PROSTHETIC_LAB_OFFLINE`; `shared/testing.py` FakeWriter answers from the
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
quality.golden_cases --rag`).

### 4.9 Orthotics: stroke ankle-foot orthosis (use case 03, drafts, 2026-10-22)

The same pipeline for a second domain. The fields, which are critical, the
topics, the prompt's rules and the golden cases are Claude's proposal,
marked on the pages as a draft awaiting the owner's and an orthotist's
review (FUTURE_WORK.md, "Orthotics").

| Part | Where | What it does |
|---|---|---|
| Intake | `orthotics/intake.py`, `/intake/orthotics` | `OrthoticCase`: condition (stroke), affected side, months since onset, goals, walking (status, aid, gait speed with its test, falls, deviations ticked by gait phase), exam (dorsiflexion with the knee extended and flexed, signed; plantarflexor tone grade with its scale; strengths; knee in stance; foot posture; sensation; proprioception; skin), footwear, donning, prior orthoses or FES, the orthotist's "what the orthosis must do" lines |
| Gaps | `orthotics/fields.py` `FIELDS` | 23 fields; 6 marked critical (months since onset, goals, both dorsiflexion ranges, protective sensation, skin): the page marks them, hides nothing |
| Topics | `orthotics/topics.py` | devices: AFO or FES for walking, AFO types, effects and limits, cautions; design and fitting: design, fitting and check-out, timing and training, outcome measures. Each searched in its own wording (no case words: they cost right passages) |
| Search | `knowledge/retrieval.py` | only documents with the "orthotics" domain (`ORTHOTIC_RETRIEVAL_DOMAINS`), at most 3 passages per document (`ORTHOTIC_PASSAGES_PER_DOCUMENT`); prosthetic searches unchanged |
| Ask | `orthotics/rag.py` (`PROFILE`, rag-ort-v1) | three parts (gaps, devices, design and fitting); only condition, limb, side and months since onset sent; never sets angles, materials, trim lines or wearing times, never says whether this patient should have an orthosis or FES; another condition's passage only where the source says it applies to stroke |
| Show and log | `review/templates/review/review.html`, `decision_log.py` | the case as recorded, deviations by phase, the requirements as written, devices side by side (never ranked); `LOG_VERSION` 6 adds "domain" |

Measured (2026-10-22, `python -m knowledge.evaluate --orthotics`, two fake
cases, 13 topics each): a right passage among those the AI sees in 22 of
26 searches, up from 10 at the first build. Still missed: protective
sensation and plantarflexor tone, for which the library has little.

**The six modules (2026-10-23, from the design's screens, `docs/design/03-orthotics/`; drafts).**
Every value is the orthotist's or the physiotherapist's (`orthotics/plan.py`
`OrthoticPlan` with `fit.py` and `followup.py`, saved in the case file,
version 4); the tool writes, suggests and ranks nothing. Module 1 is the
analysis page; the review page (what the sources say, the reviewer's marks)
is the review step reached from it, not a module.

| Module (brief capability) | Page | What it holds |
|---|---|---|
| Map | `/orthotics` | the reasoning chain, the six modules and the brief's capabilities they cover, the knowledge behind them, the draft hard stops, the roll-out |
| 1 Analysis (functional case analysis) | `/orthotics/<id>/analysis` | the condition module, goals by ICF level, the structured exam with how each value was measured and its status, gait phase by phase, the information needed (each with the source's own words or the AI's checked summary), the draft hard-stop checks |
| 2 Requirements (the bridge) | `/orthotics/<id>/requirements` | what the orthosis must do, in the orthotist's words, each tied to the case findings it comes from (gait deviations by phase, exam values, goals) and given a priority; provisional while a value it names is missing; conflicts between requirements, as the orthotist writes them |
| 3 Options (choosing and designing devices; linking the case to components and materials) | `/orthotics/<id>/options` | up to three option cards side by side, never ranked: device type, what each addresses (the orthotist's marks), what it costs the patient, materials and parts each tied to a requirement and so to a finding, clinic stock, checks at fitting; the FES referral to discuss with the rehabilitation team; the choice with its required reason, appended to the review log ("design_choice", `LOG_VERSION` 9, with the whole plan) |
| 4 Digital design (the digital design workflow) | `/orthotics/<id>/design`, `/fabrication-sheet` | capture, rectify, parameters, simulate, manufacture, release: status, method and notes per step; simulation results and pressure hot spots as entered from the design tool; each parameter with its basis (orthotist, practice rule, scan) and the orthotist's approval, every save a new version; send to manufacture once all are approved; the fabrication sheet to print |
| 5 Fit, tune and train | `/orthotics/<id>/fit`, `/leaflet` | check-out (starting from the chosen option's checks and the requirements), tuning log, before and after measures, the training plan as the physiotherapist set it, the patient leaflet the orthotist writes in Arabic and English (flagged until an Arabic-reading orthotist has checked the Arabic) |
| 6 Follow-up | `/orthotics/<id>/follow-up`, `/summary` | visits with their dates and status, outcome measures entered at each visit (shown as recorded, no conclusion drawn), wearing and device condition, alerts in the clinician's words that loop back to module 5, 3 or 1, the next review due, a summary for the physiotherapist to print |

**Hard stops (drafts).** The design's map lists four rules that route a case
to a doctor (an ulcer with infection or poor blood supply; a rigid device on
insensate skin without pressure relief; a fixed contracture beyond what the
design can accommodate; FES with an implanted electronic device).
`orthotics/hard_stops.py` checks them against what was recorded, never
inferring a value. Each rule's status, version, owner and approval date are
the owner's, in `data/knowledge/clinic_rules.csv` (`knowledge/clinic_rules.py`,
since 2026-10-24; the yardstick hook protects it): every page shows each
check with its rule's status. All four are drafts there (the owner,
2026-10-24: "not yet, keep as drafts"); approving one is a change to that
file only. Every line quotes the rule instead of saying in the tool's own
voice what to do. Nothing is blocked.

Next to each device type, part and step: what the source library says,
found by local search on fixed wording with topic words
(`orthotics/sources.py`), quoted as printed with its page, labelled as not
summarised and not checked to support the case. Nothing on these pages goes
to the AI. Not built from the design: AI-suggested parameters and code-made
judgements (principles 1-2; SYSTEM_DESIGN.md §11.7), the scan viewer and
pressure map (no scan data reaches the app), the "smallest real change" next
to each outcome measure and alerts from clinic rules (both wait for the
owner, SYSTEM_DESIGN.md §11.2-11.3).

### 4.10 Prosthetic module pages (plan Part 3, 2026-10-24)

The design's four prosthetic modules (`docs/design/02-prosthetics/`;
SYSTEM_DESIGN.md §6.1), built on the pieces every domain shares (§5):
`prosthetics/plan.py` (`ProstheticPlan`, kept with the case as
`CaseRecord.plan`), `prosthetics/hard_stops.py` and `prosthetics/modules.py`.
The intake's `Case` is unchanged (the golden cases are copies of it), so what
the intake form doesn't ask is kept in the plan. After the intake form a new
case still opens on the review page; the header's tabs, the review page and
the map lead to the modules.

| Module (brief capability) | Page | What it holds |
|---|---|---|
| 1 Assess (تقييم حالات البتر) | `/prosthetics/<id>/assess` | the residual limb and body as recorded (wound, signs of infection, volume, length and shape, skin, pain, sensation, joint range, strength, the other leg and foot), each with how it was measured and its status; mobility measured with named tests; the K-level the prosthetist set at intake, with what the review page's sources say about functional levels (read-only); goals by ICF level and the home and work setting; the information needed; the draft hard-stop checks; a form for the rest of the assessment |
| 2–3 Requirements & components (تحليل المتطلبات الوظيفية · دعم اختيار المكونات) | `/prosthetics/<id>/components`, `/configuration` | what the prosthesis must do, in the prosthetist's words, each tied to the findings it comes from (the intake's and module 1's values; provisional while one is missing), with a priority and the conflicts noted; for each component of the level (the answer key's categories, `component_guide.py` COMPONENTS: no new vocabulary) up to three options typed by the prosthetist, side by side in the order entered, never ranked: marks against the requirements (a Must marked "no" is flagged), costs, the review page's statements the prosthetist links (grade as printed, kind of source), the payer's funding rule and the maker's weight limit as printed next to the recorded weight (flagged when the recorded weight is above it), stock and checks at fitting; what the sources say about each component (read-only); the configuration (one option per component) and its required reason, appended to the review log ("design_choice", `LOG_VERSION` 10, with the whole plan) |
| 4 Design & fitting (دعم قرارات التصميم والتركيب) | `/prosthetics/<id>/fitting`, `/fabrication-sheet` | the six steps (shape capture, check socket, bench, static and dynamic alignment, delivery) with status and notes; the observation log (step, gait phase, what was seen, the adjustment made, what was seen after) next to what the sources say about fitting and alignment; check-socket versions (added, never changed); before a definitive prosthesis: what the case recorded, the volume rule and what the sources say about readiness (the clinic's own checklist waits for the owner, SYSTEM_DESIGN.md §11.3); the alignment record, every save a new version; the fabrication sheet to print |
| 5 Follow-up (المتابعة والتقييم) | `/prosthetics/<id>/follow-up` | visits, outcome measures entered at each visit (shown as recorded), wearing and device condition, alerts in the clinician's words that loop back to module 4, 2–3 or 1, and the loop-back links |

**Hard stops (drafts).** The design's module 1 lists three: an open wound or
infection; a changing volume ("a definitive socket waits for stable volume:
the prosthetist decides when"); a neuropathic other foot ("referral to the
diabetic foot team, if not under its care"). The owner asked on 2026-10-24
to add them as drafts: they are in `data/knowledge/clinic_rules.csv` as
drafts, and every page shows each check with its rule's status. The code
reads only the intake's wound and volume and module 1's infection, other
foot and diabetic-foot-team values, never inferring one. A matching rule
says so; a healing wound is the prosthetist's to judge; a value not
recorded is "not checked yet". Nothing is blocked.

Every value on these pages is the prosthetist's; nothing typed there is sent
to the AI. What the sources say comes from the review page's AI summaries
with their checked quotes, shown read-only and marked on the review page.
Not built from the design: the clinic's definitive-fitting checklist, alert
thresholds, follow-up intervals, outcome measures with their "smallest real
change", questionnaires validated in Arabic (all wait for the owner,
SYSTEM_DESIGN.md §11.2-11.3); per-observation causes searched from what was
typed (typed text is never searched).

### 4.11 Reasoning and review pages (plan Part 4, 2026-10-25)

The shared part "Reasoning and review" (SYSTEM_DESIGN.md §7.2;
`docs/design/07-reasoning-and-review/`) has its own entry in the header next
to the domains (`shared/domains.py` SHARED_PARTS, `review/nav.py`) and three
tabs:

| Tab | Page | What it holds |
|---|---|---|
| 1 Pathway | `/reasoning` | the six steps with what each produces and its guard; what the system never outputs; the four checks, each saying whether it is built here (quote check: built; advice check: measured only, `reasoning/sentence_checks.py`; population check: not built, the owner's values; hard stops: the owner's file, counted as draft and approved); where data goes, read from the settings: the model behind the one swap point (and whether it is switched off), the library build, each domain's cloud switch and what it sends |
| 2 Review | `/review` | the review page of the case saved last (any domain; none: the intake form) |
| 3 Quality and audit | `/quality` | the versions now (model, each domain's prompt, library build); development and held-out golden cases passing and the answer key covered, from the recorded results; the share of the AI's items the quote check removed, from the case files on this machine; the share of "summary is wrong" marks, from the review log since version 11; the audit trail, newest first (decisions, recorded runs, the library build, approved clinic rules, sign-offs; who: "not recorded (no login yet)"); the release gate: all tests, the held-out result, the Arabic texts checked, the owner's sign-off |

The quality page runs nothing. `python scripts/verify_all.py --record` (the
unit tests, the checks for prompts 0-2, the golden cases) and
`python -m quality.golden_cases ... --record` append one line each to
`data/quality/results/runs.jsonl` with the versions they ran with
(`quality/results.py`; in git, only ever added to; the yardstick hook asks
before Claude edits it). The owner adds a row to `data/quality/releases.csv`
to sign a release off and to record who checked the Arabic texts
(`quality/releases.py`; the owner's, protected the same way). The source
library's version is its build time (`knowledge/library.py`, from
`data/knowledge/vector_store/info.json`). Counts only, never a record's
content (`quality/measures.py`).

### 4.12 Knowledge layer pages (plan Part 5, 2026-10-25)

The shared part "Knowledge layer" (SYSTEM_DESIGN.md §7.1;
`docs/design/06-knowledge-layer/`; `knowledge/routes.py`, `knowledge/nav.py`)
has three tabs, all read-only (nothing on them writes a value):

| Tab | Page | What it holds |
|---|---|---|
| 1 Sources | `/knowledge` (`?kind=`, `?q=`) | every catalogued document with its kind, language, licence as recorded ("not shown" when none), the facts extraction recorded about its text (pages, references and repeated headers removed, search syntax removed, split words rejoined, pages with almost no text) and its status (searched, with its passages, or catalogued but not in the index; a note where the gap search leaves it out); the registry's documents that are link only (manual download) or downloaded but not catalogued (never quoted; regulations and datasets left out); the steps from document to search; what needs a curator: a document with no extracted text or not in the index, a manual download, and a search-quality test due when the library was built after the last recorded one (`python -m knowledge.evaluate --record`) |
| 2 Evidence | `/knowledge/evidence` (`?item=`, `?reason=`) | the 59 knowledge items, each with why it may need a curator (no rule matched, layer unassigned, population not set, a practice manual with no outcome evidence: facts about its fields); one item's quote and page, grade as printed, kind of source, evidence layer, tag and confidence with the owner's rule that set them, population and limitations (the owner's values only); the owner's rule table with the items each rule set. Read-only by the owner's answer (2026-10-25): CLAUDE.md keeps these values the owner's |
| 3 Graph and expertise | `/knowledge/graph` | the clinic rules with their status, version, owner, approval date and the source of their wording; the Arabic term sheet's state; not built yet: the design knowledge graph, a glossary with a status per clinical term, the case library and structured data (who curates them is the owner's to decide; owner's answer, 2026-10-25: "show what exists") |

Facts only, from the catalog, the sources registry, the extracted texts, the
search index, `items.json`, the owner's rule table and clinic rules
(`knowledge/library.py`). A search-quality run records itself with
`--record` (`quality/results.py`, kind "search_quality"), and the quality
page's audit trail lists it.

### 4.13 Smart search (use case 05, plan Part 6, 2026-10-25)

The shared part "Search and education" (SYSTEM_DESIGN.md §7.3;
`docs/design/08-search-and-education/Main.html`; `search/`) has two tabs:
**1 Smart search** (`/search`), below, and **2 Case-based learning** (§4.14).
Smart search:

- **Question and filters:** a question in English or Arabic; filters for
  domain, kind of source, language (both, English, Arabic) and from year. The
  search (`search/engine.py` find) uses the same local index as the cases,
  every document of the chosen domains and kinds (none ticked: all), in the
  languages the app searches, top `SEARCH_TOP_K` (8). The evidence layer the
  design filters by belongs to the knowledge items, not to passages, so it is
  not a filter.
- **Passages found:** in order of match, never of quality, each with its kind
  of source, language, title, year and page, the source's authors and licence
  where recorded, and its full text; Arabic passages are quoted in Arabic.
- **What the sources say:** AI sentences over checked quotes, from the same
  pipeline and checks as a case's (`reasoning/rag.py` run_part with the
  search's own instructions, prompt `search-v1`): never advice, options in the
  order the passages mention them, at most `SEARCH_MAX_ITEMS` (6). A question
  is typed text, so a cloud writer is never called until the owner sets
  `SEARCH_CLOUD_AI` (off: owner's decision 2026-10-25); until then the page
  says why and shows the passages. "The sources differ" notices of the design
  are not built (code can't tell when sources differ; the instructions ask for
  each side as its own item).
- **No answer:** no passage found, or the AI answered and no sentence passed
  the checks: the page says so, writes nothing in its place and offers
  "Suggest a source to the curator", listed on the knowledge sources page.
- **The search log** (`search/log.py`, `data/records/search_log.jsonl`, not in
  git, only ever added to, protected by the yardstick hook): each search (the
  question as typed, the filters, the passages found, whether the AI answered,
  the prompt and library versions), each mark on an answer (useful, not
  useful, a summary is wrong) and each suggestion; never who asked. The
  quality page shows the counts.
- **Not built yet:** pinning a passage to an open case (owner's answer,
  2026-10-25: later).

### 4.14 Case-based learning (use case 06, plan Part 7, 2026-10-25)

**2 Case-based learning** (`/learn`; `docs/design/08-search-and-education/Learning.html`;
`search/learning.py`, `search/learning_routes.py`):

- **Teaching cases** (`data/education/teaching_cases/<id>.json`, the
  educator's, protected by the yardstick hook): an invented case of a domain
  (read with `case_from_dict`, so any domain's case), and what only the
  educator sets: status (draft or approved), level (foundation, intermediate,
  advanced), the CPD minutes it is worth, and the expert panel's answers,
  each a new numbered version, never an edit (how many members answered, how
  many marked each item missing, their reasoning in their own words). The
  file is checked when read (`teaching_case_from_dict`). Three drafts by
  Claude (2026-10-25: transtibial, transfemoral, transradial), with no level,
  no CPD time and no panel answers (owner's answer: drafts, no panel answers,
  until the owner decides who sits on the panel, SYSTEM_DESIGN.md §11.9).
- **Library** (`/learn`): each case with its status, the level the educator
  set (or "not set yet") and its panel version (or "not recorded yet"); my
  learning log (cases worked, CPD hours as the learner recorded them, the
  last five, the CPD export as CSV) and the "How learning stays honest" card.
- **The five steps** (`/learn/attempt/<id>?step=`): 1 read the case (only
  what it records, numbers with their unit from the field's name); 2 what is
  missing (the domain's gap fields as ticks, plus free text); 3 the options
  you would weigh and why (free text, required before comparing); 4 compare:
  item by item, you, the panel ("n of m marked it", or not recorded yet) and
  the source (the citation the analysis found, "no source found", or
  "recorded in the case"), "you marked n of the m items the panel marked"
  (counts, never a score), your reasoning next to the panel's in their own
  words, and for each gap you did not mark that has a passage, what the
  sources say (AI sentence over the checked quote, labelled as AI); 5 reflect
  and the minutes spent, then the attempt goes to the learning log.
- **The analysis** is the case's own: `analyse_case` (local search, the AI
  with checked quotes) as for any case of its domain, run once and kept
  (`data/records/learning/analysis/`); only the case's amputation level, side
  and K-level are sent (owner's answer, 2026-10-25). An orthotic teaching
  case would follow `ORTHOTIC_CLOUD_AI`.
- **Attempts and the learning log** (`data/records/learning/`, not in git):
  an attempt in progress is one JSON file (`attempts/`); a finished one is a
  line in `log.jsonl`, only ever added to, protected by the yardstick hook,
  with the case's status, level and the panel version compared with. One log
  for this machine until roles and login come (owner's answer, 2026-10-25).
- **Not built:** grading of any kind (by design); "Ask the educator" (needs
  roles and login); a learner's identity in the log.

### 4.15 Patient record and governance (use case 07, plan Part 8, 2026-10-27)

The shared part "Patient record" (SYSTEM_DESIGN.md §7.4 and §8;
`docs/design/09-patient-record/`; `record/`), two tabs:

- **The record** (`record/people.py`): one file per person,
  `data/records/people/<code>.jsonl` (not in git, protected by the yardstick
  hook), of lines only ever added to: created, consent (item, answer,
  language shown in), case (attached at its intake), note (hand-over), request
  (a copy given, or a deletion and on whose request), deleted (written by the
  owner after a deletion). The code (`P-` and six hex digits) is made by the
  app; nothing else about the person is stored (owner's answer, 2026-10-27).
- **Attaching a case:** the intake forms of both domains have an optional
  "Person code" field (`shared/templates/ui_person_field.html`). The person
  must exist, have agreed to keep a care record, and have no deletion
  requested; the case is attached before it is analysed. A re-assessed
  orthotic case keeps its person.
- **Consent** (four items, SYSTEM_DESIGN.md §7.4): keep a care record (needed
  to attach a case); send coded fields to the cloud model; de-identified use
  for quality measures; use as the basis of a teaching case. The latest line
  per item holds. What it does (owner's answer, 2026-10-27: gate the AI):
  `reasoning/rag.py` generate sends a case attached to a person to a cloud
  writer only while that person's cloud item says agreed (else the passages
  without summaries, the reason on the page), whoever passes the writer; the
  quality page and `quality.trial_report` leave out the review-log lines of
  cases whose person has not agreed to quality use. A case with no person
  works as before. Teaching use is recorded and shown; teaching cases are
  invented, so none is made from a record. The consent wording is a draft
  awaiting the owner.
- **1 Record and follow-up** (`/record`, `/record/<code>`;
  `record/timeline.py`): the summary (cases, latest design choice, next review
  due and whether its date has passed, open alerts, consent), the timeline
  across domains, newest first and filtered by domain (each case's intake,
  signed reviews and design choices from the review log, the plan's versioned
  records each domain names in its `nav.py` RECORD_VERSIONS, follow-up visits),
  each opening its own page; the outcome measures by visit as entered, with
  how and when (who: not recorded); the follow-up schedule as recorded
  (intervals and reminders wait for a versioned clinic rule from the owner;
  nothing is sent to anyone); hand-over notes (added, never changed, never
  sent to a language model).
- **2 Consent and governance** (`/record/governance`,
  `/record/<code>/governance`): the consent items with their lines, in the
  language the person chose; where each piece of data goes, read from the
  code's own switches (`record/governance.py` cloud_uses); who may see what
  from the owner's `data/governance/roles.csv` (seven roles, each cell from a
  fixed vocabulary; drafts by Claude from common practice, awaiting the owner;
  not enforced until sign-in); the retention period and its law from
  `retention.csv` (not set); the access trail (`record/access.py`,
  `data/records/access_log.jsonl`, append-only, protected: every look and
  change, "who" null until sign-in); a copy for the person
  (`/record/<code>/copy`: the cases as recorded, timeline, measures, notes,
  every consent line, requests, the trail); a deletion request (recorded; the
  owner deletes by hand, README "Patient record").
- **Not built:** sign-in and roles enforced; reminders; follow-up intervals
  (a clinic rule); deleting from the review log (append-only, open decision).

### 4.16 Rehabilitation (SYSTEM_DESIGN.md §6.4, plan Part 9, 2026-10-27)

`rehabilitation/` works on a case of either domain (the design's example is
an orthotic stroke case with its AFO): it has no intake or case type of its
own, so it is listed in `shared/domains.py` SHARED_PARTS, first, next to the
domains. Its tabs carry the case's id; without a case they say one is needed
(the header reads its nav.py NEEDS_CASE). Its plan is kept with the case
(`shared/store.py` CaseRecord.rehab, case file version 5; older files read
with none). Every value is the team's (`rehabilitation/plan.py` RehabPlan):

- **1 Plan** (`/rehabilitation/<id>/plan`): when the goals were agreed with
  the person and how often they are reviewed; goals (G1 ..., by ICF level,
  in the words agreed, timeframe and review date, scaled −2 to +2);
  interventions (I1 ..., a kind from a draft list or "the therapist's own"
  with its name, the goals it serves, the dose as the therapist writes it);
  phases (inpatient, outpatient, community: status and when) and the team
  (role and what each does). Next to each intervention: what the library
  says about its kind (`rehabilitation/sources.py`: fixed wording and topic
  words per kind, searched in the catalog's "rehabilitation" documents for
  the case's limb, at most one passage per document, quoted as printed;
  `knowledge/retrieval.py` search_items, which orthotics/sources.py now uses
  too). The therapist's own is never searched: "No source in the library".
- **2 Progress**: the shared follow-up form (measures, sessions with their
  values, alerts looping back to the plan or the training); goal attainment
  scores (−2 to +2, a date, a note), each added, never changed. No change,
  trend or conclusion is computed; the smallest change that matters and
  clinic-rule alerts wait for the owner (SYSTEM_DESIGN.md §11.2-3).
- **3 Training with the device**: tasks (T1 ...) naming what they train, the
  device's requirements (`<domain>/plan.py` requirements, R1 ...) or the
  goals, with stage and status (not started, with help, with cues,
  independent); the home programme in Arabic and English, the therapist's
  words, flagged until an Arabic-reading therapist has checked the Arabic,
  printable (`/home-programme?lang=`); what was seen in training for the
  device specialist (the domain's nav.py SPECIALIST by default), added and
  answered, never changed, shown on the case's follow-up page in a
  "Rehabilitation" card (`shared/templates/ui_macros.html` rehab_card).
- **4 Team record**: one timeline of the team's entries (date, role, kind,
  words; added, never changed), the progress sessions and the device's
  versioned records (nav.py RECORD_VERSIONS), filtered by therapy, device or
  medical; the handover, each save a new version, written by a person and
  signed (final once signed; sending is done outside the tool; no AI draft,
  SYSTEM_DESIGN.md §11.8); next steps.
- **The patient record** (§4.15) shows the goals agreed, the attainment
  scores, the team's entries and the signed handovers on its timeline.
- **Not sent anywhere:** no rehabilitation value goes to a language model.
  **Not built:** clinic-rule alerts, the smallest change that matters, video
  clips, the AI-drafted handover, sending the handover. The vocabularies are
  Claude's draft, awaiting the owner and a therapist.

### 4.17 Gait analysis (SYSTEM_DESIGN.md §6.3, plan Part 10, 2026-10-27)

`gait/` works on a case of either domain, like rehabilitation (listed first
in SHARED_PARTS; its tabs carry the case's id). Its sessions are kept with
the case (`shared/store.py` CaseRecord.gait, case file version 6).

**Prototype decisions** (Claude, 2026-10-27, at the owner's request while no
legal or clinical advice exists; `gait/session.py`):
- The app measures nothing. The numbers come from the capture system, typed
  or imported as a CSV table (measure, left, right, both; a curve's points in
  left and right). Measuring from video or sensors is a medical-device
  function and stays with the system that does it; before clinical use, that
  system and this module need validation and regulatory advice.
- No video or sensor file reaches the app, so nothing needs blurring and only
  numbers are kept. A filmed session (phone video, lab capture) needs the
  person's consent to filming, recorded for the session.
- A session is saved once; the specialist's reviews are added to it.
- The measures are a fixed list (walking speed, cadence, step length, stance,
  swing, step width, stride time variability) and one curve (knee flexion).

**The modules:**
- **1 Capture** (`/gait/<id>/capture`): the sessions with their source,
  conditions (walkway, pace, device state, the device version logged from
  the domain's nav.py RECORD_VERSIONS, footwear, aid) and quality checks
  (frame rate, trials, trials with the whole body in frame, steps against the
  minimum-steps threshold, a hidden foot, the scale marker); the form adds
  one, its measures typed or imported (an imported value wins).
- **2 Interpret**: the gait cycle side by side (stance and swing per side);
  each measure next to its reference band and smallest real change from the
  owner's `data/knowledge/gait_references.csv` (each row with its source,
  page and words, checked word for word by `gait/tests`; empty, so "not
  set"); the knee curve as a chart; the capture system's accuracy for the
  angle is the owner's to add.
- **3 Indicators** (`gait/rules.py`): each value past a threshold of the
  owner's `data/knowledge/gait_thresholds.csv` (a difference between the
  sides in points or as a share of their mean, or a value below or above;
  five rows, all Claude's drafts for the prototype, shown as drafts), or
  outside a reference band; with the session's data facts (steps, trials,
  a hidden foot, the source). The specialist marks it reviewed or dismisses
  it with a reason. The page never names a cause, a diagnosis or a fall
  risk, and never proposes an adjustment.
- **4 Device and performance**: two sessions (and the kind of comparison:
  one device setting, with and without the device, two devices, before and
  after training); the conditions checked first, a difference flagged; the
  device version that changed, linked to the page where it was logged; each
  measure's difference, and whether it reaches the smallest real change only
  where the owner set one; "read with care"; the comparison sent to the case
  (kept with it; on the patient record's timeline).
- **Not sent anywhere**: nothing of gait analysis goes to a language model.
  **Not built**: measuring from video or sensors, clips, C3D or other lab
  file formats (only the CSV table), reference bands and smallest real
  changes (the owner's), approved thresholds.

### 4.18 The system map (docs/design/01-system-map/, plan Part 11, 2026-10-27)

`overview/` is the app's home (`/`, app.py index; before, `/` opened the
prosthetic intake). The header's brand opens it; it is not in the switch
between the parts (`shared/domains.py` HOME; CASE_PARTS names the parts that
work on a domain's case).
- **1 System map**: the clinical domains and the case parts (gait analysis,
  rehabilitation), then the shared parts, each card with its own module tabs
  as its nav.py names them, its Arabic name under the English one, and a
  link to its first page; the seven use cases of the brief and where each
  lives; the roll-out proposal (the owner sets the order); the rules every
  part keeps; and **Waiting for the owner** (`overview/routes.py`
  waiting_for_owner), counted from the owner's files as they are now: draft
  clinic rules, gait thresholds, roles and teaching cases; retention
  settings, gait reference bands and release sign-offs not set; each part's
  cloud switch (`record/governance.py` cloud_uses). Each opens the page that
  shows it.
- **2 Architecture** (`/architecture`): the six layers of SYSTEM_DESIGN.md
  §9, each with where it lives in the code; one answer end to end, the one
  step outside the machine marked, with the language model in use and each
  part's switch as the settings say now; adding a domain; who owns what; the
  owner's open questions with where each stands.

---

## 5. Structure

One package per part of the system (owner's decision, 2026-10-24): the
shared core, the shared parts (knowledge, reasoning, review, quality), then
one package per clinical domain with the same files. Each holds its code, its
pages (`templates/<part>/`) and its tests (`tests/`, 697 tests in all); the
data is grouped the same way. Shared code reaches a domain's part through
`shared/domains.py` (`part(domain, "rag")` is `<domain>/rag.py`), never by
naming the domain.

```
app.py                     Flask app: registers each part's blueprints, language route, template helpers
shared/
  case_schema.py           CaseCore (shared by every domain), Side, YesNoUnknown, PriorDevice, validation,
                           to_dict/case_from_dict (each domain's class registers itself), recorded_value()
  domains.py               the clinical domains and part(domain, module): how shared code reaches a domain
  field_guide.py           FieldInfo, missing_fields(), build_query(), FIELDS_BY_PATH (every domain's fields)
  forms.py                 every form's parsers (a refusal in the form's own words): intake values, and the
                           module pages' typed values, tables, requirements, conflicts and follow-up
  module_pages.py          the module pages' server side: find the case, draw a page, save the plan, refuse
  requirements.py          what every domain's modules share: Requirement, Priority, Mark, Conflict, Finding,
                           PlanError and the checks on requirements and conflicts
  followup.py              the follow-up records: visits, outcome measures, alerts, the next review due
  hard_stops.py            how a clinic rule stands for a case (Check, the statuses), with its row in the
                           owner's file
  fitting.py               a step's status and the gait phases
  dates.py                 a date as YYYY-MM-DD (check_date)
  config.py                paths, model, chunk and search settings, threshold, disclaimers, CODE_PACKAGES
  i18n.py                  all interface text in English and Arabic
  arabic_terms.py          Arabic term sheet: export for a prosthetist, apply corrections back
  store.py                 CaseRecord store: memory + one JSON file per case in data/records/cases/ (version 4)
  templates/               every page's look (2026-10-23): ui_style.html, ui_header.html (AI Prosthetic Lab /
                           <part>, the domain switch, numbered module tabs, EN | العربية, the case bar: each
                           domain's from its nav.py), ui_base.html (the map and module pages), ui_macros.html
                           (the screen pieces every domain reuses, SYSTEM_DESIGN.md §5), ui_forms.html (the
                           requirements, conflicts and follow-up forms)
  testing.py               what every part's tests share: the AI switched off, a fake writer and embedder,
                           RouteTestCase
  tests/
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
  clinic_rules.py          loads the owner's clinic rules: each rule's status, version, owner, approval date
  library.py               the library's build (time, passages) as its version; every document with its facts
                           and status; what needs a curator
  routes.py                GET /knowledge, /knowledge/evidence, /knowledge/graph (read-only)
  nav.py                   what the header shows for the shared part "Knowledge layer"
  templates/knowledge/     sources.html, evidence.html, graph.html
  tests/
reasoning/
  pathway.py               analyse_case(): search → AI summaries (quote-checked) → gaps, components, fitting
  models.py                Gap, Quote, GuidelineStatement, CitedStatement,
                           ComponentSection, FunctionalLevel, ComponentSupport, FittingSupport
  citations.py             cite(): a statement with its document's title, year, language and kind
  rag_topics.py            Topic, the gaps part, topics_for_case() (the domain's topics.py)
  rag.py                   the RAG every domain shares: schema, the parts at once, item check, page shapes;
                           profile_for(), components_from(), fitting_from() reach the domain's rag.py
  writer.py                the one place that calls a language model (GeminiWriter, ClaudeWriter, OfflineWriter)
  quote_check.py           a quote word for word in its passage; its page in data/knowledge/extracted/
  sentence_checks.py       flags on kept AI sentences (measurement only)
  gap_analysis.py          use case 01 without the AI (the fallback), and the gap explanations
  tests/
review/
  routes.py                GET /review/<id>, POST /review/<id>/decision; GET /reasoning, /review (the latest
                           case), /quality
  decision_log.py          validation, log entry building (version 11: versions signed), append/read
  nav.py                   what the header shows for the shared part "Reasoning and review"
  templates/review/        review.html, pathway.html, quality.html
  tests/
quality/
  golden_cases.py          runs the golden cases through analyse_case(), reports differences
  retrieval_misses.py      why expected statements miss the writer
  trial_report.py          counts of the reviewers' marks in the log, one domain at a time → data/quality/trial/report.csv
  load_trial_cases.py      loads the prepared trial cases (data/quality/trial/cases/) via analyse_case()
  results.py               the recorded results: record_run(), read_runs(), latest(), current_versions()
  releases.py              loads the owner's release sign-offs and Arabic checks (releases.csv)
  measures.py              the quality page's counts, release gate and audit trail
  tests/
search/                    search and education (§4.13, §4.14)
  engine.py                smart search: filters, find(), the AI part behind SEARCH_CLOUD_AI
  log.py                   the search log: searches, marks, suggestions (never who asked)
  routes.py                GET /search, POST /search/mark, /search/suggest
  learning.py              teaching cases (checked when read), attempts, the learning log, the CPD record
  learning_routes.py       GET /learn, the five steps of an attempt, GET /learn/log.csv
  nav.py                   what the header shows for the shared part "Search and education"
  templates/search/        search.html, _query_fields.html, learning.html, learning_step.html,
                           learning_macros.html
  tests/
record/                    patient record and governance (§4.15)
  people.py                one person's lines: consent, cases, notes, requests; cloud_consent(), counts_allowed()
  access.py                the access trail: every look and change, who not recorded until sign-in
  governance.py            the owner's roles and retention files; where data goes, from the code's switches
  timeline.py              the record page: timeline, measures, schedule, summary, from the attached cases
  routes.py                GET /record, /record/<code>, /record/governance, /record/<code>/governance, /copy;
                           POST /record/new, /note, /consent, /request
  nav.py                   what the header shows for the shared part "Patient record"
  templates/record/        people.html, person.html, governance.html, copy.html, macros.html
  tests/
rehabilitation/            rehabilitation on a case of either domain (§4.16)
  plan.py                  RehabPlan: goals, scores, interventions, phases, team, progress, tasks, home
                           programme, observations, entries, handovers, next steps; the draft vocabularies
  sources.py               fixed wording per kind of intervention, searched locally (no AI)
  routes.py                GET /rehabilitation; GET/POST /rehabilitation/<id>/plan, /progress, /training, /team;
                           GET /rehabilitation/<id>/home-programme
  nav.py                   what the header shows for rehabilitation (its tabs need a case)
  templates/rehabilitation/  map.html, plan.html, progress.html, training.html, home_programme.html, team.html,
                           macros.html
  tests/
gait/                      gait analysis on a case of either domain (§4.17)
  session.py               GaitRecord, Session (source, conditions, quality, measures, curves, reviews),
                           Comparison; the measures list; reading the capture system's CSV table
  rules.py                 the owner's thresholds and references, indicators, the two-session comparison
  routes.py                GET /gait; GET/POST /gait/<id>/capture, /indicators, /compare; GET /interpret,
                           /template.csv
  nav.py                   what the header shows for gait analysis (its tabs need a case)
  templates/gait/          map.html, capture.html, interpret.html, indicators.html, compare.html, macros.html
  tests/
overview/                  the system map, the home page (§4.18)
  routes.py                system_map() (app.py serves it at /), GET /architecture; waiting_for_owner()
  nav.py                   its two tabs; the brief's use cases and the part each lives in
  templates/overview/      map.html, architecture.html
  tests/
prosthetics/               use cases 01-02
  case.py                  Case (amputation level, side, residual limb, activity, prior devices), its enums
  fields.py                the 17 prosthetic gap fields: label, search query, topic terms (en/de/ar); query_for()
  topics.py                the prosthetic RAG topics and their search queries
  rag.py                   PROFILE: the prompt, the case facts sent, components_from(), fitting_from()
  component_guide.py       hand-written component rules + K-level statements (the answer key)
  component_support.py     picks component statements for a case; applies(); recorded_k_level()
  fitting_guide.py         hand-written design and fitting rules (the answer key)
  fitting_support.py       picks fitting statements; recorded readiness values
  intake.py                GET /prosthetics (map), GET/POST /intake: form → Case → analyse_case() → store
  plan.py                  ProstheticPlan (modules 1-5, §4.10), the case's findings for requirements
  hard_stops.py            the three draft rules, each with its status from the clinic rules
  modules.py               /prosthetics/<id>/assess, components, configuration, fitting, fabrication-sheet,
                           follow-up
  nav.py                   what the header shows for prosthetics: map, intake, module tabs, who decides
  templates/prosthetics/   intake_form.html, map.html, case_bar.html, macros.html, assess.html,
                           components.html, fitting.html, fabrication_sheet.html, follow_up.html
  tests/
orthotics/                 use case 03 (drafts)
  case.py, fields.py,      OrthoticCase and its 23 gap fields, topics, rag.py (PROFILE),
  topics.py, rag.py,       intake.py (/intake/orthotics)
  intake.py
  plan.py, fit.py,         OrthoticPlan (modules 2-6), sources.py (passages per device, part, step),
  sources.py, nav.py,      hard_stops.py (the four rules, each with its status from the clinic rules),
  hard_stops.py, modules.py  nav.py (what the header shows), modules.py (/orthotics: map and modules 1-6)
  templates/orthotics/
  tests/
scripts/                   verify_prompts_0_2.py (checks for prompts 0-2), verify_all.py (that + golden cases)
docs/                      this file, FUTURE_WORK.md, the independent blueprint, design/ (the target system)
data/
  knowledge/               evidence_rules.csv, clinic_rules.csv, gait_thresholds.csv and gait_references.csv
                           (the owner's), items.json,
                           items_to_curate.csv (in git; regenerate after changing a guide or the rule table)
    sources/               catalog.json, 00_registry/sources_manifest.csv (in git); PDFs (local only)
    extracted/             cleaned text per document (generated)
    vector_store/          vectors.npy, chunks.json, info.json (generated)
    eval/                  retrieval_queries.json, orthotic_topics.json
  quality/
    golden_cases/          golden-NN.json and golden-ort-NN.json (development)
    golden_cases_held_out/ golden-NN.json (held out, frozen by golden_cases_held_out.json)
    baseline/              measurement records, by date
    trial/                 arabic_terms.csv, cases/trial-NN.json (in git); report.csv (local only)
    results/runs.jsonl     the recorded results (in git; only ever added to)
    releases.csv           the owner's release sign-offs and Arabic checks
  education/
    teaching_cases/        TC-NN.json: the educator's invented teaching cases (three drafts so far)
  governance/              roles.csv, retention.csv: the owner's (in git; drafts so far)
  records/
    cases/                 one JSON file per case (local only)
    search_log.jsonl       searches, marks and suggestions (local only)
    learning/              attempts/, log.jsonl (the learning log), analysis/ (local only)
    people/                <code>.jsonl: one person's record, lines only ever added (local only)
    access_log.jsonl       the access trail (local only)
    review_log.jsonl       decisions (local only); review_log.test.jsonl: earlier test lines
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

ProstheticPlan (prosthetics/plan.py; CaseRecord.plan; §4.10)
  assessment: Assessment(measured_how {value path: how}, joint_range, strength, infection,
      other_foot_neuropathy, diabetic_foot_team (yes/no/unknown), mobility: [MobilityMeasure(name, value, how)],
      mobility_note, goal_participation, goal_body_function, home_work_setting)
  requirements, conflicts (shared/requirements.py)
  options {component key: [ComponentOption(id A-C, name, marks, mark_notes, costs, checks, sources (statement
      ids), funding, weight_limit_kg, stock, notes)]}, configuration {component key: option id}, choice_reason
  steps {FittingStep: StepRecord(status, notes)}, observations: [Observation(step, seen, phase, adjustment,
      seen_after)], socket_versions, alignment_versions: [AlignmentVersion(number, values, note, saved_at, by)]
  follow_up: FollowUp (shared/followup.py)

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
POST /intake                            (prosthetics/intake.py; /intake/orthotics: orthotics/intake.py)
  → _case_from_form (validation; errors → 400 + form)
  → analyse_case(case)                  reasoning/pathway.py:
  → retrieve_relevant_chunks(case)      fields and RAG topics (no vector store: a warning, no passages)
  → generate(case, chunks, writer)      three AI calls at once; each item quote-checked
  → gaps_from(), components_from(), fitting_from()   (without the AI: analyze_gaps, passages listed)
  → store.save(CaseRecord) → 302 /review/<case_id>

POST /review/<id>/decision
  → record_decision (validate → build entry → append one line) → 302 back with ?saved=1

POST /prosthetics/<id>/<module>, /orthotics/<id>/<module>   (each domain's modules.py)
  → shared/forms.py reads the form (errors → 400 + the form as sent)
  → the domain's plan checks and changes → store.save(CaseRecord) → 302 back with ?saved=1
  → a configuration or option chosen: record_design_choice() appends one line to the review log
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

- **697 unit tests** (standard `unittest`, fake embedder, fake AI writer, no
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
- **Quote test** (`prosthetics/tests/test_component_guide.py`): every quote and context
  quote of all 59 statements is checked word for word on its page of
  `data/knowledge/extracted/`; list items must follow their heading in order; each
  VA/DoD grade must be the one printed after the recommendation. Mutation
  checks (a changed word, a wrong page, swapped list items, a wrong grade)
  were all caught.
- **Retrieval evaluation** (§4.1).
- **Golden cases** (`python -m quality.golden_cases`, `data/quality/golden_cases/`):
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
  Since 2026-10-13, 5 of the 13 are held out (`data/quality/golden_cases_held_out/`:
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
  unsummarised and unchecked; their vocabularies are drafts; modules 5-6
  (fit and follow-up) are drafts too.
- The prosthetic module pages (§4.10, 2026-10-24) have not been used by a
  prosthetist yet; their three hard stops are drafts awaiting the owner; the
  fitting steps and module 1's extra values follow the design and are
  Claude's reading of it; the clinic's checklist, alert thresholds,
  follow-up intervals and outcome measures wait for the owner.
- Reasoning and review (§4.11, 2026-10-25): who did what is not recorded (no
  login yet; roles come with the patient record); the quality page shows
  only what was recorded, so it is empty until `verify_all.py --record` and
  the golden-case runs are recorded; the population check is not built and
  the advice check is a measurement, not shown on the pages; no held-out run
  and no sign-off yet.
- Knowledge layer (§4.12, 2026-10-25): read-only; a curator cannot set an
  item's evidence fields from the page (the owner's answer); the design
  knowledge graph, a glossary with statuses, the case library and structured
  data are not built; "pages with almost no text" counts figures and
  dividers as well as scans; no search-quality run recorded yet.
- Smart search (§4.13, 2026-10-25): no AI summary until the owner sets
  `SEARCH_CLOUD_AI`; a free question can be matched by a guideline's
  search-strategy appendix page (seen: the upper-limb VA/DoD guideline, whose
  literature-search syntax extraction did not remove); no "sources differ"
  notice; pinning to a case not built.
- Case-based learning (§4.14, 2026-10-25): the three teaching cases are
  Claude's drafts, with no level, CPD time or panel answers until the
  educator sets them, so the compare step has no panel to compare with yet;
  one learning log for the machine, with no learner's name; no "Ask the
  educator".
- Patient record (§4.15, 2026-10-27): no sign-in, so the roles table is
  shown, not enforced, and the access trail cannot say who; the roles,
  retention period, law and consent wording await the owner; a deletion is
  done by hand, and the review log's lines for the person's cases stay
  (append-only); no reminders or follow-up intervals.
- Rehabilitation (§4.16, 2026-10-27): the intervention list and its search
  wording, the roles and task statuses are Claude's drafts; the smallest
  change that matters and clinic-rule alerts wait for the owner; no video
  clips; the handover is typed and signed in the tool but sent outside it.
- Gait analysis (§4.17, 2026-10-27): measures nothing itself (only numbers
  from the capture system, as a CSV table or typed); the thresholds are
  Claude's drafts, the reference bands and smallest real changes not set; no
  clips; no lab file formats beyond the table; needs validation and
  regulatory advice before clinical use.

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

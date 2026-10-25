# Future Work / Open Decisions

Scratchpad so nothing gets lost between build steps. Update this file as
items are resolved instead of re-deriving them from scratch.

## Step 3 decisions (decided 2026-10-05)

- **Languages: Arabic and English, plus German** if it doesn't reduce
  accuracy. German costs nothing at the model level (every candidate
  multilingual model covers it). Measured 2026-10-06 (see Step 3
  progress): German search works (5/5 first place) and doesn't change
  English (10/10), but costs 1 of 8 Arabic queries.
  **Decided 2026-10-06: German is not searched** (`RETRIEVAL_LANGUAGES` =
  `("en", "ar")`). On four test cases (transtibial, transfemoral,
  transradial, transhumeral; only required fields, 64 gaps) the gap lists
  cite 54 gaps with or without German, and also when German is searched
  only if English/Arabic find nothing. German only swapped two English
  quotes (functional goals, upper limb: AWMF p. 15 at 0.68 instead of
  VA/DoD p. 8 at 0.66). The German documents stay in the catalog and the
  index, and `knowledge.evaluate` still measures them, so adding `"de"`
  back needs no re-ingest.
- **Embedding model: `BAAI/bge-m3`** (~2.3 GB, 8192-token input, no
  query/passage prefixes, best cross-language results of the candidates).
  Replaces `all-MiniLM-L6-v2` (English-only). Fallback if too slow/heavy:
  `intfloat/multilingual-e5-base` (needs `"query: "` / `"passage: "`
  prefixes). Ruled out: `paraphrase-multilingual-MiniLM-L12-v2`, which reads
  only 128 tokens and would silently cut off most of an 800-char chunk.
  Store the model name with the ingested data and refuse to search if it
  doesn't match `EMBEDDING_MODEL_NAME`, so a model change forces a re-ingest.
- **Vector store: plain numpy, no vector database.** Vectors in one `.npy`
  file, chunks + metadata in one `.json` file, same order. A few thousand
  chunks search in milliseconds; numpy is already installed with torch, so
  no new dependency and no Python 3.14 risk. Chroma stays the upgrade path
  if the library grows or needs complex filtering; only `knowledge/` changes.
- **PDF parsing: `pypdf`** (approved). Ingestion must also accept `.txt`,
  apply Unicode NFKC normalization (fixes Arabic presentation-form letters),
  warn on pages with no text (scanned PDFs; OCR is out of scope), and warn
  when Arabic extraction looks broken. `.txt` is the reliable route for
  Arabic sources.
- **Python 3.14: no new risk** with numpy + pypdf. `requirements.txt`
  lists `pypdf`, `numpy` and `sentence-transformers` (6.0.0 and torch
  2.9.1+cu130 work on 3.14).
- **Chunk metadata**, per chunk: stable `chunk_id` built from the
  catalog's permanent document `id` (e.g.
  `lower_limb_amputation_va_dod_cpg_2024-0042`), `source` (filename),
  citation fields (title, authors, year, publisher, DOI/URL), `page`
  (PDFs), `source_type` (the brief's six: scientific_reference, protocol,
  professional_knowledge, applied_case, structured_data,
  specialist_expertise), `domains` (a list: a document can cover several
  of prosthetics, orthotics, gait, rehabilitation), `language`
  (`ar` / `en` / `de`). All of it comes from the hand-written
  `data/sources/catalog.json` (fields explained in
  `data/sources/README.md`); files not in the catalog are skipped with a
  warning.
- **Retrieval shape: one search per missing field.** For each entry in
  `Case.unrecorded_fields()`, build a query from the field and the case
  (e.g. "residual limb volume stability, transtibial, prosthetic
  evaluation") and return chunks grouped by field. This changes
  `retrieve_relevant_chunks()`'s return type and step 4's input.
- **Evaluation set:** about 10 test queries per language, each with the
  chunk that should come back; a script reports how often it is in the
  top 5. Used to check German's effect and to compare models.

## Findings from the first 10 documents (checked 2026-10-05)

- **Use `pypdf` 6.x, not the old `PyPDF2`.** PyPDF2 (also installed on
  this machine) turned two PLOS ONE files into nonsense
  (`ZK[KF ZIN FZ\OIS K` instead of `RESEARCH ARTICLE`); pypdf 6.19.0
  reads all 10 correctly.
- **The first 10 were English, text-based PDFs** (no scanned pages).
  Arabic and German arrived with the 2026-10-05 clean-up (see Step 3
  progress): the WHO P&O standards in English and Arabic (same content,
  ideal for an English-query / Arabic-passage test; the WHO Arabic terms
  are البِدلات for prostheses and المقاويم for orthoses, not
  الأطراف الاصطناعية, so include both in Arabic test queries) and the
  German AWMF upper-limb guideline 187-061. Still not collected: the
  lower-limb AWMF guideline 033-044 (2019; check the register for an
  update), the German counterpart of the VA/DoD lower-limb guideline:
  https://register.awmf.org/assets/guidelines/033-044l_S2k_Rehabilitation_Majoramputation-untere_Extremitaet_2019-09_01.pdf
- **Most useful sources for use case 01** (mentions of the 12 intake
  topics in `data/extracted/`, a topic counted as covered at 3+
  mentions): VA/DoD guideline 10 of 12, CMS consensus 6 of 12, phantom
  limb pain review 2, socket shape-capture review 2, both 3D-printing
  reviews 0. Most evaluation-set queries should therefore expect chunks
  from the VA/DoD and CMS documents. The library needs more sources on
  what to assess before prosthetic fitting; the 3D-printing and socket
  reviews rarely answer "what information is missing".
- **4 of 10 are orthotics, not amputation** (scoliosis bracing, AFO
  after stroke, orthoses in cerebral palsy, AFO care-quality
  instruments). They stay in the catalog without `prosthetics` in
  `domains`. The rule is `shared/config.py:RETRIEVAL_DOMAINS`
  (`("prosthetics",)`); step 3's search must filter on it and needs a
  test proving an orthotics-only document is never returned.
- **No converting to .txt by hand.** Extraction reads each PDF once;
  searches use only the stored vectors. Keep the PDFs as the originals
  the specialist checks (with page numbers).

## Step 3 progress

- **Done 2026-10-05:** files renamed to `topic_year.pdf`, moved under
  `data/sources/`, catalogued in `data/sources/catalog.json`; source
  files (`.pdf`, `.txt`) and generated data (`data/vector_store/`,
  `data/extracted/`) are in `.gitignore`. `shared/config.py` has
  `SOURCES_DIR`, `CATALOG_PATH`, `EXTRACTED_DIR` (replacing
  `PROTOCOLS_DIR`) and `RETRIEVAL_DOMAINS`.
- **Done 2026-10-05: text extraction.** `knowledge/catalog.py` loads and
  checks the catalog. `knowledge/extract.py` (`python -m
  knowledge.extract`) writes `data/extracted/<id>.txt` with `--- page N
  ---` markers: NFKC, soft hyphens, table-of-contents dots, words split
  across lines, reference lists removed (all 10 cuts checked by hand:
  only references were removed), warnings for scanned pages and broken
  Arabic. All 10 documents take about 10 seconds. Tests:
  `tests/test_catalog.py`, `tests/test_extract.py`.
- **Done 2026-10-05: one source folder.** The Claude Desktop collection
  (`data/source/`) was merged into `data/sources/`, keeping its layout
  (`00_registry` … `05_datasets`) and its `<manifest id>_…` file names;
  `00_registry/sources_manifest.csv` records acquisition, `catalog.json`
  ingestion (18 documents: 15 English, 2 Arabic, 1 German). Six exact
  duplicates were removed; for four papers the publisher PDF replaced the
  PMC page printed to PDF (date header on every page, 2-3x the pages,
  page numbers that don't match the article). Removed files went to the
  Windows Recycle Bin. `.gitignore` now whitelists only the catalog,
  manifest, download script, READMEs and report under `data/sources/`.
  `SOURCES_NOT_INGESTED` in `shared/config.py` names the folders
  extraction skips. Reference removal now handles German ("11.
  Literatur") and Arabic (المراجع) headings, keeps an appendix that
  follows the list, and finds where a list starts when "REFERENCES" is
  repeated as a page header (WHO).
- **Done 2026-10-06: page headers, footers and search syntax removed.**
  `extract.drop_repeated_lines()` drops lines found on 40%+ of pages
  (digits ignored, so page numbers count as repeated).
  `extract.drop_search_syntax()` drops lines of literature-search syntax
  (3+ operators like `OR`, `/exp`, `[Mesh]`): 1,133 lines in the
  upper-limb VA/DoD guideline, 398 in the lower-limb one. Left in, they
  name every topic and won citations (seen in the end-to-end check).
- **Done 2026-10-06: ingestion and search.** `python -m knowledge.ingest`
  extracts, cuts each document into ~800-character chunks at sentence
  ends (150 characters of overlap, page range kept), embeds them and
  writes `data/vector_store/` (`vectors.npy`, `chunks.json`, `info.json`).
  `knowledge/retrieval.py` refuses a store built with another model,
  searches once per missing field, only in `RETRIEVAL_DOMAINS` documents,
  and leaves out documents only about the other limb (catalog field
  `limbs`). Checked end to end on all 18 documents with the small English
  model already on disk: 3,197 chunks, median 716 characters, 57 s.
- **Done 2026-10-06: evaluation.** `data/eval/retrieval_queries.json` has
  10 English, 8 Arabic, 5 German, 4 cross-language and 3 off-topic
  queries; answer pages were found by reading the text, not by searching.
  `python -m knowledge.evaluate` reports hit@1/hit@5 per group, with and
  without the German documents, and the scores of correct vs off-topic
  results. Baseline with the English-only `all-MiniLM-L6-v2`: English
  10/10 in the top 5, Arabic 0/8, cross-language 0/4, off-topic scores up
  to 0.60. That confirms the switch to bge-m3.
- **Done 2026-10-06: bge-m3 index, evaluation and threshold.**
  - **Download:** the model came in through
    `%USERPROFILE%\.cache\huggingface\bge-m3-download\download_bge_m3.py`:
    curl over 6 parallel connections, SHA-256 checked. Hugging Face's own
    downloader kept being reset on this connection.
  - **Index:** `python -m knowledge.ingest` took 126 s on the GPU for
    3,197 chunks of 1,024 numbers each. The model loads from the local
    cache first (`local_files_only`), so the app works offline.
  - **Evaluation** (`python -m knowledge.evaluate`), as hit@5, top-1:

    | queries | all documents | without German |
    |---|---|---|
    | English (10) | 10/10, 5 first | 10/10 |
    | Arabic (8) | 6/8, 3 first | 7/8 |
    | German (5) | 5/5, 5 first | - |
    | cross-language (4) | 4/4, 3 first | 3/3 |

    Missed with German: ar-04 (microprocessor knee, missed either way)
    and ar-05 (peer support; a German AWMF passage ranked first at 0.62).
  - **Threshold:** correct answers scored 0.58 or more (median 0.71);
    off-topic text at most 0.44. `MIN_RELEVANCE_SCORE` = 0.50.
  - **Gap check:** on four test cases (transtibial, transfemoral,
    transradial, transhumeral) every field query's best match scored
    0.60-0.79, so the topic check decides most citations. The final
    lists cite 9-15 sources per case.
  - **Real server:** `python app.py`; the first case takes 10-30 s (model
    load), later cases 0.1 s.
- **Run check 2026-10-06** (`python app.py`, cases submitted over HTTP,
  pages screenshotted with headless Edge): 20 requests, no errors.
  - Below-knee case: 12 gaps, 10 with a source.
  - Forearm case: 15 gaps, 12 with a source, no lower-limb-only document
    cited, one German quote.
  - Invalid age: refused with 400.
  - Unknown case: 404.
  - Approve: confirmation banner shown.

  Found:
  1. ~~A case with every form field filled still shows "Prior prosthesis
     use", because the form has no prior-devices input.~~ Fixed
     2026-10-06 (see Step 5).
  2. ~~Decisions are not saved (step 5).~~ Fixed 2026-10-06 (see Step 5).
  3. For upper-limb cases, comorbidities and cause of amputation can
     quote a lower-limb sentence from the phantom-pain review, whose
     `limbs` covers both.
  4. Some quotes are table residue ("Weak for Reviewed, Amended…",
     "AM-ULA + + N/A") or start with footnote numbers ("3 Poor fit can
     cause…").

## Step 4 (reasoning) decisions and progress

- **Rules, not a language model** (decided 2026-10-06; **replaced
  2026-10-11** by the owner's decision for a RAG, see "RAG: retrieval plus
  Claude with checked quotes" below). An LLM API call
  is a cloud service, out of scope for v1, and language models often cite
  sources that don't support their statements: 50-90% of responses not
  fully supported in Wu et al. 2025
  (`04_ai_safety_regulation/A01_...`).
- **Done 2026-10-06: `reasoning/gap_analysis.py`.** One gap per field that
  is empty or recorded as unknown (`Case.unknown_fields()`, new), in
  `shared/field_guide.py` order; free-text note fields are never gaps.
  A gap cites the best retrieved passage that scores at least
  `MIN_RELEVANCE_SCORE` *and* mentions the field's topic (per-language
  topic words), and quotes those sentences (long table rows are cut to
  the words around the match). No passing passage: the gap says no
  source was found. `why_needed` quotes the source, never our own claim.
  Every `source_protocol_reference` is a retrieved chunk (tested).
- **Done 2026-10-06: review page** shows each gap with its quote (Arabic
  right-to-left), citation with page, chunk id, similarity, the full
  passage, and the other passages retrieved; plus a banner when the
  source library wasn't searched.
- **Design rules taken from `04_ai_safety_regulation`:** FDA CDS guidance
  (2026) Criterion 4, that the clinician can independently review the
  basis, is why each gap shows its passage and page. Its automation-bias
  section (errors of omission) is why `DISCLAIMER` now says the list may
  be incomplete.
- **Known weaknesses (seen in the end-to-end check):**
  - A title/author block can be cited, e.g. the phantom-pain review's
    first chunk.
  - Table rows make poor quotes.
  - The topic check only proves a passage *mentions* the topic, not that
    it says the information is needed; the specialist judges that.
  - Chunk ids change if extraction or chunk settings change, so the
    review log stores the quoted text, citation and full passage, not
    only the chunk id (done in step 5).
  - Methods tables can be cited (e.g. "Timing KQ … Post-operative" for
    time since amputation), and the German guideline has some
    letter-spaced text ("d i e d a n n") from its PDF.
  - No source in the library is about prior prosthesis use, so that gap
    never has a citation. Add one (e.g. a prosthetic history/intake
    guide) if it should.

## Step 5 (documented outcome) and intake completion (done 2026-10-06)

- **Review log: `review/decision_log.py`.** Every decision appends one
  JSON line to `data/review_log.jsonl` (in `.gitignore`; written with
  `ensure_ascii=False`, so Arabic stays readable). Each line stands on its
  own: `log_version`, `logged_at` (UTC), `case_id`, `decision`, `note`,
  every gap as shown (`field`, `label`, `status`, `why_needed`,
  `reviewer_judgement`, and for a cited gap `source` with chunk id,
  citation, title, year, pages, file, language, score, the quote and the
  full passage), `knowledge_warning`, the search `settings` (model,
  revision, threshold, languages, domains, top k), and the case
  (`Case.to_dict()`). Lines are only ever added.
- **Per-gap judgement:** the review page asks, for each gap, "Not marked",
  "Needed" or "Not needed for this case". This is the specialist feedback
  the brief's "specialist expertise" source can later learn from.
- **Validation:** decision must be approve, edit or reject; "edit" needs a
  note; judgements must be needed / not_needed for one of the case's own
  gaps. A refused submission returns 400, logs nothing, and keeps the
  reviewer's choices and note on the page.
- The review page lists the decisions logged for the case, read back from
  the file, and the banner shows the decision just saved.
- **Prior-devices input:** the intake form has a "No prior prosthesis"
  checkbox and three device rows (description, years used, currently
  using, issues). Nothing filled -> `None` (a gap); box ticked -> `[]`
  (no gap); rows -> `PriorDevice` list. Details without a description,
  the box ticked together with a device, negative years, or an unknown
  yes/no value are refused. `PriorDevice` itself now rejects an empty
  description and negative or non-finite years. Every field the gap
  analysis checks now has a form input.
- **Run check** (`python app.py`, 16 HTTP requests, no errors):
  - Below-knee case with age and wound status filled: 15 gaps, 13 with a
    source, all English; the first case took 8.5 s (model load).
  - Same level with every field filled: 0 gaps.
  - Forearm case with "No prior prosthesis" ticked: 14 gaps, 12 with a
    source, no prior-devices gap, no German quote.
  - Device details without a description, or the box ticked together
    with a device: refused with 400 and a message.
  - Decisions: approve with 2 needed / 1 not needed, and an edit with an
    Arabic note, logged; edit without a note and "maybe" refused with
    400; decision for an unknown case: 404. The log had 3 lines; a
    15-gap entry is about 26 KB (mostly the full passages).
- **Full run check 2026-10-08** (unit tests, `knowledge.evaluate`, live
  server, 59 HTTP requests, 1,039 automated checks):
  - Evaluation unchanged; the app's setting (no German) gives English
    10/10, Arabic 7/8, cross-language 3/3.
  - All 12 amputation levels with only level and side: lower limb 17 gaps
    (14-15 with a source), upper limb 15 gaps (12 with a source). First
    case 10.9 s (model load), the rest about 0.1 s.
  - Every field filled: 0 gaps. "No prior prosthesis": no prior-devices
    gap. All "unknown" answers listed as "recorded as unknown".
  - 14 decisions logged and audited from the log itself: 174 citations,
    all at or above 0.50, all English (no Arabic: see Open decisions),
    all from prosthetics documents for the right limb. All 196 quote
    pieces appear word for word in their passage. Every saved case loads
    back with `Case.from_dict`.
  - **Bug found and fixed:** a form without `side` gave a 500 crash page
    under `python app.py`. The route used `form["side"]`, and Flask's
    debug mode turns the missing-key error into a crash instead of a 400
    (the unit tests run without debug mode, so they passed). Required
    fields are now checked by `intake/routes.py:_required()` ("side is
    required", 400); the test covers both fields.
  - The 14 run-check decisions carry the note "automated run check
    2026-10-08"; `data/review_log.jsonl` now has 17 test lines.

## Arabic UI (done 2026-10-08)

Chosen instead of Arabic citations, which need sources the library doesn't
have (see Open decisions).

- **`shared/i18n.py`** holds every interface text in English and Arabic:
  headings, labels, drop-down choices, buttons, messages, the disclaimer,
  the 17 gap field names and the gap explanations. English is the default
  and its pages show the same text as before. `GET /language/<code>` sets a
  `lang` cookie and goes back to the page (`next`, only a path of this app:
  `//host`, `/\host` and full URLs go to `/`).
- **Not translated:** quotes and citations (the source's own words), what
  the user typed, the "source library was not searched" detail (it names a
  command), and Python's own wording for impossible form values.
- **Right to left:** `<html dir="rtl">`, CSS with start/end instead of
  left/right, user text and English citations in `<bdi>` or their own
  `dir="auto"` line, and values inside Arabic sentences wrapped in Unicode
  isolates (U+2068/U+2069) so the browser doesn't reorder them.
- **One explanation function:** `reasoning/gap_analysis.explain_gap(gap,
  lang)`; `Gap.why_needed` is its English output, word for word as before.
  The Arabic sentence leaves the citation out ("المصدر المذكور أدناه"): in
  the first screenshot a 120-character English title wrapped inside the
  Arabic sentence was hard to read, and the citation is on its own line
  below the quote anyway.
- **Review log version 2:** adds `ui_language`. Labels and explanations are
  still logged in English, so entries compare across languages.
- The comorbidities box also accepts لا يوجد / لا شيء for "none" (the
  Arabic label says to type لا يوجد).
- **Tests:** 162 (28 new). `tests/test_i18n.py` fails if any text, gap
  field or choice lacks Arabic, if a translation uses a placeholder the
  English doesn't, or if a key used in a template or the code is missing.
  Checked by deleting one label, one text and breaking one placeholder: all
  three caught, each naming the key.
- **Run check** (`python app.py`, real model and index, 65 checks, run
  twice): the four test cases in Arabic list 17/17/15/15 gaps with
  15/15/12/12 sources, the same gaps the English pages cite; no English
  text left on the Arabic pages; Arabic errors (device details only, side
  missing, edit without a note) refused with 400; decisions logged with
  `ui_language` "ar" and "en". Server log: 73 requests, no 500s. Screenshots
  (headless Edge) checked by eye: right-to-left layout of both pages,
  buttons and logged decisions.
- **Needs checking by an Arabic-reading prosthetist:** the clinical terms
  in `shared/i18n.py` (amputation levels, e.g. بتر تحت الركبة for
  transtibial; K-level wording; الطرف المتبقي for residual limb). The WHO
  Arabic editions use البدلات for prostheses; the interface follows the
  brief's الأطراف الاصطناعية.
- The four run-check decisions carry the note "automated run check
  2026-10-08 (Arabic UI)"; `data/review_log.jsonl` now has 21 test lines.

## Component selection support and functional level (done 2026-10-08)

The brief's prosthetics domain: "evaluate the amputation, choose the
components, design and fit". Chosen order (2026-10-08): component support
with the functional level it depends on (use case 02, pathway step 04), then
design and fitting. This ends v1's "missing information only" rule; the
disclaimer, intake banner and out-of-scope list were revised.

- **Statements, not advice:** `reasoning/component_guide.py` holds 13 rules,
  each one statement copied word for word with its page and the source's
  own grade, plus the CMS K0-K4 descriptions and two cautions: 20
  statements, 31 quotes with their context. Sources:
  VA/DoD lower limb 2024 recommendations 15-19 (pp. 55-58), VA/DoD upper
  limb 2022 recommendations 7-8 (pp. 31-32), CMS Lower Limb Prosthetic
  Workgroup 2017 (pp. 4-12). Hand-written, not searched: a wrong component
  statement does more harm than a wrong gap, and each rule can be checked
  on its page.
- **Who a rule applies to** comes only from the source's wording: levels
  (knee rules for knee disarticulation, transfemoral, hip
  disarticulation; upper-limb rec 7 "through or proximal to the wrist"),
  "unilateral", "at the K2 level" (shown only when K2 is recorded), and
  "prosthetic/community ambulators" (not shown for K0, which CMS
  describes as no ability or potential to ambulate). Where sources differ
  (microprocessor knee at K2: VA/DoD "Weak for" vs CMS "may benefit"),
  both are shown. Nothing is ranked.
- **Shown with each statement:** the guideline's scope, confidence and
  caveats from the same document, e.g. VA/DoD's "very low" confidence and
  that household walkers are "rarely included in the evidence".
- **Functional level (the brief's "functional requirements analysis"):**
  the CMS description of the recorded K-level, the CMS cautions ("should
  not be considered a functional classification", research "has failed to
  connect" medical condition to K-level), all five descriptions for
  reference, and the recorded activity and goals. Upper limb: no K-level
  (CMS: K modifiers describe a lower-limb prosthesis).
- **Review and log:** each statement can be marked Relevant / Not relevant
  for this case; review log version 3 adds `components` (functional level,
  notes, every statement shown with quote, context, citation, grade and
  mark). A mark for a statement not shown is refused.
- **Tests:** 194 (32 new). `tests/test_component_guide.py` checks every
  quote is on its page of `data/extracted/` (skipped if not generated) and
  that each VA/DoD grade is the one printed after the recommendation.
  Checked by moving one quote to the wrong page, changing one word and
  swapping one grade: all three caught.
- **Run check** (`python app.py`, real model, 272 checks, run twice): 11
  cases (transtibial K3: 6 statements; transfemoral K2: 11, K0: 3, no
  K-level: 9; knee disarticulation K4: 7; hip disarticulation K1: 7;
  partial foot unknown: 6; transradial: 2; partial hand: 1; bilateral
  transradial: 1; transhumeral: 2). Every statement on the page word for
  word with its citation; Arabic page in Arabic with quotes in English;
  marks logged; unknown statement refused. Screenshots checked by eye;
  context quotes now show "Same source, p. N" instead of repeating the
  title (the first screenshot repeated a 120-character title three times).
  The server's request log was lost when it was stopped, so no 500 check
  from it this time; the check script verified every response's status.
- **What the library can't support yet (needs sources):** upper-limb
  terminal devices and partial-hand prostheses, and any Arabic source.
  (Transtibial socket design and alignment were added from the ICRC manual
  in stage C, see below.) CMS 2017 is US Medicare policy ("coverage"); its
  statements are shown as written, with the year.
- **Review log:** 24 lines, all test cases: the 21 earlier, two "automated
  run check 2026-10-08 (components)", and one at 11:29 UTC (approve, no
  note) not made by a check script.
- Committed 2026-10-09 as `a7ff631` (17 files) and `fdc0078` (the 33
  manifest rows), with the commit email corrected for this repository
  (`ashraf.eee2003@gmail.com`; older commits keep the typo). Not pushed.

## Design and fitting (stage C, done 2026-10-09)

The last part of the brief's prosthetics domain ("design and fit"), built
like the component support: hand-written statements quoted word for word,
applicability only from the source's wording, a quote test.

- **New source: the ICRC manual** *Prosthetic Gait Analysis for
  Physiotherapists* (2014, manifest K01) is catalogued as
  `prosthetic_gait_analysis_icrc_manual_2014` (lower limb,
  `professional_knowledge`) and ingested: 19 documents, 3,468 chunks. It
  is the only source in the library with alignment text (definition,
  steps, and which alignment error may cause which gait deviation, for TT
  and TF) and transtibial socket and suspension descriptions. It is a
  training manual for ICRC programmes (polypropylene technology), not a
  guideline: no grades, and the page labels every statement with its kind
  of source. The WHO PIR modules (G15/G16) have almost nothing on fitting
  or alignment (one "alignment" mention, about fractures) and were not
  added. K02 (ICRC gait-training exercises) is mostly illustrations.
- **The ICRC manual is quoted, not searched** (`RETRIEVAL_EXCLUDED_DOCUMENTS`
  in `shared/config.py`). Measured before deciding, on all 12 levels with
  only level and side: searched, it changed 28 of 102 lower-limb gap
  citations. Most new quotes were worse: page-header and table residue
  ("Replacing the weight loss of the missing limb 214 Weight % (average)
  …", "Femur … PhysiotheraPists12 The minimum length for a tibial stump is
  5 cm." for a partial-foot case), a footnote fragment for skin, and
  comorbidities quoting the manual instead of the VA/DoD guideline on 6
  levels. It also pushed one Arabic evaluation query (ar-05, peer support)
  out of the top 5 without German (7/8 -> 6/8). Left out: gap lists are
  identical to before (0 differences on the 12 cases) and the evaluation is
  unchanged. It stays in the index, so searching it again needs no
  re-ingest. Its running headers ("Prosthetic Gait analysis for
  [icrc] PhysiotheraPists" + page) survive `drop_repeated_lines` because
  they come in two variants, each on under 40% of pages.
- **`reasoning/fitting_guide.py`**: 33 statements in four sections:
  - *Readiness for fitting* (8): ICRC "In brief" (p. 49: ready for
    fitting / need preparatory treatment / cannot be fitted, each with its
    list), TT knee flexion contracture (p. 46), VA/DoD lower limb
    recommendation 5 (rigid or semi-rigid dressing after transtibial
    amputation, "Weak for", p. 36), VA/DoD upper limb "cleared … for a
    diagnostic socket fitting" (p. 17), WHO preparatory training and the
    decision not to prescribe (pp. 100-102).
  - *Preparatory or definitive prosthesis* (6): CMS p. 10 (no evidence; not
    non-alignable preparatory prostheses), ICRC "A definitive socket is
    fitted to a stable stump" (p. 44), stump shrinkage and recasting
    (p. 46), stubbies for bilateral TF (p. 48), and the upper-limb
    prescription list that starts with "Design (e.g., preparatory versus
    definitive)" (VA/DoD table 5, p. 18).
  - *Fitting, check-out and follow-up* (7): the VA/DoD lower-limb
    algorithm (module B: candidate? -> prescription -> "fabrication,
    fitting, and delivery" -> "final prosthesis check out" -> does it meet
    the goals?, pp. 144-145), ICRC first fitting principles and structured
    process (p. 66), TF check socket and length (pp. 72-73), WHO delivery
    check (p. 102), VA/DoD upper limb table 6 (signs the prosthesis needs
    modifying, p. 18).
  - *Alignment* (12): ICRC definition and steps (p. 31), initial TT and TF
    alignment (pp. 31-41), TT foot angle, socket flexion and foot position
    (p. 68), TF socket angles, foot, knee axis and knee friction (p. 71),
    footwear and heel height (p. 110); WHO "Individual customization is
    required for fit and alignment" (p. 101) for every level.
- **Six more component statements** from the ICRC manual: TT PTB and
  total-surface-bearing sockets (p. 20), total contact socket conditions
  and grafted skin / interface (p. 46), TT suspension methods with knee
  stability (pp. 20, 45), TF hip flexion contracture and a lockable knee
  (p. 46). The transtibial socket section is no longer empty.
- **Not used:** the VA/DoD upper limb 2014 recommendation "Initiate upper
  extremity prosthetic fitting as soon as the patient can tolerate mild
  pressure" (p. 96) is marked "Deleted" in the 2022 guideline; the
  multi-column phase tables (VA/DoD lower limb pp. 104-110) extract with
  their cells mixed, so no quote can be tied to its phase.
- **Readiness shows the case's own entries** (time since amputation,
  wound, volume, skin, pain, sensation, comorbidities, cognition) as
  entered, above the statements, never judged; statements never depend on
  them (tested).
- **Model and page:** `Quote.items` (a list a quote introduces),
  `CitedStatement.source_type`, `FittingSupport`; `Rule.bilateral_only`.
  The grade badge now reads "Source grade: none given" plus the kind of
  source ("guideline or protocol", "professional knowledge (manual)")
  instead of "Guideline grade: none given (consensus statement)", which
  would have been wrong for a manual. The disclaimer and intake banner
  mention design and fitting and say the tool does not judge readiness.
- **Review log version 4:** adds `fitting` (recorded values and every
  statement with quote, items, context, citation, grade, source type and
  mark) and `source_type` / `items` on component statements.
- **Tests:** 219 (25 new). The quote test covers both guides and checks
  list items follow their heading in order. Checked with four deliberate
  errors in memory (one word changed, wrong page, two list items swapped,
  wrong grade): all four caught, each naming the statement.
- **Run check** (`python app.py`, real model and index): 13 English cases
  (all 12 levels, bilateral TT/TF/transhumeral, K0-K4) and 2 Arabic,
  1,514 page checks plus the decision checks, 0 failed: every statement
  that applies on the page word for word with its list, context and
  citation; statements for other levels absent; no gap cites the ICRC
  manual. Statements per case: transtibial 22 fitting + 11 component,
  transfemoral K2 23 + 14, bilateral TF 24 + 12, KD/HD/partial foot/Syme
  16, upper limb 7. First case 12.3 s (model load), then 0.10-0.18 s.
  Server log: 74 requests, no 500s (one deliberate 400, two favicon 404s).
  Screenshots (English TT readiness and alignment, Arabic TF) checked by
  eye: lists, badges and right-to-left layout fine.
- **Review log:** 26 lines; the two new ones carry the note "automated run
  check 2026-10-09 (design and fitting)".
- **Needs checking by a prosthetist:** whether the alignment-to-gait
  statements (written for ICRC polypropylene prostheses) read as general
  enough, and the Arabic section names (المحاذاة for alignment, طرف اصطناعي
  تمهيدي (مؤقت) for preparatory prosthesis).
- **Manifest note:** R04 (AHRQ CER 213, 255 pages) is on disk and extracts
  cleanly, but its manifest row still says "needs manual download".
- Committed 2026-10-09 as `988f13f`. Not pushed.

## Trial readiness 1: stabilise for a specialist trial (done 2026-10-09)

Roadmap item 1 (`CLAUDE.md`): five fixes, no new features.

- **Cases persist.** `shared/store.py` writes each case to
  `data/cases/<case_id>.json` (in `.gitignore`), atomically (temporary file,
  then rename). A case not in memory is read from its file the first time
  its page is asked for, so review pages work after a restart; nothing is
  loaded up front. A file holds the case as entered, the retrieved passages,
  the gaps and the "not searched" warning (`case_file_version` 1). The
  component and fitting statements are not stored: they follow from the
  case and the guides, so they are worked out again on reading. Only ids
  of letters, digits, `-` and `_` are ever used as file names.
- **The intake form comes back filled in after an error**, every field as
  sent (a non-number typed into a number box shows empty: the browser can't
  display it). A choice that isn't one of the options falls back to the
  empty option, never a guessed one.
- **Switching language keeps the intake input.** Chosen approach: the
  language link on the intake page is a button that posts the form
  (`switch_language`); the server sends the same form back, filled in, in
  the other language, sets the cookie, and saves nothing. No JavaScript;
  it reuses the refill above. An invisible submit button placed before it
  keeps Enter sending the case (Enter uses the form's first submit button).
  The review page still switches by link, so its unsent note and marks are
  still lost on a switch.
- **No Python wording in intake errors.** Each value is parsed with the
  form's own label: "Age (years): enter a whole number." / "العمر
  (بالسنوات): أدخل عدداً صحيحاً.", likewise "enter a number", "enter 0 or
  more", "greater than 0", "choose one of the listed options", and for
  device rows "prior device 1: Years used: …". Anything unexpected shows a
  generic translated message; Python's text goes to the server log only.
- **Test lines moved out of the review log.** The 26 lines are now
  `data/review_log.test.jsonl`, unchanged (SHA-256 identical);
  `data/review_log.jsonl` was started empty for the trial.
- **Tests:** 237 (18 new: 7 in `tests/test_store.py`, 11 in
  `tests/test_routes.py`). Route tests use a temporary cases folder, like
  the temporary log. Checked by undoing each fix in memory: no disk write
  failed 7 tests, no refill 26, Python's number parsing 17.
- **Live check** (real model; cases and decisions redirected to a scratch
  folder, so `data/` stayed clean): translated errors and refill in both
  languages, language switch, a case written (50 KB), the server process
  stopped and started again, the same review page identical character for
  character, a decision saved after the restart. 11 checks, 0 failed; no
  tracebacks in either server log.

## Trial readiness 2: tooling for the two human reviews (done 2026-10-09)

Roadmap item 2 (`CLAUDE.md`), first part. How cases are analysed is
unchanged: the intake route's analysis moved, word for word, into
`intake/routes.py analyse_case()`, which the trial loader calls too.

- **Arabic term sheet** (`shared/arabic_terms.py`): `export` writes
  `data/trial/arabic_terms.csv`, 209 rows (157 page texts, 17 gap field
  names, 35 choices) with key, English, Arabic, where it appears, and empty
  "corrected Arabic" and "comment" columns. "Where it appears" comes from
  searching the templates and modules for the key, or for the prefix a
  template builds it from (`'component.' ~ key`, `f"error.required.{name}"`);
  every key was found. `apply` uses Python's `ast` to find each corrected
  string's exact place in `shared/i18n.py` and replaces only those (a
  multi-line Arabic text becomes one line), shows a diff, writes after a
  yes, and refuses the whole sheet on an unknown key, Arabic changed since
  the export, or a `{placeholder}` the English lacks. `export` won't
  overwrite a filled-in sheet.
- **15 trial cases** in `data/trial/cases/` (`trial-01` … `trial-15`):
  all 12 levels, left/right/bilateral in both limbs, K0-K4 and unknown,
  1 to 15 gaps each with the real index, some free text in Arabic. Only
  `Case` fields, so no identifiers. `python -m intake.load_trial_cases`
  analyses and saves them to `data/cases/`; a file whose `case_id` doesn't
  match its name stops the load before anything is saved.
- **Trial report** (`python -m review.trial_report`): reads the review log,
  prints a summary, writes `data/trial/report.csv` (in `.gitignore`) in
  sections: totals, gap fields (Needed / Not needed / not marked, split by
  source shown), gaps without a source marked Needed (with case ids),
  statements (Relevant / Not relevant / not marked), decisions, edit notes.
  Counts only; rows in field-guide and statement-guide order; each logged
  decision counts once and the totals say how many cases were decided more
  than once. Older log versions are read (gap marks only).
- **Tests:** 262 (25 new: 10 term sheet incl. the export/apply round trip
  on a copy of `i18n.py`, 7 trial cases and loader, 8 report on a small fake
  log written by `record_decision`).
- **Sample** (scratch folder, real model): the 15 cases loaded, 8 fake
  decisions on 7 cases logged, report built; e.g. "prior_devices" marked
  Needed 3 times with no source shown, which matches the known library gap.

## Evidence 3a: knowledge-item structure (done 2026-10-10)

Roadmap item 3 (`CLAUDE.md`), first part: the structure only. No clinical
values; the pages and the review log are unchanged.

- **`CLAUDE.md`:** clinical judgements (evidence layer, evidence tag,
  confidence, population, limitations) come only from the owner's rule
  table (`data/knowledge/evidence_rules.csv`) or the owner's own values;
  code applies them and never infers them.
- **Model:** `KnowledgeItem` in `knowledge/models.py`, next to
  `ProtocolChunk`, so any layer can use the shape without importing the
  guides. Frozen (a change makes a new item, which is checked again) and
  keyword-only. Allowed values as in the brief; `assigned_by` is a rule id
  (`R` + digits), "manual" or "none". Two more checks keep every value
  traceable: a clinical value with `assigned_by` "none" is refused, and so
  is "rule-assigned" without a rule id.
- **Items:** `knowledge/items.py` builds one item per guide statement:
  **59** (26 component: 19 rules, 5 K-level descriptions, 2 cautions; 33
  fitting), as `SYSTEM_DESCRIPTION.md` counts them. Choices made while
  building:
  - **`list_items` added** (not in the brief's field list): 7 statements
    are a heading followed by a list ("Those who are ready for fitting",
    the ICRC transtibial suspension methods, VA/DoD upper limb tables 5-6,
    …). Without it the item would hold only the heading.
  - **`date`** is the source's year from the catalog (e.g. "2017"), the
    only date recorded.
  - **`domain`** is "prosthetics" for both guides.
  - **`citation`** is the review page's form, "title (year), p. N".
  - **Context quotes not copied** into the item (scope, confidence and
    caveats from the same document). They stay in the guides. Putting one
    into `population` or `limitations` would be a judgement.
- **Export:** `python -m knowledge.items` → `data/knowledge/items.json`
  (54 KB; `ensure_ascii=False`, `\n` line ends; no timestamp, so two
  exports give the same SHA-256). The file is in git; a test fails, naming
  the command, if it no longer matches the guides. Like the Arabic term
  sheet, the export never overwrites a file in which a team field is set,
  or one it can't read (`--force` replaces it).
- **Tests:** 283 (21 new, `tests/test_knowledge_items.py`). Checked with
  nine deliberate errors in memory (a grade lower-cased, a confidence
  filled in by code, the page left out of the citation, list items left
  out, the K-level cautions left out of the guide, Arabic escaped,
  confidence values unchecked, team values overwritten, a guide quote
  changed after export): all nine caught.
- **Next (3b, needs the owner):** the owner's `evidence_rules.csv` and
  the code that applies it (`assigned_by` = the rule id, status
  "rule-assigned"); where the owner's own values are kept; and how a
  re-export keeps values already set (today it refuses).

## Evidence 3b-3c: source inventory and the owner's rules (done 2026-10-10)

- **3b, facts for the rule table:** `data/knowledge/source_inventory.md`
  (written by a one-off script, read-only otherwise): per cited document
  its title, year, source_type, item counts (component / fitting) and
  grades as printed, and per item its id, grade, page and first 120
  characters. 5 documents; grades only in the two VA/DoD guidelines (4
  "Weak for", 4 "Neither for nor against", 4 without a grade).
- **3c, the owner's table:** `data/knowledge/evidence_rules.csv`, 8 rules
  (R1-R8), copied cell for cell from the owner's message (UTF-8 with a
  byte-order mark, like the Arabic term sheet). Code never writes it.
- **Conditions, approved by the owner** (`knowledge/evidence_rules.py
  CONDITIONS`):
  - R1-R4: either VA/DoD guideline (lower limb 2024, upper limb 2022) and
    `grade_as_printed` exactly "Strong for"/"Strong against" (R1),
    "Weak for"/"Weak against" (R2), "Neither for nor against" (R3), or
    empty (R4, "no printed grade").
  - R5: CMS 2017 and the knowledge ids `cms_k0_description` …
    `cms_k4_description`.
  - R6: CMS 2017 and any other item. The CMS statements all have no
    grade, so ids tell the K-level descriptions apart.
  - R7: the four WHO standards documents, parts 1 and 2, in English and
    Arabic. The catalog dates the Arabic editions 2019.
  - R8: the ICRC manual.
- **The owner's decisions (2026-10-10):**
  - "unassigned" in a rule is deliberate: the rule sets tag and
    confidence, marks the item rule-assigned and leaves the layer empty;
    such items are not in `items_to_curate.csv`.
  - The origin check (an evidence value needs `assigned_by`) covers only
    evidence layer, tag and confidence; population and limitations may be
    filled for any item later, and stay empty for now (model changed).
  - "per item" in the layer column means the rule sets nothing (none of
    the 8 rules uses it).
- **Behaviour:** exactly one rule matching an item sets its three values,
  "rule-assigned" and the rule id; none, or a "per item" rule, leaves it
  "unassigned" (and undoes values of a rule that no longer matches); two
  or more stop the run, naming each item and its rules, with nothing
  written. Rules never touch population or limitations, and never replace
  evidence values set by hand or a reviewed item (an error too). The table
  must have exactly the six columns, valid values, unique ids, and one
  condition per rule. The export works rule values out again each time;
  it refuses to replace `items.json` holding population or limitations,
  values set by hand or a review, or a sheet with a filled-in cell.
- **First pass:** R1 0, R2 4, R3 4, R4 4, R5 5, R6 10, R7 4, R8 28. All
  59 rule-assigned (46 with the layer left unassigned by the rule), so
  `items_to_curate.csv` has only its header. Two exports gave the same
  SHA-256 for both files, from either command.
- **Tests:** 303 (20 new in `tests/test_evidence_rules.py`, step 3a's
  tests adjusted for the model change). Eight deliberate errors in memory
  (overlap resolved by the first rule, rules filling population, rule
  confidence unchecked, a "per item" rule assigning values, R6 without the
  K-level exception, the sheet listing layer-unassigned items, a filled
  population overwritten, the sheet check skipped): all caught.
- **Decided for later steps, not built:**
  - **Importing the owner's values** (e.g. a filled-in
    `items_to_curate.csv`): refuses evidence layer, tag and confidence
    for a rule-assigned item; accepts population and limitations for any
    item. Where those values are kept, so that an export keeps them, is
    still open (today the export refuses to replace them).
  - **Review page (3e):** where a rule left the layer unassigned on
    purpose (status "rule-assigned", layer "unassigned"), show "Evidence
    layer: not rated by the source" instead of nothing (with its Arabic
    text in `shared/i18n.py`).

## Evidence 4a: golden-case benchmark, format, runner, three cases (done 2026-10-10)

Roadmap item 4, first part: the manual live-run checks as a repeatable suite.

- **Format:** one fake case per file in `data/eval/golden_cases/`, in the
  research brief's benchmark fields (id, description, review_status,
  question = `Case.to_dict()`, expected_answer {gaps with source_expected
  true/false/null, statements_present, functional_level},
  common_wrong_answers {statements_absent}, supporting_sources,
  reasoning_path, evaluation_criteria). `reasoning_path` names, per
  statement, the rule fields that decide it and the case value each reads:
  every field the rule sets for a present statement, the failing one(s)
  for an absent one.
- **Runner:** `python -m intake.golden_cases [FILE ...] [--no-search]`.
  Each case goes through `analyse_case()` (POST /intake's analysis; it
  now takes an optional `retrieve`, default the normal search). Statements,
  supporting sources, reasoning path and functional level need no model;
  gap checks need the model and the vector store and are SKIPPED with the
  reason otherwise (looked up with `huggingface_hub.try_to_load_from_cache`,
  never downloaded). A mismatch is FAIL in a reviewed case, WARN in an
  unreviewed one; a gap citing a `RETRIEVAL_EXCLUDED_DOCUMENTS` document is
  always FAIL; a malformed file is ERROR; exit status 1 on FAIL or ERROR.
  The reasoning path is checked against the rule definitions and the case
  (named fields set on the rule, case values) without deciding any rule.
- **Three cases**, expectations drafted by hand from the rule fields and
  the field guide before anything was run (hashes recorded): golden-01
  transtibial left K3 (33 statements, 4 gaps), golden-02 transfemoral right
  K2 (37, 6), golden-03 transradial left (9, 4; no K-level description).
  All 52 component and fitting rules are decided in each case.
  `source_expected` is false for prior_devices (no library source covers
  it) and null elsewhere: whether a passage passes the score and topic
  check can't be drawn from the rules.
- **Result: 0 differences** (the runner, with the real model, and a
  separate script comparing raw sets). Of the 12 gaps drafted null, 10
  cited a source and 2 did not (golden-02 sensation, golden-03 residual
  limb length); golden-03 comorbidities cites the phantom-limb-pain review
  (the pattern of run-check finding 3 above).
- **Review (by Claude at the owner's request):** every expectation read
  against its rule's quote and page. The ICRC rules without a level in
  their quote follow the manual's headings: p. 20 "Transtibial prostheses"
  (PTB, TSB), pp. 67-70 "TT prostheses" (p. 68 alignment errors), pp. 70-73
  "TF prostheses (quad socket)" (pp. 71-73); pp. 44, 46, 49, 66 and 110
  are general. VA/DoD recommendation 16 is transfemoral by its own
  discussion ("sub-I and other transfemoral level sockets"). All three
  cases right; `review_status` set to "reviewed" (the only line changed).
- **Bug found, to fix in a separate step:** `cms_power_assist_ankle` has
  `ambulators_only`, but its quote (CMS p. 11) names no ambulators or
  K-level, so the statement is hidden for K0 without the source saying
  so. None of the three cases is K0; a K0 golden case would cover it.
- **What the reviewed cases hold to (current design, not bugs):**
  statements whose wording names a time ("Post-transtibial amputation",
  "a new amputation") are shown whatever the months since amputation
  (statements never depend on readiness values); "community ambulators"
  statements are shown for K2 (only K0 is excluded; VA/DoD's definition is
  shown as context). Changing either design changes golden-01/02.
- **Seen, not part of this step:** with the network up, loading bge-m3
  printed "You are sending unauthenticated requests to the HF Hub", so the
  load makes an optional Hub request despite `local_files_only`; with
  `HF_HUB_OFFLINE=1` the same run gives identical results. Check against
  principle 3 (no cloud service at runtime) separately. *Fixed 2026-10-16*
  (`knowledge/embedding.py hub_offline()`; see "Independent blueprint
  reviewed" below).
- **Tests:** 319 (16 new, `tests/test_golden_cases.py`): file checks,
  every kind of difference named, reviewed FAIL vs unreviewed WARN,
  excluded documents, the skip without the model, exit status.

## Evidence 4b: ten more golden cases, unittest guard, verify-all (done 2026-10-10)

- **Ten cases, all "unreviewed"**, drafted by hand from the rule table
  (each of the 52 rules decided present, or absent with the failing
  field) before any run; hashes recorded:

  | Case | Input (other fields: see the file) | Component + fitting | Gaps |
  |---|---|---|---|
  | golden-04 | transfemoral, bilateral, K1, uses stubbies | 12 + 24 | 2 |
  | golden-05 | knee disarticulation, left, K4 | 9 + 16 | 2 |
  | golden-06 | hip disarticulation, right, K2 | 11 + 16 | 4 |
  | golden-07 | partial foot, right, K-level recorded as unknown | 8 + 16 | 5 |
  | golden-08 | Syme, left, K3 | 8 + 16 | 2 |
  | golden-09 | transfemoral, left, K0 (the six ambulators rules absent) | 6 + 23 | 1 |
  | golden-10 | transtibial, right, no K-level recorded | 11 + 22 | 3 |
  | golden-11 | transhumeral, bilateral (unilateral rule absent) | 1 + 7 | 2 |
  | golden-12 | transtibial, left, only level and side (all 17 gaps) | 11 + 22 | 17 |
  | golden-13 | golden-01 through the Arabic form, Arabic free text, لا يوجد | 11 + 22 | 4 |

- **Result: 0 differences** in all ten (the runner with the real model,
  80 checks over 13 cases; and a separate script comparing raw sets).
  golden-13 was stored by the Arabic form exactly as its question and its
  analysis equals golden-01's, down to the passage each gap cites.
- **Section 4.5 cross-check** (counts the app showed): transtibial 22 + 11
  (golden-01, -10, -12, -13), transfemoral K2 23 + 14 (golden-02),
  bilateral transfemoral 24 + 12 (golden-04, K1), knee or hip
  disarticulation, partial foot, Syme 16 fitting (golden-05 to -08), upper
  limb 7 (golden-03, -11: 7 fitting; 9 and 8 with the components). No
  mismatch, reading "upper limb 7" as fitting statements, as
  `scripts/verify_prompts_0_2.py` check 0.6 also does. The 4.5 numbers hold
  only for these K-levels: a transtibial or bilateral transfemoral case at
  K2 shows one or two more component statements.
- **golden-09 encodes the current power-ankle rule:** `cms_power_assist_ankle`
  is drafted absent for K0, from its `ambulators_only`. The 4a review found
  that field is not in the quote; when that bug is fixed, golden-09's
  expectation must change at its review.
- **Gap sources** (all drafted null except prior_devices): no source for
  sensation in golden-06, -09, -12 and residual limb length in golden-06,
  while golden-12 (transtibial) cites VA/DoD p. 98 for length; K-level
  (unknown or not recorded) cites the ML walking-ability paper p. 5.
- **Runner:** two optional case keys. `interface_language: "ar"` submits
  the question through POST /intake with the Arabic cookie, filled in as an
  Arabic user would (لا يوجد for none; the route's store swapped for a
  memory-only one and its search for the runner's, both restored), and
  checks the stored case equals the question. `twin_of` compares the whole
  analysis with the twin's (statements, functional level, notes, gaps, and
  each gap's cited passage when the search ran).
- **unittest:** every golden case marked "reviewed" (now golden-01..03)
  runs in `python -m unittest` without the model: any non-gap check other
  than PASS fails the test run. Unreviewed cases are only read for their
  status. Three regressions made in memory (TT PTB socket widened to every
  lower-limb level, stubbies not bilateral-only, K-level read as K2) were
  each caught.
- **`python scripts/verify_all.py [--with-model]`** runs
  `scripts/verify_prompts_0_2.py` and `python -m intake.golden_cases`
  (`--no-search` without the model) as separate processes; exit 1 if
  either fails. Check 0.2 of the 0-2 script looked for the old wording
  "clinical judgements are the team"; it now looks for the owner's step-3a
  wording "clinical judgements come only from the owner".
- **Tests:** 326 (7 new: reviewed cases, Arabic form, twin).

## RAG: retrieval plus Claude with checked quotes (decided 2026-10-11)

- **The owner's decision (2026-10-11):** the system is to be a RAG, not
  rule-based. The 2026-10-06 decision "rules, not a language model" is
  replaced. Chosen, in order:
  - **Model:** the Claude API (cloud), behind one swap point
    (`reasoning/writer.py`) so a local model can replace it later.
    `claude-opus-5-5`, with server-side fallbacks on a refusal.
  - **Answers:** checked quotes. Claude writes short sentences in English
    and Arabic; each carries an exact quote from a retrieved passage and the
    passage id. Code checks every quote word for word
    (`reasoning/quote_check.py`) and removes any sentence that fails,
    keeping the reason, so the misquote rate is measured.
  - **Scope:** the review page's gaps, functional level, components and
    design and fitting come from retrieval plus Claude. The 59 hand-written
    statements stop producing the page and become the answer key
    (`python -m intake.golden_cases --rag`).
  - **Principle 1 stays:** the model reports what the sources say for the
    case; it never recommends, chooses, ranks, diagnoses or judges
    readiness.
- **Why the 2026-10-06 worry is answered by the quote check:** language
  models often cite sources that don't support them (Wu et al. 2025:
  50-90% of responses not fully supported). Here a sentence is shown only
  with a quote that is verifiably in the cited passage, labelled as AI,
  next to the quote. That proves the quote is real, not that the sentence
  says exactly what the quote says; the specialist checks that, as the
  label asks.
- **Without the API** (no key, offline, refusal) the page still works: gaps
  fall back to the retrieval and topic-word check of 2026-10-06, and each
  section lists the passages found, without summaries.
- **CLAUDE.md principles 2-4 and the quote rule were reworded the same
  day**, and `scripts/verify_prompts_0_2.py` check 0.2 looks for the new
  wording.
- **Built and tested offline (2026-10-11):** `reasoning/rag_topics.py`,
  `rag.py`, `writer.py`, `quote_check.py`; one search call for fields and
  topics; case file version 2 (the AI's answer kept); log version 5; the
  page's AI label, unavailable banner and passages-only fallback; Arabic
  texts; `python -m intake.golden_cases --rag`. 368 tests (42 new or
  rewritten), all offline; `scripts/verify_all.py`: everything passes except
  0.3 (uncommitted changes). Check 0.6 now compares SYSTEM_DESCRIPTION §4.5
  with the answer key, and check 1.3 found "name" keys and a date in the
  case file's AI part (renamed `kind`, version "rag-v1"). The Arabic term
  sheet was re-exported (225 rows, no corrections lost: there were none).
- **Measured, no API (2026-10-11): the search limits the RAG.** For the 13
  golden cases, only 129 of 359 expected hand-written statements (36%) are
  inside a passage the topic search finds at `RAG_TOP_K` 6 (10: 40%, 15:
  41%, 20: 47%, 30: 51%, with about 46, 71, 99, 125 and 169 distinct
  passages per case). Weakest: alignment 10/66, socket 2/23, suspension
  4/26, fitting 14/54; the four WHO statements are never found (the WHO
  manual's 408 passages never rank in a topic's top 6). The model can't
  quote what the search doesn't find, so this is the ceiling for coverage.
  *Corrected 2026-10-16:* the WHO manual does rank in topic top 6s (p. 97
  for the fitting topic in every development case, p. 28 for the upper-limb
  case); what never arrives is pp. 100-102, where its four answer-key
  statements are. The 129/359 rule was not recorded; `python -m
  intake.retrieval_misses` now measures it in code and matches it (see
  "Independent blueprint reviewed" below).
  Options for the owner: more passages per topic (cost grows with input),
  several queries per topic, or both. Note: queries tuned while looking at
  the golden cases would make them a weaker test of the search.
- **Not yet done:** the live run (no API key on this machine yet), so no
  real coverage, misquote rate, time per case or cost.

## Evidence 4c: held-out golden cases (done 2026-10-13)

- **Why:** the next RAG work tunes the search (topic queries, `RAG_TOP_K`)
  and the prompt against the golden cases' coverage, and tuning on them
  would make them a weaker test (the note above). Five cases are set aside
  and frozen before the first live `--rag` run, to measure whether the
  tuning carries over to cases it never saw.
- **Split** (moved with `git mv`, contents unchanged):

  | Set | Cases | Covers |
  |---|---|---|
  | Development (8), `data/eval/golden_cases/` | 01, 02, 03, 04, 05, 09, 12, 13 | TT, TF, TR, KD; K0-K4 and not recorded; lower-limb bilateral; the 17-gap case; the Arabic form |
  | Held out (5), `data/eval/golden_cases_held_out/` | 06, 07, 08, 10, 11 | hip disarticulation K2, partial foot K unknown, Syme K3, TT right no K-level, transhumeral bilateral |

  Kept for development: the three reviewed cases (the unittest guard runs
  them on every test run), golden-13 with its twin golden-01, golden-09
  (its expectation must change when the power-ankle bug is fixed, and a
  frozen file can't), golden-12 (the gap search for every field), golden-04
  (the only lower-limb bilateral case) and golden-05 (the only K4 case).
  Trade-off: hip disarticulation, partial foot, Syme, "K-level recorded as
  unknown" and upper-limb bilateral are now only in the held-out set, so it
  is partly a test on levels the tuning never saw.
- **Already seen of the five before the freeze:** their answer-key and gap
  checks (all PASS in 4b and in the baseline of 2026-10-13); the 2026-10-11
  search ceiling (129/359) was measured over all 13 together. The RAG has
  never run on them. Ceiling and coverage figures for tuning are reported
  over the 8 development cases from now on.
- **Freeze:** `data/eval/golden_cases_held_out.json` holds each case's
  SHA-256 of its JSON content (`content_hash`: line endings and layout
  don't count, since git converts line endings on this machine), with the
  date and a note. `tests/test_golden_cases.py` checks every case against
  it, checks that no id is in both sets, and reads each held-out file for
  shape only (never analysed in the tests). All five are unreviewed: if the
  team reviews them, the change of `review_status` (and any corrected
  expectation) changes the hash, and the owner records the new hash, date
  and reason in the manifest.
- **Runner:** `python -m intake.golden_cases` runs the development cases
  only. `--held-out` runs the held-out cases instead (with `--no-search` or
  `--rag` as usual) after checking the freeze, and runs nothing if a case
  changed, is missing or isn't listed. A held-out file named without
  `--held-out`, or another file with it, is refused. `verify_all.py` runs
  the development cases. CLAUDE.md: held-out runs only when the owner asks,
  each one recorded here.
- **Development run with the real search (2026-10-13):** 8 cases, 50 PASS,
  0 WARN/FAIL/SKIP/ERROR. Held-out runs so far: none.
- **Tests:** 375 (7 new: the freeze, shape, disjoint sets, which run takes
  which set, the refusals, the hash ignoring layout, a `--held-out` run on a
  frozen temporary copy of golden-03).

## Writer: Gemini's free tier (owner's decision, 2026-10-13)

- **The owner asked for a free model** in place of the Claude API (no key
  with billing on this machine). Checked on 2026-10-13:
  - **Gemini API (Google AI Studio key): chosen.** `gemini-3.8-flash` (the
    newest Flash) is on the free tier. Structured output takes a JSON
    Schema (`responseJsonSchema`; `enum`, `required`, `additionalProperties`
    supported), which is what `answer_schema()` already gives Claude.
    Long inputs (each call here is roughly 5-10k tokens of passages).
  - **DeepSeek:** no lasting free tier (a trial credit). **OpenRouter's
    free models** (Qwen, DeepSeek, Llama and others): 20 a minute and 50 a
    day without a $10 top-up, and free models come and go. **Groq,
    Cerebras and other free tiers:** smaller per-model token limits, and
    JSON-schema output depends on the model. Any of them can be added as
    another class in `reasoning/writer.py` if Gemini doesn't serve.
- **What the free tier costs instead of money** (Gemini API terms): Google
  "uses the content you submit ... and any generated responses to provide,
  improve, and develop" its products; "human reviewers may read, annotate,
  and process your API input and output"; "Do not submit sensitive,
  confidential, or personal information to the Unpaid Services." For an app
  offered to users in the EEA, Switzerland or the UK, only paid keys. The
  app's fake-data rule (CLAUDE.md 4) already covers it; the intake note says
  the case goes to a cloud service.
- **Limits:** Google doesn't publish free-tier numbers; each project's are
  shown in AI Studio (third-party reports range from 20 to 1,500 requests a
  day, by model). A case takes 3 requests; `golden_cases --rag` on the 8
  development cases takes 24. A used-up quota shows on the page as the
  reason there are no summaries. `gemini-3.5-flash-lite` usually allows
  more requests if needed (`GEMINI_MODEL`).
- **Built:** `GeminiWriter` in `reasoning/writer.py`, through the REST
  endpoint with Python's own `urllib` (no SDK, no new dependency). Key from
  `GEMINI_API_KEY`, sent in the `x-goog-api-key` header, never in the URL;
  thinking left at the model's default (logged as effort "model default");
  429/500/503 tried twice more, 3 s and 8 s apart; a blocked request,
  a declined or cut-off answer, no text or invalid JSON become the reason
  shown, like Claude's. Logged tokens: input = `promptTokenCount`, output =
  answer plus thinking tokens. `LLM_PROVIDER` in `shared/config.py` picks
  the writer (`"gemini"`, or `"claude"` for the Claude API, kept as it
  was); `golden_cases --rag` uses the same choice (no cost estimate for
  Gemini: free). `PROMPT_VERSION` stays `rag-v1` (same instructions); the
  log records the model that answered. Log format unchanged.
- **Texts:** the disclaimer and the intake note no longer name Claude
  (English and Arabic: "an AI language model in a cloud service"). The
  Arabic term sheet was re-exported: 2 rows changed, no corrections lost
  (there were none). CLAUDE.md principles 3 and 4 name both providers.
- **Not yet done: a live run** (no Gemini key on this machine). Unverified
  until then: that the API takes this schema as given (enums of passage
  ids, `additionalProperties: false`), how many of Flash's items the quote
  check removes (Claude never ran live either, so there is nothing to
  compare with yet), and the Arabic sentences. First one case through the app, then the development
  golden cases with `--rag`.
- **Tests:** 379 (4 new: the request, unusable answers, the key and the
  errors, retries; the default writer by `LLM_PROVIDER`).

## Independent blueprint reviewed, and the first fixes (2026-10-16)

- **The document:** `AI prosthetics lab independent blueprint.md` (untracked;
  an outside research report written from the 2026-10-11 handoff, before the
  Gemini switch and the held-out split). Reviewed section by section against
  the repo by Claude at the owner's request; the owner then asked Claude to
  act as the engineer on it. Nothing in it is adopted as a decision; its
  clinical and evidence proposals stay the owner's.
- **Its claims, checked here** (offline unless noted):
  - Correct: the VA/DoD lower-limb guideline has 26 recommendations, 16
    "Weak for", 10 "Neither", none strong (our extracted text, grading key
    left out); the upper-limb one 14; Wu 2025's "between 50% and 90% of LLM
    responses are not fully supported" is word for word in A01; every VA/DoD
    recommendation number and grade in its §11 matrix; its error bounds and
    sample sizes (§13); SOSORT's "Bracing is recommended …" (B, I, p. 20) and
    the 8-12 / 12-20 / 20-24 h definitions. Anthropic's and Google's
    supported-country lists do not include Syria (read online 2026-10-16;
    Google's page last updated 2026-04-28).
  - Wrong or out of date: the WHO manual "never" reaching the writer (above);
    the ICRC manual "excluded" (only from gap search: 127 of the 480 topic
    passages in the 8 development cases, second to CMS); topic queries
    "naming the side" (only "bilateral"); the GPU possibly unused (torch
    2.9.1+cu130, `sm_120`, driver 582.05); the repo in OneDrive (it isn't);
    "13 cases bound errors below 21%" (8 are now the tuning set; zero errors
    in the 5 held-out cases bounds the rate only below 45%); "re-parse the
    WHO manual first" (every answer-key quote is in `data/extracted/` on its
    page, and the measured misses below are not extraction problems).
  - Found while checking: since the RAG, nothing in code enforces "never
    advise" (prompt rule 5 only); none of the owner's evidence values
    (`items.json`) reaches the review page; the CMS cautions that K-levels
    "should not be considered a functional classification" reach the
    functional-level top 6 in 1 of the 7 lower-limb development cases; the
    Knezevic 2024 paper (`ml_walking_ability_…`, cited for the K-level gap)
    duplicated minority-class samples to 162 and then cross-validated over
    them (its own text), so its 93% may be inflated; all 40 rule statements
    expected in the held-out cases also appear in the development cases, so
    the held-out set tests query wording (other levels and K-levels) but not
    statements or passages; the Gemini free tier receives the passages too,
    ICRC (© ICRC, no reuse statement) and WHO (CC BY-NC-SA) text included;
    the review page names no licence; `pass1.csv` (open in the handoff) is
    not in the repo. AHRQ CER 213 (R04, public domain) and the AWMF G09-G11
    orthotics/rehabilitation guidelines are on disk but not catalogued.
  - Measured for a local writer (no change made): writer prompts are about
    6-11k tokens per part (bge-m3 tokeniser), up to 17.7k (golden-12's gaps,
    17 fields), up to 34k per case; bge-m3 takes 2,175 MiB of GPU memory in
    fp32 and on the CPU loads in 2.3 s, embeds 30 queries in 4.4 s and gives
    identical vectors. SQLite FTS5 (no new package) indexes all 3,468 chunks
    in memory in 0.07 s.
- **Built (no new dependency, no cloud call, no commit):**
  1. *Principle 3:* with `local_files_only`, loading bge-m3 still contacted
     huggingface.co twice (measured with the network blocked):
     huggingface_hub's "agent registry" fetch, and a transformers thread
     asking about a safetensors conversion of the `pytorch_model.bin`
     weights. `knowledge/embedding.py hub_offline()` switches the Hub's
     offline flag on while the cached model loads: 0 attempts, same vectors;
     a missing model still downloads.
  2. *Review page:* a section without an AI summary now says why, as code
     knows it ("the search found no passage", "the AI reported nothing", or
     "the checks removed the AI's n summaries"), and always lists the
     passages found. It used to say "The passages found … say nothing about
     this", even when no passage had been found or every item was removed.
     "n AI summaries removed" no longer claims every removal was a misquote.
     The page names the model that answered (as the provider reported it)
     and the prompt version; the disclaimer opens "Research prototype, not
     validated for clinical use" (blueprint §14). Arabic for each; the term
     sheet re-exported (225 rows: 3 added, 3 removed, 3 changed, no
     corrections lost: there were none).
  3. *Prompt rag-v2:* the writer gets only the case's amputation level,
     limb, side and recorded K-level (`case_for_prompt`), not the whole case:
     prompt rule 7 uses only these, and free text was the way an identifier
     or an opinion ("confirm K4") could reach the model. Intake note,
     README, SYSTEM_DESCRIPTION and CLAUDE.md principle 4's description of
     what is sent updated (the rule itself unchanged). Not yet measured
     live: no `--rag` run has been made with either version.
  4. *`python -m intake.retrieval_misses`* (blueprint step 1, adapted):
     development cases only, the app's own topic queries and filters, the
     `--rag` coverage rule (same document, 6 words in a row), the full
     ranking kept. First run: `data/eval/baseline/2026-10-16/`.
  - Tests: 400 (21 new). `verify_all.py`: the same three FAILs as the
    2026-10-13 baseline, all repo state (0.3 uncommitted changes, 0.5 main
    pushed, 1.8 one line in the trial log); golden cases 34 PASS, 0 FAIL.
- **First miss measurement** (8 development cases, 241 pairs, 57 statements,
  k = 6):
  - **Ceiling:** 85/241 (35%) reachable in some topic's top 6, 29/57
    statements; this matches the 2026-10-11 36% and its depth curve (here
    35/40/41/46/49/60% at k = 6/10/15/20/30/50), so the old script used this
    rule. A whole quote inside one passage: 49/241 (20%). In the statement's
    own topic: 51/241 (21%); 34 pairs are found only under another topic.
  - **Why the 156 others miss:** 149 *query mismatch* (the statement's own
    words put a gold passage in the top 6; the topic query ranks it 7-30 for
    26, beyond 30 for 123), 7 *representation* (even its own words don't),
    0 *not searchable*. One other document holds 4+ of the topic's top 6 in
    35 of them (the ICRC manual in 21).
  - **By topic** (own topic / reachable): fitting 0/36 and 10/36, socket
    0/17 and 2/17, interface 1/14 and 7/14, alignment 6/49 and 9/49,
    suspension 3/17, readiness 15/44 and 18/44, preparatory or definitive
    9/30, foot and ankle 6/18 and 14/18, knee 4/7, functional level 5/6 and
    6/6. **By document:** WHO implementation manual in 10 of 80 searches'
    top 6, 0/32 of its pairs reachable; ICRC 50 searches, 36/126; CMS 55,
    29/49; VA/DoD lower limb 45, 16/29.
  - **What it means:** the passages exist and embed well; one general query
    per topic does not reach the specific statements, mostly not even in the
    top 30, so raising `RAG_TOP_K` alone helps little (60% at k = 50). The
    blueprint's parsing and chunking fixes (Docling, re-chunking) answer the
    7 representation misses, not the 149. The writer's cap of 4 per topic
    (41 pairs expect a 5th or later item) doesn't bind yet: the search
    finds fewer.
  - **Before tuning queries on this:** the held-out cases share every
    statement with the development cases, so a query tuned to reach these
    statements will look good on the held-out cases too. The owner decides
    first: a statement-level hold-out, new reviewer-written statements held
    back, or accepting and recording the weakness.
- **Built next, same day (no new dependency, no cloud call, no commit):**
  5. *The yardstick asks first:* `.claude/hooks/protect_yardstick.py`, a
     Claude Code PreToolUse hook in the project's `.claude/settings.json`
     (with matching "ask" permission rules). Before Claude edits the golden
     cases, the freeze manifest, the two guides (the answer key),
     `evidence_rules.csv` or the review logs, or runs a shell command that
     names one of them with a write (redirect, `sed -i`, `mv`, `git
     checkout`, `Set-Content`, …), Claude Code asks the owner. Reading is
     never stopped; the app's own log writes are not touched. Seen firing
     live; 5 tests. A script that writes one without naming it is not seen
     (the held-out cases are also hash-frozen).
  6. *Sentence checks, measurement only:* `reasoning/sentence_checks.py`
     flags kept AI items whose English sentence has a number, a code (K0-K4,
     L-codes) or an amputation level the quote doesn't, a negation the quote
     lacks (or drops one it has), advice wording (directive, choice or
     ranking, readiness verdict, own recommendation; marked when the quote
     has the same word), or whose Arabic sentence has other numbers or codes
     or Arabic advice wording. Nothing is removed or shown: `golden_cases
     --rag` reports them ("rag sentence flags", INFO) and `python -m
     reasoning.sentence_checks` replays them over stored case files (none
     has AI output yet). The patterns are deliberately simple; the owner
     approves any that should ever remove or mark an item, from counts on
     real output (open item 3 below). 12 tests.
  7. *Licence on the citation line:* `licence` in `catalog.json` for the 12
     documents whose manifest row states a Creative Commons licence (8 CC BY
     4.0, 1 CC BY, the 4 WHO documents CC BY-NC-SA 3.0 IGO), copied as
     written; a test checks catalog and manifest agree both ways. The review
     page shows "authors; licence: …" under such a source's citation (CC
     licences ask for both); US federal works and documents without a
     recorded licence (ICRC, AAOP toolkit, AWMF, Fatone 2020) show nothing
     more. Not added: WHO's adaptation disclaimer for AI summaries of its
     text (part of open item 2). Arabic text added; term sheet re-exported
     (226 rows).
  - Checked live: golden-01 through the real form and search, AI off (the
    2026-10-13 end-to-end script, output to a scratch folder): OK, real
    `data/` untouched; the page opens with the prototype line, credits 19
    licensed passages, never says "say nothing". Tests: 419.
- **Open, for the owner** (none started):
  1. Where the app will run, for the owner and the trial. If from Syria,
     neither cloud writer is available; a local writer then becomes the only
     path to a live run (and to a trial that reviews summaries).
  2. ICRC and WHO text going to Gemini's free tier: accept and record,
     filter what the writer receives, or change the writer; whether to ask
     ICRC for permission.
  3. Code checks for advice wording and for numbers, codes, level and
     K-level in the English and Arabic sentences (the code half of principle
     1): patterns to approve, and best calibrated on a first live run.
  4. The owner's evidence values on the page (applying R1-R8 to AI items;
     R5/R6 need a ruling, since they match on knowledge ids).
  5. The CMS K-level cautions: fixed quotes on the page, answer-key entries,
     or a second functional-level query.
  6. The Knezevic paper: as it is, a limitation, a rule, or excluded.
  7. `cms_power_assist_ankle`'s `ambulators_only` and golden-09's
     expectation (still as recorded in 4a).
  8. How to hold out statements before query tuning (above).
  9. Which reviewer to approach (roadmap item 2).

## Product 6 and orthotics (owner's decision 2026-10-16; core split done 2026-10-17)

- **Decision (owner, 2026-10-16):** start orthotics (use case 03) before
  the trial, replacing "only after the trial results are in"; split `Case`
  first (item 6); stroke AFO is the first area. The others considered:
  diabetic foot (IWGDF 2023 is the richest orthotic source on disk, but all
  rights reserved, and its passages would go to Gemini's free tier),
  scoliosis (SOSORT, paediatric), cerebral palsy (paediatric; GMFCS needs a
  licence).
- **Built (no new dependency, no cloud call, no commit):** `CaseCore` in
  `shared/case_schema.py` holds what every domain records: case id, time,
  age, body weight, comorbidities, cognitive status, notes, with their
  checks and `unrecorded_fields()`/`unknown_fields()` (which now open any
  nested section). `Case(CaseCore)` stays the prosthetics case: amputation
  level, side, cause, months since amputation, residual limb, activity and
  K-level, prior prostheses, contralateral limb. Prior devices and the
  contralateral limb stay prosthetic because their field-guide queries are
  about prostheses; an orthotic section can reuse `PriorDevice` if the
  owner wants device history (the blueprint suggests adherence too).
  `DOMAIN_CASES` and `case_from_dict()`: a case dict names its domain in
  "domain" unless it is prosthetics, the default. So a prosthetics dict is
  unchanged: no `CASE_FILE_VERSION` or `LOG_VERSION` change, and the frozen
  held-out cases still pass "question must be exactly what Case.to_dict()
  gives". The store reads through `case_from_dict()`; the golden-case and
  trial-case loaders keep `Case.from_dict()`, since their checks are
  prosthetic (a dict naming a domain fails there). The core fields' search
  queries in `shared/field_guide.py` are worded for prosthetics; an orthotic
  field guide needs its own.
- **Checked:** 424 tests (5 new, with a stand-in second domain). All 5
  saved case files, 15 trial cases, 13 golden cases (8 development, 5 held
  out) and the review log's 1 line read through the new code and give the
  identical dict. `golden_cases --no-search`: 34 PASS, 0 FAIL, as before.
- **Next, waiting on the owner** (nothing orthotic is built or shown yet):
  1. The orthotic intake fields for stroke AFO, and which are critical.
     Blueprint §7 proposes a set from its sources (for stroke: ambulatory
     status with a named gait-speed test, plantarflexion range with the knee
     extended and flexed, tone with its scale, grade, muscle and position);
     its critical/important split is a proposal for an orthotist to confirm.
  2. Which sources to catalogue. On disk (rough counts of orthosis words in
     pypdf text, 2026-10-16): Choo 2021 AFO meta-analysis, already catalogued
     (`afo_stroke_walking_review_2021`); WHO PIR module 3, neurological (192
     pages, 76 mentions; WHO licence, see open item 2 above); VA/DoD stroke
     rehabilitation 2024 (242 pages, only 11 mentions; US federal work);
     Wang 2025 3D-printed AFO review (41 pages). Arabic: only the WHO P&O
     standards, which are about running a service (WHO's Arabic term for
     orthoses is المقاويم).
  3. The orthotic topics (the counterpart of `reasoning/rag_topics.py`), the
     answer key and the golden cases (the blueprint's GC-ORT-01 is a
     proposal).
  4. Whether orthotic passages may go to Gemini's free tier (open item 2
     above).
  (Items 1-3 built on 2026-10-22 as drafts, item 4 still open: next section.)

## Orthotics, use case 03: stroke AFO (built 2026-10-22 as drafts, awaiting the owner)

- **Owner's answers (2026-10-21/22):** commit, then branch (main at
  `578ef22`; this work is on the branch `orthotics`, not committed); use
  Claude's proposal as drafts for the fields, critical flags, topics and
  golden cases, marked as awaiting the owner's and an orthotist's review;
  sources: VA/DoD stroke rehabilitation 2024, WHO PIR module 3, Wang 2025
  3D-printed AFO review, ICRC AFO manual 2010, and "download what is
  suitable"; scope: modules 1-3 plus fitting (intake with the exam and gait
  by phase, information needed, what the sources say about devices and
  about design and fitting, the orthotist's choice in the review log).
- **Sources (catalog 24 documents; none of the new ones is searched for
  prosthetics):** `stroke_rehabilitation_va_dod_cpg_2024` (G14),
  `who_pir_module3_neurological_2023` (G16, CC BY-NC-SA 3.0 IGO),
  `afo_3d_printing_review_2025` (R05, CC BY 4.0), `afo_manufacturing_icrc_2010`
  (K07, downloaded 2026-10-22) and `fes_drop_foot_nice_htg178_2009` (G21, NICE
  HTG178, downloaded 2026-10-22). Downloaded, not catalogued: K08, the ICRC
  KAFO manual 2006 (no KAFO in scope yet). Not on disk: G03, the APTA/ANPT
  2021 guideline on AFO and FES after stroke, the most direct source (the
  journal site answered with a Cloudflare check; "needs manual download").
- **Built:**
  - `shared/case_schema.py` `OrthoticCase(CaseCore)`: condition (stroke),
    affected side, months since onset, goals, `Walking` (status, aid, gait
    speed with its test, falls, deviations as observed by phase: None = not
    observed, [] = none), `OrthoticExam` (dorsiflexion with the knee extended
    and flexed, signed, ±90°; plantarflexor tone grade with its scale;
    strengths; knee in stance; foot posture; protective sensation;
    proprioception; skin), footwear, donning, prior orthoses or FES,
    implanted device (asked only if FES is discussed, never a gap), and the
    orthotist's own "what the orthosis must do" lines.
  - `shared/field_guide.py` `ORTHOTIC_FIELDS`: 23 gap fields, 6 marked
    critical (months since onset, goals, both dorsiflexion ranges,
    protective sensation, skin); the page marks a critical gap and hides
    nothing.
  - `orthotics/` package: `topics.py` (devices: AFO or FES, types, effects
    and limits, cautions; design and fitting: design, fitting and check-out,
    timing and training, outcome measures), `rag.py` (`PROMPT_VERSION`
    rag-ort-v1: never set angles, materials, trim lines or wearing times,
    never say whether this patient should have an orthosis or FES, another
    condition's passage only where the source says it applies to stroke;
    only condition, limb, side and months since onset are sent), `routes.py`
    and its form (`/intake/orthotics`, English and Arabic).
  - Shared code dispatches by `case.domain`: `reasoning/rag.py` `Profile`,
    `rag_topics.topics_for_case`, `knowledge/retrieval.py domains_for()`
    (an orthotic case searches only "orthotics" documents), the review page
    (orthotic case summary, gaps by phase, the orthotist's requirements,
    critical badge), and `review/decision_log.py` (`LOG_VERSION` 6 adds
    "domain"; earlier lines still read).
  - `intake/golden_cases.py` reads orthotic cases, gaps only (there is no
    orthotic answer key); `data/eval/golden_cases/golden-ort-01..03`
    (unreviewed drafts, PASS with the real search).
  - `python -m knowledge.evaluate --orthotics`: the app's own orthotic
    searches for the two fake cases in `data/eval/orthotic_topics.json`
    (pages read by hand; a draft yardstick for tuning, not held out).
- **Measured (2026-10-22, 26 topic searches = 2 cases × 13 topics):**

  | Step | Right passage among those the AI sees | Choo 2021 share |
  |---|---|---|
  | First build (case words: condition, side, months, "ankle-foot orthosis") | 10/26 | 103/146 |
  | + at most 2 passages per document | 8/26 | 51/146 |
  | + ICRC text repaired, yardstick widened after reading | 14/26 | 51/146 |
  | no case words; limit 1 / 2 / 3 per document | 18 / 18 / 20 of 26 | 26 / 38 / 50 |
  | + reworded fitting, timing and tone queries (now) | 22/26 | 42/146 |

  - Choo's meta-analysis (title and table rows) filled most places, hence
    `ORTHOTIC_PASSAGES_PER_DOCUMENT` = 3 (orthotic searches only).
  - The ICRC AFO PDF splits words after ligatures ("fi tting", "Th e"):
    catalog `split_ligatures` (only that document) rejoins them in
    extraction. Re-ingested: every other document's chunks have identical
    text and vectors within 2.5e-7.
  - The yardstick was widened only with pages read to answer the topic:
    Fatone 2020 pp. 7-21 (its instrument tables: 10MWT, gait speed, MAS in
    stroke), WHO P&O standards part 1 pp. 62-63 and implementation manual
    pp. 101-102 (fitting, user training, follow-up), English and Arabic.
  - The case's side and months since onset in the search text cost right
    passages (the only condition is stroke, which the queries name), so the
    orthotic search uses each topic's own wording.
  - Still missed: protective sensation and plantarflexor tone. The library
    has little on them for an orthosis: two ICRC lines on EVA lining "to
    prevent skin breakage in patients with sensation loss", inside long
    manufacturing passages; the VA/DoD spasticity text is about botulinum
    toxin; Fatone's MAS row is a reliability table. G03 would likely help.
  - Tuned on this two-case yardstick; there is no held-out orthotic set.
  - Prosthetics unchanged: `knowledge.evaluate` as before (English 10/10,
    Arabic 7/8 without German, cross-language 3/3, off-topic ≤ 0.44);
    development golden cases 50 PASS, 0 FAIL; held-out cases not run.
  - Without the AI, the gap topic-word check had cited NICE for sensation
    ("absolute **numb**ers") and skin ("skin surface FES"); both terms are
    tightened. Other offline gap citations are often Choo table rows.
- **Run check (2026-10-22, real search, AI switched off):** a fake case
  through `/intake/orthotics` in the browser: a tone grade without its
  scale is refused and the form keeps what was typed; the review page shows
  the orthotic disclaimer, case summary, deviations by phase, 4 gaps (2
  critical), the device and design sections with their passages, and
  renders right to left in Arabic. Numbers now show as typed (7, not 7.0).
- **Waiting on the owner:**
  1. Review the drafts: the fields and which are critical, the topics and
     their wording, the prompt's rules, the golden cases, the yardstick.
  2. Whether orthotic passages may go to Gemini's free tier (WHO PIR module
     3 is CC BY-NC-SA, the ICRC manual has no reuse statement). No live
     orthotic run has been made (`--rag` was not run).
  3. The Arabic orthotic terms in `shared/i18n.py` need an Arabic-reading
     orthotist (WHO's Arabic edition uses المقاويم for orthoses).
  4. G03 (APTA/ANPT 2021) by manual download, if wanted.
  5. Optional: advice patterns in `reasoning/sentence_checks.py` for angles
     and wearing times (the prompt forbids them; nothing in code flags them).

## Orthotic modules 2-4 from the design canvas (built 2026-10-23, drafts)

- **Asked (owner, 2026-10-23):** "apply the artifacts to the app" (the
  "Orthotics Module Design" canvas, https://claude.ai/artifact/4DXeCxBbo6nMWWEgqKu6ZD,
  six screens) and make sure the app implements the brief's four orthotics
  capabilities: تحليل الحالات الوظيفية (functional case analysis), اختيار
  وتصميم الأجهزة التقويمية (choosing and designing orthotic devices), ربط الحالة
  بالمكونات والمواد (linking the case to components and materials), دعم سير عمل
  التصميم الرقمي (supporting the digital design workflow).
- **Where each is now:**

  | Brief capability | Module | Page |
  |---|---|---|
  | Functional case analysis | 1 | `/intake/orthotics` and the review page (2026-10-22) |
  | (the canvas's bridge) | 2, requirements | `/orthotics/<id>/requirements` |
  | Choosing and designing devices; linking the case to components and materials | 3, options | `/orthotics/<id>/options` |
  | Digital design workflow | 4, digital design | `/orthotics/<id>/design` |

  The module map is `/orthotics`. Modules 5 (fit, tune and train) and 6
  (follow-up) are on the canvas but not built: they cover other capabilities
  (follow-up is roadmap use case 07, and needs a pseudonymous link between
  visits first).
- **Built (no new dependency, no cloud call, no commit):**
  - `orthotics/plan.py` `OrthoticPlan`: the orthotist's requirements (text,
    the case findings they come from, priority), up to three options (device
    type, materials and parts each tied to the requirements it serves, the
    orthotist's yes/partly/no marks, notes), the choice and its reason, the
    workflow steps (status, method, notes) and the design parameters, every
    save a new version. Vocabularies: 9 device types, 10 materials and
    parts, 5 steps with their methods, 9 parameters: a PROPOSAL awaiting the
    owner and an orthotist. Saved in the case file (`CASE_FILE_VERSION` 3,
    "plan"; older files read unchanged).
  - `orthotics/sources.py`: per device type, part and step, a fixed search
    text and topic words; the pages show up to 3 passages that mention the
    item (at most 2 from one document), quoted as printed, labelled as not
    summarised and not checked to support the case. Nothing typed is
    searched, nothing is sent to the AI.
  - `orthotics/modules.py` and its templates: the canvas's look (dark teal
    header with the modules, case bar, cards; system fonts) on every
    orthotic page, the intake form and the orthotic review page included,
    English and Arabic.
  - The review log: `LOG_VERSION` 7 adds "plan" to every entry (null for a
    prosthetic case) and the decision "design_choice", appended when the
    orthotist records a choice (the reason is the note). Older lines read
    unchanged. The trial report counts a design choice as a decision and
    leaves its copy of the gaps and statements out of the mark counts
    (nothing was marked on the options page).
  - 23 new tests (488 in all).
- **Where the app differs from the canvas, by CLAUDE.md's principles:**
  the canvas shows AI-suggested design parameters ("joint axis on the
  malleolar line", "trim line below the fibular head") and system-written
  judgements ("Addresses R1 yes", "Leaves a Must requirement unmet", hard
  stops that route a case to a doctor, "Any rigid design needs pressure
  relief"). Here every mark, requirement and parameter is the orthotist's;
  the only thing the page derives is a restatement of the orthotist's own
  marks ("Marked by the orthotist as not addressing a Must requirement").
  Hard-stop rules would be clinical judgements: they wait for the owner's
  rules. Also not built: the 3D scan viewer, pressure maps and simulation
  (no scan data reaches the app), clinic stock, send to manufacture, the
  per-measure "how it was measured" column and goals by ICF level (the
  intake keeps the tone scale and gait-speed test only). Google Fonts are
  not loaded (principle 3: nothing from the internet); the pages declare a
  light colour scheme, which also stops the browser pane's automatic dark
  mode seen on 2026-10-22.
- **Measured while building (real library, 2026-10-23):** the first
  wording found title pages, a PubMed Central disclaimer, a scoliosis brace
  and the cerebral palsy review for several items. With topic words, the
  scoliosis guideline and the cerebral palsy review left out (other
  conditions, and no AI to judge whether they apply to stroke) and
  table-of-contents passages dropped, the passages read as relevant for
  most items (e.g. straps: ICRC pp. 9 and 16; release: WHO standards pp.
  62-63 and the implementation manual p. 102); the heel wedge finds none
  (the page says so); carbon and the posterior leaf spring find only
  table rows. Not a yardstick, not measured further.
- **Run check (2026-10-23, real search, AI off):** a fake stroke case
  through the browser: requirements tied to findings with priorities; two
  options, each part tied to the requirements and so to the findings
  ("Plantarflexion stop: serves R1 ← Swing: toe drag"); passages per device
  and part; the choice recorded; workflow steps and a parameter version
  saved; every page in Arabic, right to left, with no English interface
  text. The check ran the real app, so its choice was appended to the real
  `data/review_log.jsonl` (line 2, case `a254f60fd4e6`, decision
  "design_choice", fake data): append-only, so it stays unless the owner
  decides otherwise (as with `review_log.test.jsonl` on 2026-10-09).
- **Waiting on the owner:** the vocabularies and wording (drafts); whether
  hard stops are wanted and their rules; modules 5-6; AI summaries for the
  option and step passages (they would go to the cloud model, open item 2
  of the previous section); the Arabic terms (an orthotist). (Later:
  modules 5-6 were built that evening, and the hard stops are kept as draft
  rules: "Orthotic modules 1, 5, 6 and the hard stops" below.)

## One look for both domains (2026-10-23)

- **Asked (owner):** "normalize also the prosthetic part to the interfaces
  like those for orthotics".
- **Built:** the orthotic look moved to app-wide templates
  (`templates/ui_style.html`, `ui_header.html`, `ui_base.html`; CSS names
  `ui-*` instead of `ort-*`). Every page now has the same header: a domain
  switch (Prosthetics / Orthotics), the domain's modules, the language link
  (the intake forms keep their own button, which keeps what was typed) and,
  on a case's pages, the case bar. The prosthetic modules follow the brief's
  prosthetics capabilities: 1 Evaluate (تقييم حالات البتر), 2 Functional level
  (تحليل المتطلبات الوظيفية), 3 Components (دعم اختيار المكونات), 4 Design and
  fitting (دعم قرارات التصميم والتركيب). They are the review page's sections
  (`#gaps`, `#functional`, `#components`, `#fitting`), not separate pages,
  because one decision form marks the gaps and statements together. The
  prosthetics map `/prosthetics` lists them and the fifth, follow-up (المتابعة
  والتقييم), as not built. `/` still opens the prosthetic intake form.
- **Unchanged:** every prosthetic text, heading, form field and the decision
  form (verify check 0.6 still finds the same headings; 1.7 the language
  button); 4 new tests (492).
- **Checked in the browser (2026-10-23, no decision submitted, so nothing
  reached the review log):** the prosthetics map, intake form and review page
  in English and Arabic (right to left, no English interface text but the
  field paths shown before); the section links jump to their sections; one
  header row at 1,100 px for both domains, wrapping below that.

## First live run, and the AI off for orthotics (2026-10-23)

- **Owner's decisions (2026-10-23):** a Gemini API key, kept as the Windows
  user variable `GEMINI_API_KEY` (in no project file); the first live run
  is one development case, golden-01, which accepts for this run that its
  passages, ICRC and WHO text included, go to Gemini's free tier (open item
  2 of the blueprint section); keep `gemini-3.8-flash`; no orthotic case
  goes to the cloud writer for now.
- **Key check, no project data sent** ("Reply with the single word OK."):
  `gemini-3.8-flash` answered 503 "currently experiencing high demand"
  twice and once not within 60 s, then "OK" after 114.6 s;
  `gemini-3.5-flash-lite` answered in 1.2 s. No request was refused for
  the machine's location, so from here the cloud writer is available (open
  item 1, in part).
- **Built:** `shared/config.py ORTHOTIC_CLOUD_AI = False`; in
  `reasoning/rag.py generate()` an orthotic case given a cloud writer
  (`reasoning/writer.py is_cloud()`: any `LLM_PROVIDER` writer) gets an
  offline one instead, whoever passes it (the app, the trial loader,
  `golden_cases --rag`): its page shows the passages without summaries and
  says why. Tests' fake writers are unaffected. 3 tests (495).
- **Run** (`data/eval/baseline/2026-10-23/live_golden01/`: script, the
  record and the output; real search, prompt rag-v2, the `--rag`
  measurements of `check_case`): 137 s for the case (the three parts in
  parallel: 93, 121 and 100 s, under Google's high demand); 17,152 input +
  20,100 output tokens; free tier.
  - **Quote check:** 28 items kept, 0 removed (no misquote).
  - **Answer-key checks:** statements, sources, reasoning path, functional
    level (`cms_k3_description`), gaps and excluded documents PASS.
    Coverage 5 of 34 expected statements (14%); 24 statements shown, 16 of
    them match no expected statement. All 4 gaps cite a passage (for
    `prior_devices` CMS p. 7, where the golden file, set from the topic-word
    check, expects none).
  - **"Must not show" WARN is a false alarm of the coverage rule:** the AI
    quoted ICRC p. 31, transtibial initial alignment, right for this
    transtibial case; ICRC's transfemoral sentence (p. 36,
    `icrc_tf_initial_alignment`) is the same but for "bench" and
    "transfemoral", so the 6-word rule (`COVER_WORDS`) credits the quote to
    both. Not changed: how the yardstick matches is the owner's call.
  - **Read by hand (all 28):** every sentence names its source; none
    advises about this patient in the AI's own voice, chooses or ranks.
    Three go beyond their quote: VA/DoD p. 57 drops "Evidence from three
    RCTs and one SR suggests" and states the finding as fact; CMS p. 7 adds
    "pre-authorization reports should document", from outside the quote;
    ICRC p. 31 turns "is carried out ... in accordance with a protocol" into
    "must follow". The sentence checks flagged 8 items (13 flags): "must" or
    "should" (most also in the quote), "يجب", and "transtibial" not in the
    quote (twice an accurate reading: a transtibial-socket review, and PTB
    and PTS sockets).
  - **Also seen:** two quotes shown twice under different topics (CMS's K3
    note under functional level and under preparatory or definitive;
    a socket-design sentence under socket and under fitting), and weak topic
    fits in those two. The Arabic is fluent, but one concept gets two
    terms: socket التجويف / المقبس, transtibial عبر القصبة / تحت الركبة,
    fitting التركيب and twice التثبيت ("fixing"): for the Arabic-reading
    prosthetist. ICRC's bullets show as "y" in its quotes (extraction).
- **Then fixed, same day** (owner: "do all necessary to make it work"; no
  new dependency, no commit; 504 tests, 9 new):
  1. *Trial report by domain:* `review/trial_report.py` counts one domain's
     decisions (default prosthetics, the trial's; `--domain orthotics` →
     `report_orthotics.csv`) and says how many on other domains it left out.
     Before, an orthotist's mark on `age_years`, `body_weight_kg`,
     `comorbidities` or `cognitive_status` (gap fields in both domains)
     landed in the prosthetic row, and an orthotic case could be listed
     among "gaps without a source marked Needed".
  2. *A changed option loses its choice:* `orthotics/plan.py set_options`
     keeps the choice only if the chosen option is still the same device
     with the same parts (new marks or notes keep it). Before, option A
     changed from a solid AFO to a posterior leaf spring stayed "chosen"
     with the reason written for the solid AFO. The review log keeps each
     choice as made.
  3. *Coverage rule:* `intake/golden_cases.py counted_for()` credits a RAG
     quote to the answer-key statement(s) of its document sharing the
     longest run of words (and any it holds whole), still needing
     `COVER_WORDS` = 6 in a row. Measured: 11 pairs of answer-key
     statements share a 6-word run (CMS K2/K3/K4 descriptions, VA/DoD
     recommendations 15/16/18/19, the ICRC alignment pair); a page rule
     was rejected because 22 statements also appear on other pages (VA/DoD
     prints each recommendation in its tables and its discussion). The
     first run re-measured offline: coverage 5 of 34 as before,
     must-not-show PASS. `intake.retrieval_misses` keeps the plain 6-word
     rule for its passages (a passage often holds several statements).
  4. *Prompt rag-v3* (`reasoning/rag.py FAITHFULNESS`, `ARABIC_TERMS`; the
     orthotic prompt is rag-ort-v2 with the same rule and its own terms):
     keep the source's hedges and strength, no "must" or "should" the quote
     doesn't have, nothing from outside the quote; the review page's Arabic
     word for each thing (22 prosthetic and 9 orthotic terms, each checked
     against `shared/i18n.py` in the tests).
  5. *Repeats:* `drop_repeats` shows a component or fitting quote once (a
     quote holding or held by one already shown under an earlier topic, same
     document); it is logged as `"dropped": "repeat"`, not a failed check,
     and the empty section says "the AI gave it only a quote that is already
     shown under an earlier section" (English and Arabic; term sheet
     re-exported, 561 rows, no corrections lost). `LOG_VERSION` 8.
- **Second live run** (golden-01, rag-v3, `gemini-3.8-flash`;
  `data/eval/baseline/2026-10-23/live_golden01_rag-v3/`): 240 s (parts
  127, 205 and 109 s, Google still reporting high demand); 18,073 input +
  25,108 output tokens; 25 items kept, 0 misquotes, 2 repeats removed (the
  CMS K3 note and the socket-design sentence, as in the first run);
  coverage 6 of 34 (17%); must-not-show PASS; answer-key checks PASS.
  - The three sentences of the first run: VA/DoD p. 57 now "notes that
    evidence suggests"; CMS p. 7 now says only what its quote says; ICRC
    p. 31 "is performed ... according to protocol", no "must".
  - Arabic, all 25 sentences: socket التجويف 8 times, المقبس 0 (first run 7
    and 7); transtibial تحت الركبة 3, عبر القصبة 0 (first run 3 and 3);
    التثبيت 0 (first run 2).
  - Still seen: ICRC p. 105 "need to be taught" became "must be taught";
    ICRC p. 91 names "transtibial" from the page's heading, outside the
    quote. The sentence checks flagged 6 of 25 items (first run 8 of 28),
    among them a false "numbers differ" ("3D" written ثلاثية الأبعاد).
- **Not done:** other cases, `--rag` on all development cases, the
  held-out cases, any orthotic case; Arabic read by a prosthetist.
- **Owner's decisions, end of the day (2026-10-23):**
  - *Test lines moved out of the review log*, as on 2026-10-09: the 2
    lines (an approve on case `db7a20c8262e`, 2026-10-13, and the run
    check's design choice on `a254f60fd4e6`) are now
    `data/review_log.test-2026-10-23.jsonl`, unchanged (SHA-256 identical,
    5EC5B020…469D); `data/review_log.jsonl` starts empty for the trial.
    The new file is protected by the yardstick hook like the other logs.
    `verify_all` check 1.8 passes again.
  - *Commit* everything on the branch `orthotics` (no push).

## Folder layout by part of the system (2026-10-24)

- **Asked (owner, 2026-10-24):** the target system is the owner's design in
  `docs/design/` (`SYSTEM_DESIGN.md` and 31 screens). The last changes were
  messy because the domains were inconsistent: orthotics was one package,
  prosthetics was spread over `intake/`, `reasoning/` and `shared/`. "Change
  the folder structure to be more normalised, tidy and convenient across all
  parts of the system: each file and folder related to a module in the
  corresponding module folder." Answers: tests inside each part; regroup
  `data/` by part; documents into `docs/`.
- **Moved (no behaviour change):**

  | Before | Now |
  |---|---|
  | `intake/routes.py` | `prosthetics/intake.py` (the form), `shared/forms.py` (the parsers, now public names: `choice`, `optional_number`, ...), `reasoning/pathway.py` (`analyse_case`) |
  | `intake/golden_cases.py`, `retrieval_misses.py`, `load_trial_cases.py`, `review/trial_report.py` | `quality/` (`python -m quality.golden_cases`, ...) |
  | `reasoning/component_guide.py`, `fitting_guide.py`, `component_support.py`, `fitting_support.py` | `prosthetics/` (the two guides with the owner's approval of the yardstick prompts); `cite()` to `reasoning/citations.py`, `recorded_value()` to `shared/case_schema.py` |
  | `shared/case_schema.py` `Case` and its enums; `OrthoticCase` and its enums | `prosthetics/case.py`, `orthotics/case.py`; the core (`CaseCore`, `Side`, `YesNoUnknown`, `PriorDevice`, `case_from_dict`) stays |
  | `shared/field_guide.py` `FIELDS`, `ORTHOTIC_FIELDS` | `prosthetics/fields.py`, `orthotics/fields.py` (each `FIELDS`, with `query_for()`); the mechanics stay |
  | `reasoning/rag_topics.py` prosthetic topics; `reasoning/rag.py` prosthetic prompt, `case_for_prompt`, `components_from`, `fitting_from` | `prosthetics/topics.py`, `prosthetics/rag.py` (`PROFILE`); the shared pipeline stays, `_statements` is now `statements_for` |
  | `orthotics/routes.py`; `orthotics/templates/*.html` | `orthotics/intake.py`; `orthotics/templates/orthotics/` (`intake_form`, `macros`, `map`, ...) |
  | `templates/ui_*.html`; `intake/templates/`; `review/templates/review.html` | `shared/templates/`; `prosthetics/templates/prosthetics/` (`intake_form`, `map`); `review/templates/review/review.html` |
  | `tests/` (one folder) | `<part>/tests/`; the helpers and `RouteTestCase` in `shared/testing.py`, the prosthetic route fixtures in `prosthetics/tests/helpers.py` |
  | `data/sources/`, `extracted/`, `vector_store/`, `eval/retrieval_queries.json`, `eval/orthotic_topics.json` | `data/knowledge/` (`sources/`, `extracted/`, `vector_store/`, `eval/`) |
  | `data/eval/golden_cases*`, `eval/baseline/`, `trial/` | `data/quality/` |
  | `data/cases/`, `data/review_log*.jsonl` | `data/records/` |
  | `SYSTEM_DESCRIPTION.md`, `FUTURE_WORK.md`, the blueprint, `AI-Prosthetic-Lab-System-Design/` | `docs/`, `docs/design/` |

- **The domain registry, `shared/domains.py`:** shared code no longer names a
  domain. `part(domain, "rag")` is `<domain>/rag.py`; each domain has the same
  files (`case.py`, `fields.py`, `topics.py`, `rag.py`, `intake.py`, and
  `plan.py` with `PLAN` if it has modules after the analysis). Each case
  class registers itself (`register_case`); `shared/store.py` reads a saved
  plan with the domain's `PLAN`. The prosthetic intake blueprint is now named
  `prosthetic_intake` (as `orthotic_intake`); URLs unchanged.
  `CODE_PACKAGES` in `shared/config.py` lists the packages the i18n key check
  and the Arabic term sheet scan. One domain name is still checked in shared
  code: `reasoning/rag.py generate()` keeps the orthotic cloud switch
  (`ORTHOTIC_CLOUD_AI`) as it was.
- **Checked:** 504 tests before and after, the same 4 failures both times
  (left by the uncommitted orthotics work of 2026-10-23 evening: three page
  texts and the `fu.back_to.` key; to be repaired next, at the owner's word),
  none skipped. Every page (76: the
  maps, both intake forms, the review page of each of the 9 saved cases and
  each orthotic module page, in English and Arabic) saved before the moves
  and after: byte for byte the same. The yardstick hook and its permission
  list name the new paths; the held-out hashes are of the cases' content, so
  they still match.
- **Left as written (records):** this file's earlier sections, the hand-offs,
  the blueprint and the measurement baselines name the old paths; the
  baseline scripts (`data/quality/baseline/*/*.py`) import `intake.*` and no
  longer run as they are. The golden cases' descriptions name the old guide
  paths (the held-out ones are frozen). `data/quality/trial/arabic_terms.csv`
  shows the old paths in "where it appears" until it is exported again.
- **Not done:** `shared/i18n.py` stays one table for every part:
  `python -m shared.arabic_terms apply` writes the Arabic reviewer's
  corrections back into that one file, and the reviewer checks one sheet.
  Splitting it per part is possible but changes that tool; the owner's call.

## Orthotic modules 1, 5, 6 and the hard stops (built 2026-10-23 evening, repaired 2026-10-24)

- **Built on 2026-10-23 evening, not recorded at the time** (committed with
  the folder layout in `4a492f8`): the rest of the design's orthotics screens.
  Module 1, the analysis page (goals by ICF level, the exam with how each
  value was measured, gait phase by phase, the information needed, the
  hard-stop checks); module 5, fit, tune and train (check-out, tuning,
  before and after, training plan, patient leaflet in Arabic and English);
  module 6, follow-up (visits, outcome measures, alerts that loop back,
  wearing and device, a summary for the physiotherapist); the fabrication
  sheet. The plan gained conflicts, the FES referral, the option cards'
  costs, checks at fitting and stock, simulation results and hot spots as
  entered, each parameter's basis and approval, and send to manufacture.
  Case file version 4, `LOG_VERSION` 9; golden-ort-01..03 gained the new
  case fields, all empty. Every value is the orthotist's (SYSTEM_DESIGN.md
  §11.7): the tool suggests no parameter.
- **Found wrong on 2026-10-24:** 4 tests failing; no tests for
  `orthotics/hard_stops.py`, `fit.py`, `followup.py` or the six new pages;
  these records not updated; the four hard stops labelled "the owner's
  rules" (citing an owner's decision of 2026-10-23 the owner says was not
  made); some of their lines stating clinical advice in the tool's own voice
  ("any rigid design needs pressure relief and lining"), against principle
  2; two pages headed as module 1; the option cards' part → requirement →
  finding trace cut down to "Serves R1".
- **Owner's answers (2026-10-24):** repair the work, don't discard it; the
  hard stops are "not yet" the owner's rules: keep them as drafts.
- **Repaired (2026-10-24):**
  - The 4 tests: the requirements test reads the requirement in its text box
    (the page shows it there, for the orthotist to change); the Arabic design
    page is checked for its own heading and the English one for the brief's
    Arabic name; the option cards show the trace again ("Serves R1 Clear
    the toes ← Swing: toe drag"), and the unmet-Must flag lost a stray
    space; the i18n key check skips a prefix a key is built from
    (`'fu.back_to.' ~ b`), as it already did for one-level prefixes.
  - Hard stops: every text says "draft rule, awaiting the owner's approval"
    (`hard.draft_rules` replaces `hard.owners_rules`), and every line quotes
    the draft rule instead of advising ("Recorded as reduced or absent. The
    draft rule is about a rigid device on insensate skin without pressure
    relief; the orthotist checks each design against it."). Checks, statuses
    and what triggers them unchanged.
  - One module 1: the analysis page; the review page is headed as the review
    step ("What the sources say, and your review · مراجعة المختص", the
    design's pathway step 05) and highlights no module tab.
  - 36 new tests (540 in all, every one passing): `orthotics/tests/
    test_hard_stops.py` (each rule's statuses, the option check, the draft
    wording, the pages' labels), `test_fit_followup.py` (dates, round trips,
    the next review due, values as entered, a version-3 plan read with
    modules 5-6 empty), `test_module_pages.py` (the six pages in English
    and Arabic, each form saved and refused, nothing sent to the AI, a
    version-3 case file and a version-8 log line still read). The orthotic
    page tests share `orthotics/tests/helpers.py`.
- **Owner's answers (2026-10-24, after the repair):** keep the golden-ort-01..03
  edits (the new case fields, all empty; no expectation changed); export the
  Arabic term sheet again: `data/quality/trial/arabic_terms.csv` now has all
  899 texts (it had 561, and no corrections, so nothing was lost), and
  `verify_prompts_0_2.py` check 2.1 passes.
- **Waiting on the owner:**
  1. The hard stops: approve, change or drop each draft rule. Once approved
     they go into a versioned clinic-rule file (plan Part 2), not code.
  2. As before: the vocabularies, fields, topics and wording of the
     orthotic drafts (an orthotist), the Arabic terms (an Arabic-reading
     orthotist, on the new sheet), and whether orthotic passages may go to
     the cloud model.

## Shared screen pieces, built once (plan Part 2, 2026-10-24)

- **Asked (owner, 2026-10-24):** "ensure this part is correct and then move to
  the next part". Part 0 was checked again first: its diff read line by line,
  every interface text searched for advice in the tool's own voice (none),
  every page requested from the real server (all 200), `verify_all.py`; one
  Arabic word fixed (draft rule: قاعدة … مسوّدة, not توقف … مسوّد).
- **Built (SYSTEM_DESIGN.md §5, "build them once and reuse them"):**
  1. *Building blocks:* `shared/requirements.py` (Requirement, Priority,
     Mark, Conflict), `shared/followup.py` (visits, outcome measures, alerts,
     moved from orthotics) and `shared/dates.py`. Where an orthotic alert may
     loop back to (`BACK_TO`) is checked by the orthotic plan. Saved plans read
     unchanged.
  2. *Page pieces:* `shared/templates/ui_macros.html`: status icons, a
     measured value's status, an information-needed item, the hard-stop
     banner and list, requirement chips, an option's marks, the unmet-Must
     flag, typed lists, evidence, passages, outcome charts, alerts, the
     latest visit, loop-back links. The orthotic pages use them: every page
     (102, with a fully filled fake case) rendered the same HTML before and
     after. The requirement and option edit forms stay in orthotics until
     prosthetics needs them (Part 3), so their shared shape is not guessed.
  3. *Header:* "AI Prosthetic Lab / <part>", the domain switch, the modules as
     numbered tabs, an EN | العربية pair with the current one marked (on an
     intake form the other is a button that posts the form, so nothing typed
     is lost; Enter still sends the case). Each domain says what its header
     shows in its own `nav.py` and `templates/<domain>/case_bar.html`; the
     header names no domain.
  4. *Clinic rules:* `data/knowledge/clinic_rules.csv` (owner's; the yardstick
     hook protects it): each rule's id, domain, kind, status (draft or
     approved), version, owner, approval date and source, read by
     `knowledge/clinic_rules.py`. The four orthotic hard stops are in it as
     drafts; `orthotics/hard_stops.py` attaches each rule's row to its check
     and refuses to run if the file and the code name different rules. The
     pages show each rule's status ("Draft rule, awaiting the owner's
     approval", or "Clinic rule, version N, approved by … on …") and the note
     under them follows: approving a rule is a change to that file only. The
     hard-stop texts no longer say "draft" themselves.
  5. *Shared code names no domain:* the cloud switch is each domain's RAG
     profile (`cloud_ai`, `ai_off_reason`; orthotics reads
     `ORTHOTIC_CLOUD_AI` at each run); what a case searches is its domain's
     `topics.py` (`SEARCH_DOMAINS`, `PASSAGES_PER_DOCUMENT`).
     `shared/tests/test_domains.py` checks that every domain has the same
     parts and that `shared/`, `knowledge/`, `reasoning/` and the shared
     templates never check a domain by name.
- **Left:** the review page (`review/routes.py`, `review.html`) still
  branches on orthotics; it is rebuilt with the prosthetic module pages
  (Part 3). Tests: 555, all passing.

## Prosthetic module pages (plan Part 3, 2026-10-24)

- **Asked (owner, 2026-10-24):** "start with Part 3". Owner's answers: add
  the design's three prosthetic hard stops as **drafts** in
  `data/knowledge/clinic_rules.csv` (open wound or infection; changing
  volume; neuropathic other foot); component options are **typed by the
  prosthetist** as free text, per the component categories already in the
  answer key, **no new vocabulary**.
- **Built** (SYSTEM_DESIGN.md §6.1; docs/SYSTEM_DESCRIPTION.md §4.10):
  1. *What both domains' module pages share, moved out of orthotics first*
     (every orthotic page renders the same HTML as before, 102 pages
     compared): the forms' parsers (`shared/forms.py`: typed values, tables,
     requirements, conflicts, follow-up), the pages' server side
     (`shared/module_pages.py`), the hard-stop check
     (`shared/hard_stops.py`), step statuses and gait phases
     (`shared/fitting.py`), a case finding and the requirement checks
     (`shared/requirements.py`), and the requirement, conflict and follow-up
     forms (`shared/templates/ui_forms.html`). Each domain's `nav.py` names
     its own words for the shared pieces (`WORDS`: who judges, whose marks,
     the stop banner, the draft note) and the review page's links
     (`REVIEW_BACK`, `REVIEW_NEXT`), so the review page no longer names
     orthotics for them.
  2. *`prosthetics/plan.py`* (`ProstheticPlan`): the intake's `Case` stays as
     it is (the golden cases are copies of `Case.to_dict()`), so module 1's
     extra values (how each was measured, joint range, strength, signs of
     infection, the other foot and the diabetic foot team, mobility
     measures, goals by ICF level, home and work setting) are in the plan,
     with the requirements, the component options per category, the
     configuration and reason, the fitting steps, observations, check-socket
     and alignment versions, and follow-up.
  3. *`prosthetics/hard_stops.py`*: the three rules as drafts, each shown
     with its status from the owner's file (approved by the owner's prompt
     on 2026-10-24); the other-foot rule only for a lower-limb case.
  4. *`prosthetics/modules.py`* and its templates: 1 Assess, 2–3
     Requirements & components (with `/configuration`), 4 Design & fitting
     (with the fabrication sheet), 5 Follow-up; the header's tabs, the map
     and the review page lead to them. What the sources say is the review
     page's AI summaries with their checked quotes, shown read-only.
  5. *Review log version 10*: a prosthetic case's `plan` and its
     configuration logged as a `design_choice`; older lines still read.
- **Left as it was, on purpose:** after the intake form a new prosthetic case
  still opens on the review page, the page the trial measures (orthotics
  opens module 1). The owner may want module 1 instead; the tests and the
  trial's flow rely on the review page today.
- **Waiting for the owner** (SYSTEM_DESIGN.md §11.2-11.3): approve, change or
  drop the three draft hard stops; the clinic's checklist before a
  definitive prosthesis (module 4 says it isn't set); alert thresholds,
  follow-up intervals, outcome measures with their "smallest real change"
  and questionnaires validated in Arabic (module 5 records the clinician's
  own). Module 1's extra values and the six fitting steps follow the design;
  a prosthetist should check them, and an Arabic-reading prosthetist the new
  Arabic texts (the term sheet was exported again, 1,082 texts).
- Tests: 580, all passing; `verify_all.py`: golden cases OK, checks 0-2 fail
  only on 0.3 (uncommitted changes). Committed `91d2f3b`, pushed (2026-10-25).

## Reasoning and review pages (plan Part 4, 2026-10-25)

- **Asked (owner, 2026-10-25):** "continue on to part 4". Owner's answers:
  commit and push Part 3 first (done, `91d2f3b`); add **both** "Summary is
  wrong" and a reason per gap mark (review log version 11); the release gate
  reads **recorded files**, with the owner's sign-off in
  `data/quality/releases.csv`, protected by the yardstick hook; the audit's
  "who" shows **"not recorded"** until there is a login (plan Part 8).
- **Built** (SYSTEM_DESIGN.md §7.2; docs/SYSTEM_DESCRIPTION.md §4.11):
  1. *A shared part in the header:* "Reasoning and review" next to the
     domains (`shared/domains.py` SHARED_PARTS, `review/nav.py`), with the
     tabs 1 Pathway, 2 Review (the latest case), 3 Quality and audit.
  2. *Pathway page* (`/reasoning`): the six steps and their guards, the
     "never outputs" list, the four checks each saying whether it is built
     here, and where data goes, read from the settings.
  3. *Review page, steps 05-06:* "Summary is wrong" for each AI summary, a
     reason with each gap mark, the decision in a side panel (approve as
     reviewed, approve with edits, reject the analysis) and one "Sign and
     record"; a decision without a choice is refused, the marks kept. Log
     version 11 adds `reviewer_reason`, `summary_wrong` and `versions`
     (prompt, models, library build: `knowledge/library.py`); older lines
     still read. The trial report counts the new mark and lists the gap
     reasons as written.
  4. *Quality page* (`/quality`): the measures, the audit trail and the
     release gate, read from `data/quality/results/runs.jsonl` (written by
     `scripts/verify_all.py --record`, which now also runs the unit tests,
     and `quality.golden_cases --record`), the review log, the case files
     and the owner's files; it runs nothing (`quality/results.py`,
     `releases.py`, `measures.py`).
  5. *Protected:* `data/quality/releases.csv` (created with its header only)
     and `data/quality/results/` were added to the yardstick hook.
- **Not built from the design:** the population check (a source's population
  comes only from the owner's values); showing the advice check's flags
  (measurement until the owner approves patterns); "who" in the audit trail
  (no login); a release candidate's name other than what the owner writes in
  releases.csv.
- **Next, when the owner wants:** run `python scripts/verify_all.py --record`
  on a committed tree so the quality page has its first recorded results; a
  held-out run only when the owner asks; the owner's first sign-off row.
- Tests: 603, all passing; checks 0-2 fail only on 0.3 (uncommitted changes);
  golden cases OK; the Arabic term sheet exported again (1,197 texts).

## Open decisions

- **Arabic sources are never cited in gap lists** (seen 2026-10-06).
  Investigated 2026-10-08 with a throwaway probe (four test cases,
  transtibial, transfemoral, transradial, transhumeral; 64 gaps; the
  app's own citation rule). Code alone can't fix it:
  - The cause is not that the English WHO edition wins: the English WHO
    documents are never cited either. All 200 citations in the 17 logged
    decisions come from five English documents (VA/DoD lower limb 94,
    VA/DoD upper limb 58, ML walking ability 25, phantom pain 14, socket
    shape capture 9).
  - The two Arabic WHO documents are about running a P&O service, not
    about assessing an amputee. With vowel marks removed they use
    البدلات about 900 times, but الطرف المتبقي (residual limb), socket
    and phantom 0 times, wound and edema 0-2 times.
  - Arabic field queries on the Arabic documents pass the rule for 42 of
    64 gaps, but read by hand the passages are false matches: الجلد is
    leather in a list of materials, هدف is the service's goal, العمر is
    "lifelong", حجم/شكل are measurements for a plaster cast, and the
    passage cited for sensation, wound and cause is about diabetic feet
    before amputation. Arabic queries instead of English ones also cut
    citations from 54 to 47.
  - Showing the Arabic twin of a cited WHO passage would add nothing,
    since no WHO passage is cited.
  - So the library needs Arabic text on assessing an amputee. Not found
    online: an Arabic edition of WHO's *Package of interventions for
    rehabilitation*, module 2 (2023, covers amputation;
    https://www.who.int/publications/i/item/9789240071100), or of the
    ICRC/WHO/AO limb-injury handbook (2016). Found: the MSD Manuals Arabic
    consumer pages on rehabilitation after amputation and on prostheses
    (peer-reviewed, updated 2026, use الطرف المتبقي and الطرف الاصطناعي;
    but consumer level, web pages without page numbers, "all rights
    reserved").
  - Before any Arabic source is added, the Arabic `topic_terms` in
    `shared/field_guide.py` need tightening for the double meanings
    above, or a clinical Arabic text will get the same false matches.
  - **Decided 2026-10-08:** build the Arabic UI instead (done, see above);
    Arabic citations wait for an Arabic clinical source.

## Known v1 simplifications (acceptable for now, revisit later if scope grows)

- `shared/store.py` keeps cases in memory and in one JSON file each
  (`data/cases/`, since 2026-10-09), single process, no concurrency
  handling. Fine for a local single-user prototype; would need a real store
  if this ever becomes multi-user.
- The intake form has three fixed prior-device rows (no JavaScript). A
  patient with more devices needs the rest in the intake notes; an "add
  device" button would need a little JavaScript.
- Review "edit" records a decision with a required note; it does not open
  an editable form for the case or the gap list itself. Revisit if
  reviewers need to actually correct case data, not just annotate a
  decision.
- After a decision is saved, the page's per-gap choices reset to "Not
  marked"; the logged-decisions list shows only counts ("2 needed, 1 not
  needed, …"). The full marks are in the log.
- The review log is read in full for each review page, and each 15-gap
  entry is about 26 KB. Fine for a local prototype; a database (or one
  file per case) would be needed for thousands of reviews.
- Tests (`python -m unittest`) cover the case schema, catalog, extraction,
  ingestion, retrieval, field guide, gap analysis, the review log and the
  pages; route tests write to a temporary log, never the real one. They use
  a tiny fake embedder (`tests/helpers.py`), so they never load the real
  model; the real model is checked by `python -m knowledge.evaluate`.
  Uses the standard library's `unittest`, so no extra dependency.
- ~~After a validation error, the intake form comes back empty.~~ Fixed
  2026-10-09 (Trial readiness 1).
- ~~Some intake error messages are Python's own wording.~~ Fixed
  2026-10-09: every intake error is a translated text with the field's label.
- Switching language on the review page reloads it, so an unsent note and
  marks are lost. (Fixed for the intake form 2026-10-09.)

## Path to the full system

The visual brief (09/2026) describes four domains — prosthetics, orthotics,
biomechanics/gait analysis, motor rehabilitation — and seven initial use
cases. v1 is use case 01 only. None of the items below should be built yet;
they're recorded so v1 choices don't block them.

- ~~**Other domains need other case data.**~~ The shared core is split off
  (2026-10-17, see "Product 6 and orthotics" above); each domain's case adds
  its own fields, and since 2026-10-24 each domain is its own package of the
  same shape (`shared/domains.py`).
- **Follow-up over time** (prosthetics follow-up, rehab progress, use case
  07) needs several cases linked to the same person. Today each case stands
  alone. Add a pseudonymous patient reference — still no real identifiers —
  and treat each visit as its own case.
- **Assistive recommendations** (pathway step 04, use case 02 component
  selection support): started 2026-10-08 as quoted guideline statements
  per component (see "Component selection support" above), with the
  disclaimer, banners and out-of-scope list revised; design and fitting
  added 2026-10-09 in the same form. The final decision still stays with
  the specialist.
- **Gait and motion data** (use case 04) is measured data over time, not
  form fields. It will need its own upload/intake path. It is also a
  regulatory boundary: FDA CDS guidance (2026) Criterion 1 excludes
  software that analyzes "patterns or signals from a signal acquisition
  system" from non-device decision support. Get regulatory advice
  before this goes beyond a prototype.
- **Smart search in the knowledge base** (use case 05) can reuse
  `knowledge/retrieval.py` directly, with its own page.
- **Training and education** (use case 06) can reuse the golden and trial
  cases (`data/quality/`) together with the review log.

## Explicitly out of scope for v1 (per original build spec — don't build)

- Treatment recommendations, and the system choosing or ranking
  components or judging readiness for fitting. (Revised 2026-10-08:
  component support may quote guideline statements word for word with
  their grade; 2026-10-09: the same for design and fitting statements. The
  specialist decides.)
- Auth, multi-user accounts, deployment config, cloud services (except
  the Claude API for the summaries, since 2026-10-11).
- Editing/removing already-logged review decisions.

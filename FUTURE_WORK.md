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

- **Rules, not a language model** (decided 2026-10-06). An LLM API call
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

- `shared/store.py` is an in-memory, single-process dict — no persistence
  across a server restart, no concurrency handling. Fine for a local
  single-user prototype; would need a real store if this ever becomes
  multi-user.
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
- After a validation error, the intake form comes back empty; the user has
  to retype everything, now including the device rows. Fix by passing the
  submitted values back into the template, as the review page already
  does for a refused decision.
- Some intake error messages are Python's own wording ("'banana' is not
  a valid AmputationLevel", "could not convert string to float"). The
  form's drop-downs and number inputs prevent most of them in a browser;
  friendlier wording per field would help if they show up in practice.
  They are not translated: the Arabic page shows them in English.
- Switching language reloads the page, so anything typed but not yet
  submitted is lost (the intake form, the review note and marks).

## Path to the full system

The visual brief (09/2026) describes four domains — prosthetics, orthotics,
biomechanics/gait analysis, motor rehabilitation — and seven initial use
cases. v1 is use case 01 only. None of the items below should be built yet;
they're recorded so v1 choices don't block them.

- **Other domains need other case data.** `Case` requires
  `amputation_level` and `side`, so it cannot hold an orthotics case.
  When a second domain starts, split it into a shared core (ids, timestamps,
  demographics, health context) plus one section per domain (prosthetic,
  orthotic, gait session, rehab plan), and give each use case its own module
  under `reasoning/`. Until then, keeping one `Case` is simpler.
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
- **Training and education** (use case 06) can reuse stored test cases from
  `data/test_cases/` together with the review log.

## Explicitly out of scope for v1 (per original build spec — don't build)

- Treatment recommendations, and the system choosing or ranking
  components or judging readiness for fitting. (Revised 2026-10-08:
  component support may quote guideline statements word for word with
  their grade; 2026-10-09: the same for design and fitting statements. The
  specialist decides.)
- Auth, multi-user accounts, deployment config, cloud services.
- Editing/removing already-logged review decisions.

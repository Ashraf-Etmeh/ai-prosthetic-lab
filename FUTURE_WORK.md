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

## Open decisions

- **Arabic UI.** The UI is English-only; Arabic quotes display
  right-to-left, the rest of the page doesn't.
- **Arabic sources are never cited in gap lists** (seen 2026-10-06, same
  four test cases). The field queries are English, and the two Arabic
  documents are the WHO P&O standards, whose English edition is also in
  the library, so the English text always scores higher. Arabic search
  itself works (6-7 of 8 evaluation queries). For an Arabic-reading
  reviewer, options are Arabic field queries (`shared/field_guide.py`),
  showing the Arabic twin of a cited WHO passage, or more Arabic-only
  sources.

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
  selection support) need a new output type next to `Gap`: an option with
  its rationale and source. The disclaimer in `shared/config.py`, the page
  banners, and the out-of-scope list below all say "missing information
  only"; they must be revised per feature when that changes. The final
  decision still stays with the specialist.
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

- Treatment or component recommendations of any kind.
- Auth, multi-user accounts, deployment config, cloud services.
- Editing/removing already-logged review decisions.

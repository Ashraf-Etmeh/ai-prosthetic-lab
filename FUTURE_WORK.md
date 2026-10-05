# Future Work / Open Decisions

Scratchpad so nothing gets lost between build steps. Update this file as
items are resolved instead of re-deriving them from scratch.

## Step 3 decisions (decided 2026-10-05)

- **Languages: Arabic and English, plus German** if it doesn't reduce
  accuracy. German costs nothing at the model level (every candidate
  multilingual model covers it). Measure the real effect with the
  evaluation set below, with and without the German documents.
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
- **Python 3.14: no new risk** with numpy + pypdf. `pypdf>=6,<7` is in
  `requirements.txt`; add `sentence-transformers` when embedding is built.
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
- **All 10 are English, text-based PDFs** (no scanned pages). There is
  no Arabic or German content yet, so the test set can't check those
  languages until such documents are added. Candidates found 2026-10-05
  (not downloaded; check licence and newer versions first):
  - German: AWMF S2k guideline 033-044, *Rehabilitation nach
    Majoramputation an der unteren Extremität* (2019), the German
    counterpart of the VA/DoD guideline:
    https://register.awmf.org/assets/guidelines/033-044l_S2k_Rehabilitation_Majoramputation-untere_Extremitaet_2019-09_01.pdf
    (AWMF guidelines are reviewed every 5 years; check the register for
    an update). Upper limb: 187-061 (2024):
    https://register.awmf.org/assets/guidelines/187-061l_S2k_Rehabilitation-Majoramputation-obere-Extremitaet-proximal-Hand_2024-08.pdf
  - Arabic: no Arabic clinical guideline found. The MSD Manual's
    consumer page on prosthetic options exists in Arabic and English
    with the same content, which suits a cross-language test (English
    query, Arabic passage):
    https://www.msdmanuals.com/ar/home/%D8%A7%D9%84%D9%85%D9%88%D8%B6%D9%88%D8%B9%D8%A7%D8%AA-%D8%A7%D9%84%D8%AE%D8%A7%D8%B5%D9%91%D9%8E%D8%A9/%D8%A7%D9%84%D8%A3%D8%B7%D8%B1%D8%A7%D9%81%D9%8F-%D8%A7%D9%84%D8%A8%D8%AF%D9%8A%D9%84%D8%A9-%D8%A3%D9%88-%D8%A7%D9%84%D8%A7%D8%B5%D8%B7%D9%86%D8%A7%D8%B9%D9%8A%D9%91%D9%8E%D8%A9/%D8%AE%D9%8A%D8%A7%D8%B1%D8%A7%D8%AA-%D8%A7%D9%84%D8%A3%D8%B7%D8%B1%D8%A7%D9%81-%D8%A7%D9%84%D8%A7%D8%B5%D8%B7%D9%86%D8%A7%D8%B9%D9%8A%D8%A9
    Save web pages as `.txt`.
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
- **Next: `knowledge/ingest.py`.** Read the pages back with
  `extract.read_extracted()`, chunk them (keep the page number per
  chunk), embed with bge-m3, save the `.npy` + `.json` store. Then the
  real search in `retrieval.py`, the domain filter, and the evaluation
  set.

## Open decisions

- **Who reads the German sources?** Retrieved chunks are shown to the
  reviewer as evidence; a German passage only helps a reader of German.
- **Reasoning approach (step 4).** Rules over `Case.unrecorded_fields()` and
  the retrieved text, or an LLM call that must cite the retrieved chunk ids.
  Either way, every `Gap.source_protocol_reference` must point at a chunk
  that was actually retrieved, so the specialist can check it.
- **Arabic UI.** The UI is English-only with no right-to-left support.
  Separate from retrieval; not needed for step 3.

## Deferred implementation (stubbed in step 2, real in later steps)

- `knowledge/retrieval.py` — `retrieve_relevant_chunks()` always returns one
  hardcoded `ProtocolChunk` regardless of the case. Real ingestion +
  similarity search lands in **step 3** (needs `knowledge/ingest.py`, not
  yet created).
- `reasoning/gap_analysis.py` — `analyze_gaps()` always returns one
  hardcoded `Gap`. Real logic (driven by `Case.unrecorded_fields()` plus the
  retrieved protocol chunks) lands in **step 4**.
- `review/decision_log.py` — `record_decision()` only prints to the
  console. Real JSON-lines persistence to
  `shared/config.py:REVIEW_LOG_PATH` (`data/review_log.jsonl`) lands in
  **step 5**. This is the brief's "documented outcome" step, so log enough
  to audit later: a snapshot of the case (`Case.to_dict()`), the gaps shown,
  the sources cited, and a timestamp. Consider recording a decision per gap,
  not only per case: specialist accept/reject per item is the feedback the
  knowledge layer's "specialist expertise" source can learn from. Also
  validate `decision`: `review/routes.py` currently accepts any string.
- `review/templates/review.html` — the retrieved chunks are passed to the
  template but not shown. Show them (or at least the cited ones) once step 3
  returns real text, so the reviewer can see the evidence behind each gap.
- Empty `data/sources/` handling (no crash, just no results) needs to be
  verified explicitly once step 3's ingestion script exists.

## Known v1 simplifications (acceptable for now, revisit later if scope grows)

- `shared/store.py` is an in-memory, single-process dict — no persistence
  across a server restart, no concurrency handling. Fine for a local
  single-user prototype; would need a real store if this ever becomes
  multi-user.
- The intake form's "prior devices" field isn't wired up yet — `Case.
  prior_devices` has no form input. Low priority since it's a list-of-objects
  field; add a repeating sub-form or simple textarea-per-line parser if
  needed before step 6's README claims full field coverage.
- Review "edit" currently just records a free-text note with the decision;
  it does not open an editable form for the case or the gap list itself.
  Revisit if reviewers need to actually correct case data, not just
  annotate a decision.
- Tests (`python -m unittest`) cover the case schema and the intake/review
  pages. The stubs aren't tested; add tests for retrieval and reasoning as
  steps 3 and 4 replace them. Uses the standard library's `unittest`, so no
  extra dependency.
- After a validation error, the intake form comes back empty; the user has
  to retype everything. Fix by passing the submitted values back into the
  template.

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
  form fields. It will need its own upload/intake path.
- **Smart search in the knowledge base** (use case 05) can reuse
  `knowledge/retrieval.py` directly, with its own page.
- **Training and education** (use case 06) can reuse stored test cases from
  `data/test_cases/` together with the review log.

## Explicitly out of scope for v1 (per original build spec — don't build)

- Treatment or component recommendations of any kind.
- Auth, multi-user accounts, deployment config, cloud services.
- Editing/removing already-logged review decisions.

# Future Work / Open Decisions

Scratchpad so nothing gets lost between build steps. Update this file as
items are resolved instead of re-deriving them from scratch.

## Open decisions (need an answer before step 3)

- **Vector store: Chroma vs FAISS.** Recommendation: **Chroma** — it persists
  to disk and stores each chunk's source document alongside its embedding,
  which `source_protocol_reference` in the gap output needs. FAISS is a
  lighter dependency but requires hand-rolling that id → source bookkeeping.
  Not yet confirmed by the user.
- **PDF parsing library.** The build spec says `data/protocols/` will hold
  `.txt` and `.pdf` files. Reading `.pdf` needs one more dependency beyond
  Flask/sentence-transformers/vector-store. Recommendation: **pypdf** (pure
  Python, no sub-dependencies). Not yet approved by the user — per the
  constraints, must ask before adding. If not approved, v1 ingestion should
  accept `.txt` only and skip `.pdf` with a warning.
- **Python version risk.** This machine runs Python 3.14.0, which is very
  new. `sentence-transformers` (via PyTorch) and/or Chroma may not have
  wheels for it yet. Needs to be checked when step 3 actually installs
  these. Fallback: a Python 3.12 virtual environment dedicated to this
  project.

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
  **step 5**.
- Empty `data/protocols/` handling (no crash, just no results) needs to be
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
- No tests directory yet. Consider adding basic tests once reasoning (step
  4) has real logic worth testing — the stub logic isn't worth testing.

## Explicitly out of scope for v1 (per original build spec — don't build)

- Treatment or component recommendations of any kind.
- Auth, multi-user accounts, deployment config, cloud services.
- Editing/removing already-logged review decisions.

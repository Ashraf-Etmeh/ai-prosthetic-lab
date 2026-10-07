# AI Prosthetic Lab — v1 prototype

First prototype of **AI Prosthetic Lab**, a specialised AI system for
prosthetics, orthotics and rehabilitation (see the visual brief, 09/2026).

This prototype covers one slice of the full system:

> **Use case 01 — analyse an amputation case and identify the information
> still needed before specialist evaluation.**

It is **decision support, not a replacement** for the specialist. It reports
missing information only; it does not diagnose or recommend treatment or
components. The final decision always stays with the specialist.

Fake/test data only. No patient identifiers (name, date of birth, address,
record numbers) are collected.

## How it follows the brief's reasoning pathway

| Brief pathway step          | Module                              | Status in v1                       |
|-----------------------------|-------------------------------------|------------------------------------|
| 01 Case data                | `intake/`, `shared/case_schema.py`  | Working: form, schema, validation  |
| 02 Information analysis     | `knowledge/`                        | Working: extraction, chunking, multilingual search (en/ar/de) |
| 03 Specialised reasoning    | `reasoning/gap_analysis.py`         | Working: rule-based, every gap cites a checkable passage or says none was found |
| 04 Assistive output         | `reasoning/models.py` (`Gap`)       | Working: gap list with quoted sources on the review page |
| 05 Specialist review        | `review/`                           | Working: approve / edit / reject   |
| 06 Documentation            | `review/decision_log.py`            | Stub: prints to console            |

The rest of the brief (orthotics, gait analysis, rehabilitation, component
selection support, follow-up) is planned but not started — see
[FUTURE_WORK.md](FUTURE_WORK.md#path-to-the-full-system).

## Running it

Requires Python 3.12+ (developed on 3.14).

```
pip install -r requirements.txt
python app.py
```

Then open http://127.0.0.1:5000. The first case you submit takes about
10 seconds while the search model loads; later cases take well under a
second. Build the search index first (below), or the review page will
warn that no sources were searched.

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

To check how well the search finds the right page, in English, Arabic and
German, with and without the German documents:

```
python -m knowledge.evaluate
```

## How a gap list is made

1. `shared/field_guide.py` lists the intake fields that can be gaps, with
   a search query and topic words (English, German, Arabic) for each.
2. For every field that is empty or recorded as unknown, retrieval
   searches the prosthetics documents for the case's limb (upper or lower).
3. The gap cites the best passage that is similar enough
   (`MIN_RELEVANCE_SCORE`) **and** mentions the field's topic, and quotes
   its sentences on that topic. If none passes, the gap says no source was
   found instead of citing a weak one.
4. The review page shows each gap with its quote, citation (title, year,
   page) and the other passages considered.

## Tests

```
python -m unittest
```

## Layout

```
app.py              Flask entry point; registers the intake and review pages
shared/             Case schema, config (paths, settings, disclaimer), in-memory store
intake/             Intake form -> Case -> runs knowledge + reasoning -> review page
knowledge/          Source catalog, text extraction, ingestion, search, evaluation
reasoning/          Gap analysis: what information is missing, and which source says why
review/             Specialist review page and decision log
tests/              unittest suite (uses a tiny fake embedder, not the real model)
data/sources/       Knowledge documents: catalog.json in git, the PDFs kept local
data/extracted/     Cleaned text per document (generated, not in git)
data/vector_store/  Chunks and their vectors (generated, not in git)
data/eval/          Retrieval evaluation queries (in git)
```

## Plan and open decisions

[FUTURE_WORK.md](FUTURE_WORK.md) tracks the build steps, open decisions and
known simplifications.

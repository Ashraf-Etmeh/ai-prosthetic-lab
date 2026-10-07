# Knowledge sources

Everything collected for the project: the documents the knowledge layer
searches, plus references and datasets kept for later use cases.

```
00_registry/              sources_manifest.csv: every source (also failed or
                          link-only ones) with URL, licence and status;
                          fetch_figshare_data.py downloads the datasets;
                          the source-verification report
01_guidelines/            clinical practice guidelines and standards
02_evidence_reviews/      systematic reviews and studies
03_outcome_measures/      outcome-measure toolkits and reviews
04_ai_safety_regulation/  AI safety and medical-device regulation (not searched)
05_datasets/              gait datasets with their papers (not searched)
catalog.json              which documents ingestion reads, and their metadata
```

Files are named `<manifest id>_<Author or body><year>_<topic>.pdf`, for
example `G01_VADoD_2024_Lower_Limb_Amputation_CPG.pdf`. The id at the
front is the file's row in `00_registry/sources_manifest.csv`, which records
where it came from and its licence.

Only `catalog.json`, the manifest, the download script, the verification
report and this README are in git (see `.gitignore`). The documents and
datasets stay local: several documents are under publisher copyright and
the datasets are many GB. The manifest lists where to download each one.

## Manifest and catalog

- **`00_registry/sources_manifest.csv`** records *acquisition*: every source,
  where it came from, its licence, and whether it was downloaded.
- **`catalog.json`** records *ingestion*: which documents the system reads,
  with the citation shown to the reviewer, the domains and the language.
  Folders `00_registry`, `04_ai_safety_regulation` and `05_datasets` are
  never ingested (`shared/config.py: SOURCES_NOT_INGESTED`).

## Adding a document

1. Put the file (`.pdf` or `.txt`) in the matching folder, named as above.
2. Add a row to `00_registry/sources_manifest.csv` (licence: write
   "not shown" if the document doesn't state one).
3. Add an entry to `catalog.json`.
4. Run `python -m knowledge.extract` and open
   `data/extracted/<id>.txt` to check the text came out right.

Prefer the publisher's PDF over a web page printed to PDF: printed pages
repeat the print date and title on every page, and their page numbers don't
match the published article, so citations can't be checked.

For Arabic sources, prefer a `.txt` copy if the PDF's text comes out
broken (letters in the wrong order or shape).

## Catalog fields

| Field | Meaning |
|---|---|
| `id` | Permanent name. Chunk ids are built from it (`<id>-0042`), and saved review decisions point at those. **Never change it after the first ingestion**, even if the file is renamed. |
| `file` | Path relative to this folder. |
| `title`, `authors`, `year`, `publisher` | Shown to the reviewer as the citation. |
| `doi` / `url` | Where to get the document. `null` if none. |
| `notes` | Optional. |
| `source_type` | One of the brief's six: `protocol`, `scientific_reference`, `professional_knowledge`, `applied_case`, `structured_data`, `specialist_expertise`. |
| `domains` | One or more of: `prosthetics`, `orthotics`, `gait`, `rehabilitation`. v1 (use case 01) searches `prosthetics` only. |
| `language` | `en`, `ar` or `de`. |
| `limbs` | Optional. `["lower"]`, `["upper"]` or both: which amputations the document is about. An upper-limb case never cites a `["lower"]`-only document. Leave it out if the document isn't limb-specific. |

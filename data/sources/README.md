# Knowledge sources

The documents the knowledge layer searches. Ingestion (step 3) reads
`catalog.json` and only ingests the files listed there; anything else is
skipped with a warning.

The documents (`.pdf` and `.txt`) are not in git (see `.gitignore`):
several are under publisher copyright. `catalog.json` is in git, with the
DOI or web address of each document so it can be downloaded again.

## Adding a document

1. Put the file (`.pdf` or `.txt`) in the matching folder, named
   `topic_words_year.pdf`: lowercase, underscores, no spaces.
2. Add an entry to `catalog.json`.
3. Run `python -m knowledge.extract` and open
   `data/extracted/<id>.txt` to check the text came out right.

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

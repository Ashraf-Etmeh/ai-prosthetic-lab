"""Prosthetics: use cases 01 (analyse an amputation case) and 02 (component selection from the functional level).

The prosthetic case shares everything else with the other domains: the case
core (shared/case_schema.py), the field guide's mechanics, the search, the AI
writer and its word-for-word quote check (reasoning/rag.py, through this
domain's PROFILE), the case store, the review page and the review log.

- case.py: the prosthetic case (`Case`).
- fields.py: the gap fields and how each is searched.
- topics.py: what a prosthetic case searches for and asks the AI about.
- rag.py: the prosthetic instructions and the page's sections.
- component_guide.py, fitting_guide.py: the 59 hand-written statements, now the
  answer key the RAG is measured against (quality/golden_cases.py).
- component_support.py, fitting_support.py: those statements applied to a case.
- intake.py: GET/POST /intake, the prosthetic intake form, and /prosthetics, the map.
"""

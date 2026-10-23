"""Orthotics: use case 03 of the visual brief, stroke ankle-foot orthosis first (built 2026-10-22).

Owner's decisions: start orthotics before the trial, stroke AFO first
(2026-10-16); build Claude's proposal as a draft, cover the case analysis,
missing information, what the sources say about the orthosis options and
about design and fitting, with the orthotist's choice in the review log
(2026-10-22). The intake fields, which are critical, the topics and the golden
cases are a PROPOSAL awaiting the owner's and an orthotist's review.

The orthotic case shares everything else with prosthetics: the case core
(shared/case_schema.py OrthoticCase), the field guide's mechanics
(shared/field_guide.py ORTHOTIC_FIELDS), the search, the AI writer and its
word-for-word quote check (reasoning/rag.py, through a profile), the case
store, the review page and the review log.

- topics.py: what an orthotic case searches for and asks the AI about.
- rag.py: the orthotic instructions and the page's sections.
- routes.py: GET/POST /intake/orthotics, the orthotic intake form.
"""

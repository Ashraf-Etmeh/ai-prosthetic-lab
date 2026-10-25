"""What the shared header shows for the reasoning and review part (shared/templates/ui_header.html; SYSTEM_DESIGN.md
§7.2; docs/design/07-reasoning-and-review/; plan Part 4, 2026-10-25).

A shared part, not a clinical domain (shared/domains.py SHARED_PARTS): its pages are the pathway and its guards,
the latest case's review page, and quality and audit. A case's own review page keeps its domain's header.
"""

MAP = "review.pathway"  # the part's first page
# Its pages as numbered tabs: (key, endpoint, anchor); the tab's label is the interface text LABELS + key.
MODULES = (("pathway", "review.pathway", ""), ("review", "review.latest", ""), ("quality", "review.quality", ""))
LABELS = "rmod."

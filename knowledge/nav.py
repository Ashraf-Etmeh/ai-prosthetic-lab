"""What the shared header shows for the knowledge layer (shared/templates/ui_header.html; SYSTEM_DESIGN.md §7.1;
docs/design/06-knowledge-layer/; plan Part 5, 2026-10-25).

A shared part, not a clinical domain (shared/domains.py SHARED_PARTS): the source library and ingestion, evidence
and curation (read-only: the owner's rules and values), and the graph and expertise.
"""

MAP = "knowledge.sources"  # the part's first page
# Its pages as numbered tabs: (key, endpoint, anchor); the tab's label is the interface text LABELS + key.
MODULES = (("sources", "knowledge.sources", ""), ("evidence", "knowledge.evidence", ""),
           ("graph", "knowledge.graph", ""))
LABELS = "kmod."

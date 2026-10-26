"""What the shared header shows for search and education (shared/templates/ui_header.html; SYSTEM_DESIGN.md §7.3;
docs/design/08-search-and-education/; plan Part 6, 2026-10-25).

A shared part (shared/domains.py SHARED_PARTS). Smart search is built; case-based learning (use case 06) is a
later part and gets its tab then.
"""

MAP = "search.smart_search"  # the part's first page
# Its pages as numbered tabs: (key, endpoint, anchor); the tab's label is the interface text LABELS + key.
MODULES = (("search", "search.smart_search", ""),)
LABELS = "smod."

"""What the shared header shows for search and education (shared/templates/ui_header.html; SYSTEM_DESIGN.md §7.3;
docs/design/08-search-and-education/; plan Part 6, 2026-10-25).

A shared part (shared/domains.py SHARED_PARTS): smart search (use case 05, Part 6) and case-based learning (use
case 06, Part 7, search/learning_routes.py).
"""

MAP = "search.smart_search"  # the part's first page
# Its pages as numbered tabs: (key, endpoint, anchor); the tab's label is the interface text LABELS + key.
MODULES = (("search", "search.smart_search", ""), ("learning", "learning.library", ""))
LABELS = "smod."

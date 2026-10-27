"""What the shared header shows for rehabilitation (shared/templates/ui_header.html; SYSTEM_DESIGN.md §6.4;
docs/design/05-rehabilitation/; plan Part 9, 2026-10-27).

Listed with the shared parts (shared/domains.py SHARED_PARTS), first, next to the domains: rehabilitation works on
a case of either domain and has no intake of its own. Its four tabs open a case's pages when a case is open (the
page passes part_args with its id); without one they say a case is needed.
"""

MAP = "rehab.map"  # the part's first page: what it does, and the cases to open
# Its pages as numbered tabs: (key, endpoint, anchor); the tab's label is the interface text LABELS + key.
MODULES = (("plan", "rehab.plan", ""), ("progress", "rehab.progress", ""), ("training", "rehab.training", ""),
           ("team", "rehab.team", ""))
LABELS = "rehmod."
NEEDS_CASE = "rehmod.needs_case"  # the tabs' hint before a case is open

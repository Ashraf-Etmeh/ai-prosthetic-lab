"""What the shared header shows for gait analysis (shared/templates/ui_header.html; SYSTEM_DESIGN.md §6.3;
docs/design/04-gait-analysis/; plan Part 10, 2026-10-27).

Listed with the shared parts (shared/domains.py SHARED_PARTS), first, next to the domains: gait analysis works on a
case of either domain and has no intake of its own. Its four tabs open a case's pages when a case is open (the page
passes part_args with its id); without one they say a case is needed.
"""

MAP = "gait.map"  # the part's first page: what it does, the prototype's decisions, the cases to open
# Its pages as numbered tabs: (key, endpoint, anchor); the tab's label is the interface text LABELS + key.
MODULES = (("capture", "gait.capture", ""), ("interpret", "gait.interpret", ""),
           ("indicators", "gait.indicators", ""), ("compare", "gait.compare", ""))
LABELS = "gmod."
NEEDS_CASE = "gmod.needs_case"  # the tabs' hint before a case is open

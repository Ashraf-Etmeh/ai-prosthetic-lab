"""What the shared header shows for the system map (shared/templates/ui_header.html; SYSTEM_DESIGN.md §3 and §9;
docs/design/01-system-map/; plan Part 11, 2026-10-27).

The home of the app (/): reached from the header's brand, not listed in the switch between the parts
(shared/domains.py HOME).
"""

MAP = "index"  # the app's home, /
# Its pages as numbered tabs: (key, endpoint, anchor); the tab's label is the interface text LABELS + key.
MODULES = (("map", "index", ""), ("architecture", "overview.architecture", ""))
LABELS = "omod."
# The brief's use cases and the part each lives in (SYSTEM_DESIGN.md §3).
USE_CASES = (("01", "prosthetics"), ("02", "prosthetics"), ("03", "orthotics"), ("04", "gait"), ("05", "search"),
             ("06", "search"), ("07", "record"))

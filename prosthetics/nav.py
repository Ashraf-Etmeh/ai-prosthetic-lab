"""What the shared header shows for prosthetics (shared/templates/ui_header.html, through shared/domains.py).

The design's four modules (docs/design/02-prosthetics/; plan Part 3, 2026-10-24), each a page of
prosthetics/modules.py. The review page (what the sources say, and the specialist's marks) is reached from
module 1 and is no module of its own.
"""

MAP = "prosthetic_intake.prosthetics_map"  # the domain's map page
INTAKE = "prosthetic_intake.show_form"  # the first tab before there is a case
# The modules as numbered tabs: (key, endpoint, anchor); the tab's label is the interface text LABELS + key.
MODULES = (("assess", "prosthetic_modules.assess", ""), ("components", "prosthetic_modules.components", ""),
           ("fitting", "prosthetic_modules.fitting", ""), ("follow_up", "prosthetic_modules.follow_up", ""))
LABELS = "pmod."
DECIDES = "pmod.prosthetist_decides"  # the case bar's "Decision support: the prosthetist decides"
APPROVES: dict[str, str] = {}  # a module where the specialist approves each step instead: its own words
CASE_BAR = "prosthetics/case_bar.html"  # the case bar's one-line summary of the case
# The shared pieces' text slots in this domain's words (shared/templates/ui_macros.html word()).
WORDS = {"judge": "phard.judge", "stop_banner": "phard.stop_banner", "draft_rules": "phard.draft_rules",
         "addresses": "pcomp.addresses", "unaddressed": "pcomp.unaddressed", "needs_case": "pmod.needs_case"}
# The review page's links (review/templates/review/review.html): back to module 1, and on: (endpoint, text key).
REVIEW_BACK = ("prosthetic_modules.assess", "pmod.to_assess")
REVIEW_NEXT = ("prosthetic_modules.components", "pmod.to_components")

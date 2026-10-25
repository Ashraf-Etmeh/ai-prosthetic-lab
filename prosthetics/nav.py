"""What the shared header shows for prosthetics (shared/templates/ui_header.html, through shared/domains.py).

The prosthetic modules are the review page's sections so far (one decision form
marks them all), so the tabs link to those sections; plan Part 3 makes them
pages of their own (docs/design/02-prosthetics/).
"""

MAP = "prosthetic_intake.prosthetics_map"  # the domain's map page
INTAKE = "prosthetic_intake.show_form"  # the first tab before there is a case
# The modules as numbered tabs: (key, endpoint, anchor); the tab's label is the interface text LABELS + key.
MODULES = (("evaluate", "review.show_case", "#gaps"), ("functional", "review.show_case", "#functional"),
           ("components", "review.show_case", "#components"), ("fitting", "review.show_case", "#fitting"))
LABELS = "pmod."
DECIDES = "pmod.specialist_decides"  # the case bar's "Decision support: the ... decides"
APPROVES: dict[str, str] = {}  # a module where the specialist approves each step instead: its own words
CASE_BAR = "prosthetics/case_bar.html"  # the case bar's one-line summary of the case

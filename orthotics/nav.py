"""What the shared header shows for orthotics (shared/templates/ui_header.html, through shared/domains.py)."""

MAP = "orthotic_modules.module_map"  # the domain's map page
INTAKE = "orthotic_intake.show_form"  # the first tab before there is a case
# The six modules as numbered tabs: (key, endpoint, anchor); the tab's label is the interface text LABELS + key.
MODULES = (("analyse", "orthotic_modules.analysis", ""), ("requirements", "orthotic_modules.requirements", ""),
           ("options", "orthotic_modules.options", ""), ("design", "orthotic_modules.design", ""),
           ("fit", "orthotic_modules.fit", ""), ("follow_up", "orthotic_modules.follow_up", ""))
LABELS = "mod."
DECIDES = "mod.orthotist_decides"  # the case bar's "Decision support: the orthotist decides"
APPROVES = {"design": "mod.orthotist_approves"}  # module 4: the orthotist approves each step
CASE_BAR = "orthotics/case_bar.html"  # the case bar's one-line summary of the case

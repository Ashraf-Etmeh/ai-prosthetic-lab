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
# The shared pieces' text slots in this domain's words (shared/templates/ui_macros.html word()).
WORDS = {"judge": "hard_status.judge", "stop_banner": "hard.stop_banner", "draft_rules": "hard.draft_rules",
         "addresses": "options.addresses", "unaddressed": "options.unaddressed", "needs_case": "mod.needs_case"}
# The review page's links (review/templates/review/review.html): back to module 1, and on: (endpoint, text key).
REVIEW_BACK = ("orthotic_modules.analysis", "review.to_analysis")
REVIEW_NEXT = ("orthotic_modules.requirements", "review.to_requirements")
# The patient record's timeline (record/timeline.py; plan Part 8): the plan's versioned records (plan field, text
# key, page), and the pages a design choice and a follow-up visit open.
RECORD_VERSIONS = (("parameter_versions", "rec_ev.parameter_version", "orthotic_modules.design"),)
RECORD_CHOICE = "orthotic_modules.options"
RECORD_FOLLOW_UP = "orthotic_modules.follow_up"

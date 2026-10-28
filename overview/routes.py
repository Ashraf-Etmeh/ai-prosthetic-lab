"""The system map (SYSTEM_DESIGN.md §3, §4, §9; docs/design/01-system-map/; plan Part 11, 2026-10-27).

GET /              1 System map: the clinical domains and the parts on a case, the shared parts, each with its own
                   module tabs (from its nav.py); the brief's use cases and where each lives; what waits for the
                   owner, counted from the owner's files; the roll-out; the rules every part keeps
GET /architecture  2 Architecture: the six layers, one answer end to end (the step outside the clinic, as the
                   settings say now), adding a domain, who owns what, the owner's open questions as they stand

Everything shown about the system's state is read from the files and settings the code follows, never written here.
"""

from dataclasses import dataclass
from typing import Optional

from flask import Blueprint, render_template, request

from gait import rules as gait_rules
from knowledge.clinic_rules import load_rules
from overview import nav as overview_nav
from quality.releases import load_releases
from record import governance
from search import learning
from shared import config, domains
from shared.i18n import t

bp = Blueprint("overview", __name__, template_folder="templates")


@dataclass(frozen=True)
class Waiting:
    """One kind of value the owner sets: how many there are, how many are still drafts or not set, and where."""

    key: str  # its text key, "owait.<key>"
    drafts: int
    total: int
    endpoint: str  # the page that shows it
    args: Optional[dict] = None


def waiting_for_owner() -> list[Waiting]:
    """Counted from the owner's files as they are now."""
    rules = load_rules()
    thresholds = gait_rules.load_thresholds()
    roles = governance.load_roles()
    retention = governance.load_retention()
    try:
        teaching = learning.load_teaching_cases()
    except learning.TeachingCaseError:
        teaching = []
    return [
        Waiting("clinic_rules", sum(1 for r in rules if not r.approved), len(rules), "knowledge.graph"),
        Waiting("gait_thresholds", sum(1 for t in thresholds if not t.approved), len(thresholds), "gait.map"),
        Waiting("gait_references", 0 if gait_rules.load_references() else 1, 1, "gait.map"),
        Waiting("roles", sum(1 for r in roles if r.status != governance.APPROVED), len(roles), "record.governance"),
        Waiting("retention", sum(1 for s in retention.values() if not s.value), len(retention), "record.governance"),
        Waiting("teaching_cases", sum(1 for c in teaching if c.status == "draft"), len(teaching), "learning.library"),
        Waiting("releases", 0 if load_releases() else 1, 1, "review.quality"),
    ]


def _part(name: str) -> dict:
    nav = domains.nav(name)
    return {"name": name, "map": nav.MAP, "labels": [nav.LABELS + key for key, _, _ in nav.MODULES],
            "is_domain": name in domains.DOMAINS}


def _page(template: str, module: str, **context):
    # t_ar: a part's Arabic name under its English one, as the design's map shows it.
    return render_template(template, part=domains.HOME, module=module, here=request.path, case=None,
                           t_ar=lambda key: t(key, "ar"), **context)


def system_map():
    """The app's home (app.py index)."""
    clinical = [_part(d) for d in (*domains.DOMAINS, *domains.CASE_PARTS)]
    shared = [_part(p) for p in domains.SHARED_PARTS if p not in domains.CASE_PARTS]
    return _page("overview/map.html", "map", clinical=clinical, shared=shared, use_cases=overview_nav.USE_CASES,
                 waiting=waiting_for_owner(), clouds=governance.cloud_uses())


@bp.route("/architecture", methods=["GET"])
def architecture():
    return _page("overview/architecture.html", "architecture", clouds=governance.cloud_uses(),
                 provider=config.LLM_PROVIDER, all_parts=[*domains.DOMAINS, *domains.SHARED_PARTS])

"""The knowledge layer's pages (SYSTEM_DESIGN.md §7.1; docs/design/06-knowledge-layer/; plan Part 5, 2026-10-25).

GET /knowledge            1 Sources: every document with its kind, language, licence as recorded, what
                          extraction did to its text and its status; the steps from document to search; what
                          needs a curator (?kind=<source type> and ?q=<words> narrow the list)
GET /knowledge/evidence   2 Evidence: the knowledge items with why each may need a curator, one item's quote, grade
                          as printed and evidence fields with the owner's rule that set them (?item=, ?reason=),
                          and the owner's rule table, all read-only (owner's answer, 2026-10-25: values come only
                          from the owner's rule table or values the owner gives, CLAUDE.md)
GET /knowledge/graph      3 Graph and expertise: the clinic rules with their status, the Arabic term sheet's state,
                          and what is not built yet (the design knowledge graph, the glossary's statuses, the case
                          library, structured data: owner's answer, 2026-10-25, "show what exists")

Facts only: nothing here rates a source, an item or a rule. Nothing is written.
"""

from flask import Blueprint, render_template, request

from knowledge import library
from knowledge.catalog import SOURCE_TYPES
from knowledge.clinic_rules import load_rules as load_clinic_rules
from knowledge.evidence_rules import load_rules as load_evidence_rules
from knowledge.items import read_items
from knowledge.models import UNASSIGNED, VALIDATION_STATUSES
from quality import results
from quality.releases import latest_release
from shared import config
from shared.i18n import TEXT

bp = Blueprint("knowledge", __name__, template_folder="templates")

PART = "knowledge"
# Why an item may need a curator (interface texts "kreason.<reason>"), in the order shown.
NO_RULE, LAYER_UNASSIGNED, POPULATION_NOT_SET, PRACTICE = "no_rule", "layer_unassigned", "population_not_set", "practice"
REASONS = (NO_RULE, LAYER_UNASSIGNED, POPULATION_NOT_SET, PRACTICE)
# The catalog's kinds of source, in the design's order (interface texts "source_type.<kind>").
KINDS = ("scientific_reference", "protocol", "professional_knowledge", "applied_case", "structured_data",
         "specialist_expertise")
assert set(KINDS) == set(SOURCE_TYPES)


def _page(template: str, module: str, **context):
    return render_template(template, part=PART, module=module, here=request.full_path.rstrip("?"), case=None,
                           **context)


@bp.route("/knowledge", methods=["GET"])
def sources():
    rows = library.library_rows()
    kind = request.args.get("kind") if request.args.get("kind") in KINDS else None
    words = (request.args.get("q") or "").strip()
    shown = [row for row in rows if (kind is None or row.source_type == kind)
             and (not words or words.lower() in " ".join([row.title, *row.domains, row.licence or ""]).lower())]
    catalogued = [row for row in shown if row.doc_id]
    searches = [run for run in results.read_runs() if run.get("kind") == results.SEARCH_QUALITY]
    version = library.library_version()
    return _page("knowledge/sources.html", "sources", kinds=KINDS, kind=kind, words=words, version=version,
                 catalogued=catalogued, others=[row for row in shown if not row.doc_id],
                 counts={k: sum(1 for row in rows if row.source_type == k) for k in KINDS},
                 total=sum(1 for row in rows if row.doc_id),
                 queue=library.curator_queue(rows, searches, version), last_search=searches[-1] if searches else None)


def topic_key(topic: str) -> str:
    """The interface text naming an item's topic: a component, a design and fitting section, or the functional level."""
    for key in (f"component.{topic}", f"fitting_section.{topic}"):
        if key in TEXT:
            return key
    return "functional.heading" if topic == "functional_level" else "kev.other_topic"


def item_reasons(item) -> list[str]:
    """Why an item may need a curator: facts about its fields, never a judgement of the item."""
    reasons = []
    if item.assigned_by in ("none", ""):
        reasons.append(NO_RULE)
    elif item.evidence_layer == UNASSIGNED:
        reasons.append(LAYER_UNASSIGNED)
    if not item.population:
        reasons.append(POPULATION_NOT_SET)
    if item.source_type == "professional_knowledge":
        reasons.append(PRACTICE)
    return reasons


@bp.route("/knowledge/evidence", methods=["GET"])
def evidence():
    items = read_items(config.KNOWLEDGE_ITEMS_PATH)
    rules = load_evidence_rules()
    reasons = {item.knowledge_id: item_reasons(item) for item in items}
    reason = request.args.get("reason") if request.args.get("reason") in REASONS else None
    listed = [item for item in items if reason is None or reason in reasons[item.knowledge_id]]
    chosen = next((item for item in items if item.knowledge_id == request.args.get("item")), None)
    chosen = chosen or (listed[0] if listed else None)
    return _page("knowledge/evidence.html", "evidence", items=listed, all_items=len(items), reasons=reasons,
                 reason=reason, reason_keys=REASONS, chosen=chosen,
                 reason_counts={r: sum(1 for found in reasons.values() if r in found) for r in REASONS},
                 rules=rules, rule_items={rule.rule_id: sum(1 for item in items if item.assigned_by == rule.rule_id)
                                          for rule in rules},
                 rule=next((r for r in rules if chosen and r.rule_id == chosen.assigned_by), None),
                 unassigned=UNASSIGNED, topic_keys={item.topic: topic_key(item.topic) for item in items},
                 statuses=VALIDATION_STATUSES)


@bp.route("/knowledge/graph", methods=["GET"])
def graph():
    release = latest_release()
    return _page("knowledge/graph.html", "graph", clinic_rules=load_clinic_rules(), texts=len(TEXT),
                 term_sheet=(config.TRIAL_DIR / "arabic_terms.csv").relative_to(config.PROJECT_ROOT).as_posix(),
                 arabic_checked=release if release and release.arabic_checked else None)

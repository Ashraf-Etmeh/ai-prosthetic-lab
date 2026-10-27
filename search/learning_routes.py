"""The case-based learning pages (use case 06; docs/design/08-search-and-education/Learning.html; plan Part 7,
2026-10-25).

GET  /learn                     the case library (each case's status and the level the educator set), my learning
                                log (cases worked, CPD time recorded), the CPD export
POST /learn/<case>/start        a new attempt at a teaching case, then its step 1
GET  /learn/attempt/<id>        ?step=read|missing|options|compare|reflect: one step of the attempt
POST /learn/attempt/<id>        action "missing", "options" or "reflect" (the last adds it to the learning log)
GET  /learn/log.csv             the CPD record, one row per case worked

The compare step shows, item by item, the learner, the expert panel (when the educator has recorded its
answers) and the source the local search found; for a gap the learner did not mark, what the sources say about
it (the case's own analysis: the local search and the AI with checked quotes, run once and kept, as for any case
of its domain; owner's answer, 2026-10-25). It never grades: it shows where the learner and the panel differ.
"""

from typing import Optional

from flask import Blueprint, Response, abort, current_app, redirect, render_template, request, url_for

from reasoning.pathway import analyse_case
from search import learning
from shared import config, domains
from shared.case_schema import recorded_value
from shared.field_guide import missing_fields
from shared.i18n import TranslatableError, language_from_cookies
from shared.store import CaseRecord, CaseStore

bp = Blueprint("learning", __name__, template_folder="templates")


def _teaching_case(case_id: str) -> learning.TeachingCase:
    case = learning.teaching_case(case_id)
    if case is None:
        abort(404)
    return case


def _attempt(attempt_id: str) -> tuple[learning.Attempt, learning.TeachingCase]:
    attempt = learning.get_attempt(attempt_id)
    if attempt is None:
        abort(404)
    return attempt, _teaching_case(attempt.case_id)


def _fields(case: learning.TeachingCase):
    return domains.part(case.domain, "fields").FIELDS


# A number's unit, from its field's name in the case schemas: (the name's ending, the interface text that shows it).
UNITS = (("_kg", "kg"), ("_years", "years"), ("_deg", "deg"), ("_m_s", "m_s"))


def unit_key(path: str) -> Optional[str]:
    """The interface text that shows a number of this field with its unit ("learn_unit.kg"), or None."""
    name = path.rsplit(".", 1)[-1]
    if name.startswith("months_since"):
        return "learn_unit.months"
    return next((f"learn_unit.{unit}" for ending, unit in UNITS if name.endswith(ending)), None)


def analysis(case: learning.TeachingCase) -> CaseRecord:
    """The teaching case's analysis (the local search and the AI, as for any case of its domain), run once and
    kept on this machine (data/records/learning/analysis/)."""
    store = CaseStore(config.LEARNING_DIR / "analysis")
    record = store.get(case.case.case_id)
    if record is None:
        record = analyse_case(case.case, writer=current_app.config.get("RAG_WRITER"))
        store.save(record)
    return record


def _page(template: str, module: str = "learning", **context):
    return render_template(template, part="search", module=module, here=request.full_path.rstrip("?"), case=None,
                           levels=learning.LEVELS, **context)


@bp.route("/learn", methods=["GET"])
def library():
    entries = learning.read_log()
    return _page("search/learning.html", cases=learning.load_teaching_cases(), summary=learning.log_summary(entries),
                 entries=entries[-5:][::-1], logged=request.args.get("logged") is not None)


@bp.route("/learn/<case_id>/start", methods=["POST"])
def start(case_id: str):
    case = _teaching_case(case_id)
    attempt = learning.start_attempt(case.id)
    return redirect(url_for("learning.attempt", attempt_id=attempt.id, step="read"))


def _text(form, name: str) -> Optional[str]:
    value = (form.get(name) or "").strip() or None
    if value is not None and len(value) > learning.MAX_TEXT:
        raise TranslatableError("error.learn_too_long", n=learning.MAX_TEXT)
    return value


def _compare(attempt: learning.Attempt, case: learning.TeachingCase) -> dict:
    """The compare step: item by item, the learner, the panel and the source; the gaps the learner did not mark."""
    record = analysis(case)
    gaps = {gap.field: gap for gap in record.gaps}
    panel = case.panel_now
    marked = set(attempt.missing)
    panel_items = set(panel.missing) if panel else set()
    unrecorded = {item.info.path for item in missing_fields(case.case)}
    # (field path, the learner marked it, how many panel members did (None: no panel), the app's gap or None,
    # recorded in the case)
    rows = [(info.path, info.path in marked, panel.missing.get(info.path) if panel else None, gaps.get(info.path),
             info.path not in unrecorded) for info in _fields(case) if info.path in marked | panel_items | set(gaps)]
    return {"rows": rows, "panel": panel, "missed": [gap for path, gap in gaps.items() if path not in marked and gap.evidence],
            "found_of_panel": len(marked & {p for p, n in (panel.missing.items() if panel else []) if n}),
            "panel_count": sum(1 for n in (panel.missing.values() if panel else []) if n),
            "knowledge_warning": record.knowledge_warning, "generation": record.generation}


@bp.route("/learn/attempt/<attempt_id>", methods=["GET", "POST"])
def attempt(attempt_id: str):
    attempt_, case = _attempt(attempt_id)
    step = request.args.get("step") if request.args.get("step") in learning.STEPS else "read"
    error = None
    if request.method == "POST":
        action, form = request.form.get("action"), request.form
        try:
            if action == "missing":
                paths = {info.path for info in _fields(case)}
                chosen = form.getlist("missing")
                if set(chosen) - paths:
                    raise TranslatableError("error.invalid_input")
                attempt_.missing, attempt_.other_missing = chosen, _text(form, "other_missing")
                step_done, next_step = "missing", "options"
            elif action == "options":
                attempt_.options, attempt_.reasons = _text(form, "options"), _text(form, "reasons")
                if not attempt_.options:
                    raise TranslatableError("error.learn_options_needed")
                step_done, next_step = "options", "compare"
            elif action == "reflect":
                if not attempt_.step_done("compare"):
                    raise TranslatableError("error.learn_compare_first")
                minutes = (form.get("minutes") or "").strip()
                if minutes and not (minutes.isdigit() and 0 < int(minutes) <= learning.MAX_MINUTES):
                    raise TranslatableError("error.learn_minutes", n=learning.MAX_MINUTES)
                attempt_.reflection, attempt_.minutes = _text(form, "reflection"), int(minutes) if minutes else None
                step_done, next_step = "reflect", None
            else:
                raise TranslatableError("error.invalid_input")
        except TranslatableError as e:
            error = e.message(language_from_cookies(request.cookies))
            step = {"missing": "missing", "options": "options", "reflect": "reflect"}.get(action, step)
        else:
            if step_done not in attempt_.done:
                attempt_.done.append(step_done)
            learning.save_attempt(attempt_)
            if next_step is None:
                learning.log_attempt(attempt_, case)
                return redirect(url_for("learning.library", logged=1))
            return redirect(url_for("learning.attempt", attempt_id=attempt_.id, step=next_step))
    context = {}
    if step in ("compare", "reflect"):
        if not (attempt_.step_done("missing") and attempt_.step_done("options")):
            step = "options" if attempt_.step_done("missing") else "missing"
        else:
            context = _compare(attempt_, case)
            if "compare" not in attempt_.done:
                attempt_.done.append("compare")
                learning.save_attempt(attempt_)
    shown = [(info.path, recorded_value(case.case, info.path), unit_key(info.path)) for info in _fields(case)]
    return _page("search/learning_step.html", attempt=attempt_, teaching=case, step=step, steps=learning.STEPS,
                 fields=_fields(case), shown=[row for row in shown if row[1] is not None], error=error,
                 form=request.form if request.method == "POST" else {}, **context), 400 if error else 200


@bp.route("/learn/log.csv", methods=["GET"])
def cpd_record():
    return Response(learning.cpd_csv(learning.read_log()), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=cpd_record.csv"})

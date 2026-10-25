"""The prosthetics pages after the intake, from the owner's design (docs/design/02-prosthetics/; plan Part 3, 2026-10-24).

GET  /prosthetics/<id>/assess             module 1: the case as measured (residual limb and body, each with how
POST /prosthetics/<id>/assess             it was measured; mobility, measured; the K-level the prosthetist set;
                                          goals by ICF level), the information needed and the draft hard-stop
                                          checks; the form records the rest of the assessment
GET  /prosthetics/<id>/components         modules 2-3: the requirements and their conflicts, then for each component
POST /prosthetics/<id>/components         of the case's level up to three options side by side, never ranked;
                                          action "requirements", "conflicts" or "options" (with "component")
POST /prosthetics/<id>/configuration      the prosthetist's configuration and reason (review log), then module 4
GET  /prosthetics/<id>/fitting            module 4: the six steps, the observation log, check-socket versions,
POST /prosthetics/<id>/fitting            what bears on a definitive prosthesis, the alignment record;
                                          action "steps", "observations", "socket" or "alignment"
GET  /prosthetics/<id>/fabrication-sheet  the configuration and the latest alignment record, to print
GET  /prosthetics/<id>/follow-up          module 5: visits, outcome measures over time, alerts, loop back
POST /prosthetics/<id>/follow-up          action "measures", "visits" or "alerts"

Every value saved here is the prosthetist's (prosthetics/plan.py). The pages add only
what code can know: the recorded facts, what the prosthetist linked, the design's
draft hard-stop rules (awaiting the owner) applied to recorded values
(prosthetics/hard_stops.py), and what the sources say for this case: the review
page's AI summaries with their checked quotes (record.components, record.fitting),
shown here read-only and marked on the review page. Nothing typed here is sent to
the AI. The forms are read by shared/forms.py, the pages drawn by
shared/module_pages.py; a refused form comes back as it was sent, with a message in
the page's language (400).
"""

from typing import Optional

from flask import Blueprint, redirect, request, url_for

from prosthetics import hard_stops
from prosthetics.plan import (
    BACK_TO,
    MAX_ALIGNMENT_VALUES,
    MAX_MOBILITY,
    MEASURED_PATHS,
    OPTION_IDS,
    OTHER_LEG_PATHS,
    Assessment,
    ComponentOption,
    FittingStep,
    MobilityMeasure,
    Observation,
    ProstheticPlan,
    StepRecord,
    case_findings,
    components_for,
    linkable,
    missing_findings,
    value_of,
    waiting_on,
)
from review.decision_log import read_decisions, record_design_choice
from shared import forms
from shared import module_pages as pages
from shared.case_schema import YesNoUnknown
from shared.config import CASES_DIR
from shared.fitting import GAIT_PHASES, StepStatus
from shared.followup import VisitStatus
from shared.forms import MAX_ROWS, NEW_ROWS
from shared.i18n import TextKey, TranslatableError
from shared.requirements import Mark, PlanError, Priority
from shared.store import CaseRecord, store

bp = Blueprint("prosthetic_modules", __name__, template_folder="templates")

DOMAIN = "prosthetics"
MODULES = ("assess", "components", "fitting", "follow_up")
# Module 1's yes / no / unknown values (prosthetics/plan.py Assessment).
YES_NO_VALUES = ("infection", "other_foot_neuropathy", "diabetic_foot_team")
TEXT_VALUES = ("joint_range", "strength", "mobility_note", "goal_participation", "goal_body_function",
               "home_work_setting")
# The values with a short name of their own on these pages ("prow.<path, dots as __>"); the others use the
# intake's field label.
SHORT_NAMES = frozenset(MEASURED_PATHS) | {"assessment.goal_participation", "assessment.goal_body_function",
                                           "assessment.home_work_setting"}
# Module 4's sources: what the review page's design and fitting sections say, by the part of module 4 they bear on.
READINESS, OBSERVATION_SOURCES = "readiness", ("fitting", "alignment")


# ---- Helpers ----------------------------------------------------------------------


def _record(case_id: str) -> CaseRecord:
    return pages.record_for(case_id, DOMAIN)


def _plan(record: CaseRecord) -> ProstheticPlan:
    """The case's plan; a new, empty one if none is saved yet."""
    return record.plan if record.plan is not None else ProstheticPlan()


def _rows_shown(case) -> tuple[str, ...]:
    """Module 1's table rows for this case (the other leg: a lower-limb case only)."""
    return tuple(path for path in MEASURED_PATHS if case.is_lower_limb or path not in OTHER_LEG_PATHS)


def _section(support, key: str):
    """The statements a section of the review page shows for this case ([] if none or not available)."""
    if support is None:
        return []
    return next((section.statements for section in support.sections if section.component == key), [])


def _page(template: str, record: CaseRecord, plan: ProstheticPlan, module: str, status: int = 200, **context):
    case = record.case
    return pages.render_module(template, record, plan, module, status, short_names=SHORT_NAMES,
                               checks=hard_stops.case_checks(case, plan),
                               review_url=url_for("review.show_case", case_id=case.case_id), **context)


# ---- Module 1: amputation case assessment -----------------------------------------


def _assessment_from_form(form, case) -> Assessment:
    rows = _rows_shown(case)
    measured_how = {}
    for n, path in enumerate(rows, 1):
        how = forms.text(form.get(f"how_{n}"), "passess.how")
        if how:
            measured_how[path] = how
    mobility = [MobilityMeasure(r["name"] or "", r["value"] or "", r["how"]) for r in
                forms.rows(form, "mob", ("name", "value", "how"), "passess.mobility", MAX_MOBILITY)]
    if any(not (m.name and m.value) for m in mobility):
        raise TranslatableError("error.mobility_needs_name_value")
    values = {name: forms.member(YesNoUnknown, form.get(name)) for name in YES_NO_VALUES}
    values |= {name: forms.text(form.get(name), f"passess.{name}") for name in TEXT_VALUES}
    if not case.is_lower_limb:
        values["other_foot_neuropathy"] = values["diabetic_foot_team"] = None
    return Assessment(measured_how=measured_how, mobility=mobility, **values)


@bp.route("/prosthetics/<case_id>/assess", methods=["GET", "POST"])
def assess(case_id: str):
    record = _record(case_id)
    plan = _plan(record)
    if request.method == "POST":
        try:
            if request.form.get("action") != "assessment":
                raise TranslatableError("error.invalid_input")
            plan.set_assessment(_assessment_from_form(request.form, record.case))
        except (TranslatableError, PlanError) as e:
            return _assess_page(record, plan, 400, error=pages.refused(e), form=request.form)
        return pages.save_plan(record, plan, "prosthetic_modules.assess")
    return _assess_page(record, plan)


def _assess_page(record: CaseRecord, plan: ProstheticPlan, status: int = 200, **context):
    case = record.case
    rows = [(path, value_of(case, plan, path)) for path in _rows_shown(case)]
    functional = record.components.functional_section if record.components else None
    return _page("prosthetics/assess.html", record, plan, "assess", status, rows=rows,
                 functional=functional.statements if functional else [], yes_no=list(YesNoUnknown),
                 max_mobility=MAX_MOBILITY, new_rows=NEW_ROWS, **context)


# ---- Modules 2-3: requirements and component support ------------------------------


def _options_from_form(form, plan: ProstheticPlan, known_sources: set[str]) -> list[ComponentOption]:
    known = {r.id for r in plan.requirements}
    options = []
    for option_id in OPTION_IDS:
        prefix = f"opt_{option_id}_"
        name = forms.text(form.get(prefix + "name"), "pcomp.option_name")
        texts = {key: forms.text(form.get(prefix + key), f"pcomp.{key}") for key in ("funding", "stock", "notes")}
        lists = {key: forms.lines(form.get(prefix + key), f"pcomp.{key}") for key in ("costs", "checks")}
        weight = forms.optional_number(form.get(prefix + "weight_limit_kg"), "pcomp.weight_limit", positive=True)
        sources = form.getlist(prefix + "source")
        if set(sources) - known_sources:
            raise TranslatableError("error.invalid_input")
        marks, mark_notes = {}, {}
        for requirement_id in sorted(known):
            mark = forms.member(Mark, form.get(f"{prefix}mark_{requirement_id}"))
            if mark is not None:
                marks[requirement_id] = mark
            note = forms.text(form.get(f"{prefix}marknote_{requirement_id}"), "options.mark_note")
            if note:
                mark_notes[requirement_id] = note
        if name is None:
            if any(texts.values()) or any(lists.values()) or weight is not None or sources or marks or mark_notes:
                raise TranslatableError("error.option_needs_name", option=option_id)
            continue
        options.append(ComponentOption(option_id, name, marks, mark_notes, lists["costs"], lists["checks"], sources,
                                       texts["funding"], weight, texts["stock"], texts["notes"]))
    return options


def _components_page(record: CaseRecord, plan: ProstheticPlan, status: int = 200, **context):
    case = record.case
    logged = [entry for entry in read_decisions(case.case_id) if entry["decision"] == "design_choice"]
    components = components_for(case)
    return _page("prosthetics/components.html", record, plan, "components", status, components=components,
                 sources={key: _section(record.components, key) for key in components},
                 findings=case_findings(case, plan), missing=missing_findings(case, plan),
                 priorities=list(Priority), marks=list(Mark), option_ids=OPTION_IDS, new_rows=NEW_ROWS,
                 waiting={r.id: waiting_on(r, case, plan) for r in plan.requirements}, logged_choices=logged,
                 **context)


@bp.route("/prosthetics/<case_id>/components", methods=["GET", "POST"])
def components(case_id: str):
    record = _record(case_id)
    plan = _plan(record)
    if request.method == "POST":
        action, form = request.form.get("action"), request.form
        try:
            if action == "conflicts":
                plan.set_conflicts(forms.conflicts_from_form(form, "preq.conflict_note"))
            elif action == "requirements":
                known = linkable(record.case)
                plan.set_requirements(forms.requirements_from_form(form, plan.requirements, known), known)
            elif action == "options":
                component = form.get("component", "")
                if component not in components_for(record.case):
                    raise TranslatableError("error.invalid_input")
                known_sources = {cited.statement.id for cited in _section(record.components, component)}
                plan.set_options(component, _options_from_form(form, plan, known_sources),
                                 components_for(record.case), known_sources)
            else:
                raise TranslatableError("error.invalid_input")
        except (TranslatableError, PlanError) as e:
            return _components_page(record, plan, 400, error=pages.refused(e), form=request.form)
        anchor = f"component-{request.form.get('component')}" if action == "options" else None
        response = pages.save_plan(record, plan, "prosthetic_modules.components")
        if anchor:
            response.location += f"#{anchor}"
        return response
    return _components_page(record, plan)


@bp.route("/prosthetics/<case_id>/configuration", methods=["POST"])
def configuration(case_id: str):
    record = _record(case_id)
    plan = _plan(record)
    chosen = {component: request.form.get(f"chosen_{component}") or "" for component in components_for(record.case)}
    try:
        reason = forms.text(request.form.get("reason"), "pcomp.reason")
        if not any(chosen.values()):
            raise TranslatableError("error.configuration_needs_option")
        if any(option_id and plan.option(component, option_id) is None for component, option_id in chosen.items()):
            raise TranslatableError("error.invalid_input")
        if reason is None:
            raise TranslatableError("error.choice_needs_reason")
        plan.choose(chosen, reason)
    except (TranslatableError, PlanError) as e:
        return _components_page(record, plan, 400, error=pages.refused(e), form=request.form)
    record.plan = plan
    store.save(record)
    record_design_choice(record, ui_language=pages.ui_language())
    # The design's "Record and go to design →".
    return redirect(url_for("prosthetic_modules.fitting", case_id=case_id, chosen=1))


# ---- Module 4: design and fitting -------------------------------------------------


def _steps_from_form(form) -> dict[FittingStep, StepRecord]:
    return {step: StepRecord(forms.member(StepStatus, form.get(f"step_{step.value}_status")) or StepStatus.NOT_STARTED,
                             forms.text(form.get(f"step_{step.value}_notes"), f"pstep.{step.value}"))
            for step in FittingStep}


def _observations_from_form(form) -> list[Observation]:
    """The observation log's rows; a row with nothing typed is left out, one without what was seen is refused."""
    kept = []
    for n in range(1, forms.count(form, "obs_rows", MAX_ROWS) + 1):
        prefix = f"obs_{n}_"
        seen = forms.text(form.get(prefix + "seen"), "pfit.seen")
        adjustment = forms.text(form.get(prefix + "adjustment"), "pfit.adjustment")
        after = forms.text(form.get(prefix + "seen_after"), "pfit.seen_after")
        step = forms.member(FittingStep, form.get(prefix + "step"))
        phase = form.get(prefix + "phase") or None
        if phase is not None and phase not in GAIT_PHASES:
            raise TranslatableError("error.invalid_input")
        if seen is None:
            if adjustment or after:
                raise TranslatableError("error.observation_needs_seen")
            continue
        if step is None:
            raise TranslatableError("error.observation_needs_step")
        kept.append(Observation(step.value, seen, phase, adjustment, after))
    if len(kept) > MAX_ROWS:
        raise TranslatableError("error.too_many_rows", field=TextKey("pfit.observations"), n=MAX_ROWS)
    return kept


def _save_alignment(form, plan: ProstheticPlan) -> None:
    values = {}
    for n in range(1, forms.count(form, "align_rows", MAX_ALIGNMENT_VALUES) + 1):
        name = forms.text(form.get(f"align_{n}_name"), "pfit.align_name")
        value = forms.text(form.get(f"align_{n}_value"), "pfit.align_value")
        if bool(name) != bool(value):
            raise TranslatableError("error.alignment_needs_both")
        if name:
            if name in values:
                raise TranslatableError("error.alignment_repeated", name=name)
            values[name] = value
    if len(values) > MAX_ALIGNMENT_VALUES:
        raise TranslatableError("error.too_many_rows", field=TextKey("pfit.alignment"), n=MAX_ALIGNMENT_VALUES)
    try:
        plan.save_alignment(values, forms.text(form.get("align_note"), "pfit.align_note"),
                            forms.text(form.get("align_by"), "pfit.align_by"))
    except PlanError:
        raise TranslatableError("error.no_alignment_change") from None


def _fitting_page(record: CaseRecord, plan: ProstheticPlan, status: int = 200, **context):
    case = record.case
    return _page("prosthetics/fitting.html", record, plan, "fitting", status, steps=list(FittingStep),
                 statuses=list(StepStatus), phases=GAIT_PHASES, new_rows=NEW_ROWS,
                 components=components_for(case), readiness=_section(record.fitting, READINESS),
                 observation_sources=[cited for key in OBSERVATION_SOURCES for cited in _section(record.fitting, key)],
                 readiness_values=record.fitting.recorded if record.fitting else [],
                 chosen_logged=request.args.get("chosen") is not None, **context)


@bp.route("/prosthetics/<case_id>/fitting", methods=["GET", "POST"])
def fitting(case_id: str):
    record = _record(case_id)
    plan = _plan(record)
    if request.method == "POST":
        action, form = request.form.get("action"), request.form
        try:
            if action == "steps":
                plan.set_steps(_steps_from_form(form))
            elif action == "observations":
                plan.set_observations(_observations_from_form(form))
            elif action == "socket":
                seen = forms.text(form.get("socket_seen"), "pfit.socket_seen")
                if seen is None:
                    raise TranslatableError("error.socket_needs_seen")
                plan.add_socket_version(seen, forms.text(form.get("socket_changed"), "pfit.socket_changed"))
            elif action == "alignment":
                _save_alignment(form, plan)
            else:
                raise TranslatableError("error.invalid_input")
        except (TranslatableError, PlanError) as e:
            return _fitting_page(record, plan, 400, error=pages.refused(e), form=request.form)
        return pages.save_plan(record, plan, "prosthetic_modules.fitting")
    return _fitting_page(record, plan)


@bp.route("/prosthetics/<case_id>/fabrication-sheet", methods=["GET"])
def fabrication_sheet(case_id: str):
    record = _record(case_id)
    plan = _plan(record)
    return _page("prosthetics/fabrication_sheet.html", record, plan, "fitting", components=components_for(record.case),
                 steps=list(FittingStep))[0]


# ---- Module 5: follow-up and evaluation -------------------------------------------


def _follow_up_page(record: CaseRecord, plan: ProstheticPlan, status: int = 200, **context):
    return _page("prosthetics/follow_up.html", record, plan, "follow_up", status, new_rows=NEW_ROWS,
                 statuses=list(VisitStatus), back_to=BACK_TO, **context)


@bp.route("/prosthetics/<case_id>/follow-up", methods=["GET", "POST"])
def follow_up(case_id: str):
    record = _record(case_id)
    plan = _plan(record)
    if request.method == "POST":
        try:
            forms.follow_up_from_form(request.form, plan.follow_up, BACK_TO)
        except (TranslatableError, ValueError) as e:
            return _follow_up_page(record, plan, 400, error=pages.refused(e), form=request.form)
        return pages.save_plan(record, plan, "prosthetic_modules.follow_up")
    return _follow_up_page(record, plan)


def latest_case_id() -> Optional[str]:
    """The prosthetic case saved last, for the map's links."""
    return pages.latest_case_id(DOMAIN, CASES_DIR)

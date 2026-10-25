"""The orthotics pages after the intake, from the owner's "Orthotics Module Design" canvas (2026-10-23).

GET  /orthotics                         the system map: the reasoning chain, the six modules, the knowledge
                                        behind them, the draft hard stops and the roll-out
GET  /orthotics/<id>/analysis           module 1: functional case analysis (goals by ICF level, the structured
                                        exam with how each value was measured, gait phase by phase, the
                                        information needed and the hard-stop checks)
GET  /orthotics/<id>/requirements       module 2: what the orthosis must do, traced to the case; conflicts
POST /orthotics/<id>/requirements       action "requirements" or "conflicts"
GET  /orthotics/<id>/options            module 3: up to three option cards side by side, never ranked, and the
POST /orthotics/<id>/options            FES referral; form "options" or "fes"
POST /orthotics/<id>/choice             the option the orthotist chose and why (review log), then module 4
GET  /orthotics/<id>/design             module 4: six steps, simulation as entered, parameters with their basis
POST /orthotics/<id>/design             and approval, versions; action "steps", "parameters", "approve",
                                        "simulation" or "manufacture"
GET  /orthotics/<id>/fabrication-sheet  the chosen option and the approved parameters, to print
GET  /orthotics/<id>/fit                module 5: check-out, tuning, before and after, training plan, leaflet
POST /orthotics/<id>/fit                action "delivered", "checkout", "tuning", "measures", "training", "leaflet"
GET  /orthotics/<id>/leaflet            the patient leaflet, to print (?lang=ar or en)
GET  /orthotics/<id>/follow-up          module 6: visits, outcome measures over time, alerts, wearing, loop back
POST /orthotics/<id>/follow-up          action "measures", "visits" or "alerts"
GET  /orthotics/<id>/summary            what was recorded, for the physiotherapist, to print

Every value saved here is the orthotist's (or the physiotherapist's): owner's
decision 2026-10-23, the design's screens with the orthotist filling what the
design shows as a suggestion. The pages add only what code can know: the
recorded facts, what the orthotist linked, the design's draft hard-stop rules (awaiting the owner) applied to
recorded values (orthotics/hard_stops.py), and what the source library says about
each device type, part and step, found by local search on fixed wording
(orthotics/sources.py) and quoted as printed. Nothing is sent to the AI. A refused
form comes back as it was sent, with a message in the page's language (400).
"""

from typing import Optional

from flask import Blueprint, abort, redirect, render_template, request, url_for

from knowledge.catalog import load_catalog
from knowledge.retrieval import KnowledgeBaseMissing
from orthotics import hard_stops, sources
from orthotics.case import GAIT_PHASES
from orthotics.fields import FIELDS as ORTHOTIC_FIELDS
from orthotics.fit import BeforeAfter, CheckItem, TuningRow
from orthotics.plan import (
    BACK_TO,
    FES_REFERRAL,
    MAX_PARTS_PER_OPTION,
    OPTION_IDS,
    PARAMETERS,
    STEP_METHODS,
    Basis,
    DesignOption,
    DeviceType,
    FesReferral,
    Method,
    OptionPart,
    OrthoticPlan,
    Part,
    PlanError,
    SimulationRow,
    Step,
    StepRecord,
    StepStatus,
    case_findings,
    linkable,
    missing_findings,
    value_at,
    waiting_on,
)
from review.decision_log import read_decisions, record_design_choice
from shared import forms
from shared import module_pages as pages
from shared.config import CASES_DIR
from shared.dates import DateError
from shared.followup import VisitStatus
from shared.forms import MAX_LIST, NEW_ROWS
from shared.i18n import LANGUAGES, TranslatableError, language_from_cookies, t
from shared.requirements import Mark, Priority
from shared.store import CaseRecord, store

bp = Blueprint("orthotic_modules", __name__, template_folder="templates")

CRITICAL = {info.path for info in ORTHOTIC_FIELDS if info.critical}
# The design's roll-out: one condition and device at a time. Only stroke is built.
CONDITIONS = ("stroke", "cerebral_palsy", "spinal_cord_injury", "peripheral_nerve_injury", "diabetic_foot", "scoliosis")
MODULES = ("analysis", "requirements", "options", "design", "fit", "follow_up")

# Search the source library; replaced in the tests (no embedding model there).
find_passages = sources.find_passages


# ---- Helpers ----------------------------------------------------------------------
# Reading the forms (shared/forms.py) and drawing, saving and refusing a page (shared/module_pages.py) are
# every domain's; what is orthotic is the page context below.


def _record(case_id: str) -> CaseRecord:
    return pages.record_for(case_id, "orthotics")


def _plan(record: CaseRecord) -> OrthoticPlan:
    """The case's plan; a new one (from the intake's requirements) if none is saved yet."""
    return record.plan if record.plan is not None else OrthoticPlan.started_from(record.case)


def latest_case_id() -> Optional[str]:
    """The orthotic case saved last (in memory, else in the cases folder), for the map's links."""
    return pages.latest_case_id("orthotics", CASES_DIR)


def _passages(items: dict[str, tuple[str, str]]):
    """(passages by key, None) or ({}, the reason the library couldn't be searched)."""
    if not items:
        return {}, None
    try:
        return find_passages(items), None
    except KnowledgeBaseMissing as e:
        return {}, str(e)


def _source_types() -> dict[str, str]:
    """doc id -> its kind of source (catalog source_type), for the evidence badges."""
    return {doc.id: doc.source_type for doc in load_catalog()}


def _page(template: str, record: CaseRecord, plan: OrthoticPlan, module: str, status: int = 200, **context):
    return pages.render_module(template, record, plan, module, status, critical=CRITICAL, gait_phases=GAIT_PHASES,
                               fes_id=FES_REFERRAL, **context)


# ---- Map --------------------------------------------------------------------------


@bp.route("/orthotics", methods=["GET"])
def module_map():
    case_id = latest_case_id()
    return render_template("orthotics/map.html", case=None, domain="orthotics", module="map", here=request.path,
                           latest=case_id, modules=MODULES, rules=hard_stops.RULES,
                           clinic_rules=hard_stops.clinic_rules())


# ---- Module 1: functional case analysis -------------------------------------------


EXAM_ROWS = (  # the structured exam table, in the design's order: (path, how it was measured)
    ("exam.dorsiflexion_knee_extended_deg", "measured"), ("exam.dorsiflexion_knee_flexed_deg", "measured"),
    ("exam.plantarflexor_tone_grade", "tone"), ("exam.dorsiflexor_strength", "measured"),
    ("exam.knee_extensor_strength", "measured"), ("exam.knee_in_stance", "measured"),
    ("exam.foot_posture", "measured"), ("exam.protective_sensation", "measured"), ("exam.proprioception", "measured"),
    ("exam.skin_condition", "measured"), ("exam.ulcer_infection_or_poor_blood_supply", "measured"),
    ("walking.gait_speed_m_s", "speed"), ("walking.status", "status"), ("walking.falls_last_6_months", "measured"),
    ("footwear", "measured"), ("donning", "measured"), ("prior_orthoses", "measured"),
    ("implanted_electronic_device", "implant"),
)


@bp.route("/orthotics/<case_id>/analysis", methods=["GET"])
def analysis(case_id: str):
    record = _record(case_id)
    plan = _plan(record)
    rows = [(path, kind, value_at(record.case, path)) for path, kind in EXAM_ROWS]
    return _page("orthotics/analysis.html", record, plan, "analyse", exam_rows=rows, conditions=CONDITIONS,
                 checks=hard_stops.case_checks(record.case, record.plan))[0]


# ---- Module 2: requirements -------------------------------------------------------


def _requirements_page(record, plan, status=200, **context):
    case = record.case
    return _page("orthotics/requirements.html", record, plan, "requirements", status, findings=case_findings(case),
                 missing=missing_findings(case), priorities=list(Priority), new_rows=NEW_ROWS,
                 waiting={r.id: waiting_on(r, case) for r in plan.requirements}, **context)


@bp.route("/orthotics/<case_id>/requirements", methods=["GET", "POST"])
def requirements(case_id: str):
    record = _record(case_id)
    plan = _plan(record)
    if request.method == "POST":
        known = linkable(record.case)
        try:
            if request.form.get("action") == "conflicts":
                plan.set_conflicts(forms.conflicts_from_form(request.form))
            else:
                plan.set_requirements(forms.requirements_from_form(request.form, plan.requirements, known), known)
        except (TranslatableError, PlanError) as e:
            return _requirements_page(record, plan, 400, error=pages.refused(e), form=request.form)
        return pages.save_plan(record, plan, "orthotic_modules.requirements")
    return _requirements_page(record, plan)


# ---- Module 3: design options -----------------------------------------------------


def _options_from_form(form, plan: OrthoticPlan) -> list[DesignOption]:
    known = {r.id for r in plan.requirements}
    options = []
    for option_id in OPTION_IDS:
        prefix = f"opt_{option_id}_"
        device = forms.member(DeviceType, form.get(prefix + "device"))
        texts = {name: forms.text(form.get(prefix + name), f"options.{name}") for name in ("notes", "summary", "stock")}
        lists = {name: forms.lines(form.get(prefix + name), f"options.{name}") for name in ("costs", "checks")}
        marks, mark_notes = {}, {}
        for requirement_id in sorted(known):
            mark = forms.member(Mark, form.get(f"{prefix}mark_{requirement_id}"))
            if mark is not None:
                marks[requirement_id] = mark
            note = forms.text(form.get(f"{prefix}marknote_{requirement_id}"), "options.mark_note")
            if note:
                mark_notes[requirement_id] = note
        parts = []
        for k in range(1, MAX_PARTS_PER_OPTION + 1):
            part = forms.member(Part, form.get(f"{prefix}part_{k}"))
            serves = form.getlist(f"{prefix}part_{k}_req")
            note = forms.text(form.get(f"{prefix}part_{k}_note"), "options.part_note")
            if set(serves) - known:
                raise TranslatableError("error.invalid_input")
            if part is None:
                if serves or note:
                    raise TranslatableError("error.part_needs_choice", option=option_id)
                continue
            parts.append(OptionPart(part, serves, note))
        if device is None:
            if any(texts.values()) or any(lists.values()) or marks or mark_notes or parts:
                raise TranslatableError("error.option_needs_device", option=option_id)
            continue
        options.append(DesignOption(option_id, device, parts, marks, texts["notes"], texts["summary"], mark_notes,
                                    lists["costs"], lists["checks"], texts["stock"]))
    return options


def _options_page(record: CaseRecord, plan: OrthoticPlan, status: int = 200, **context):
    devices = {o.device for o in plan.options} | {DeviceType.FES}
    parts = {p.part for o in plan.options for p in o.parts}
    items = {f"device.{d.value}": sources.DEVICES[d] for d in devices}
    items |= {f"part.{p.value}": sources.PARTS[p] for p in parts}
    passages, library_warning = _passages(items)
    case = record.case
    logged = [entry for entry in read_decisions(case.case_id) if entry["decision"] == "design_choice"]
    return _page("orthotics/options.html", record, plan, "options", status, devices=list(DeviceType), parts=list(Part),
                 marks=list(Mark), option_ids=OPTION_IDS, max_parts=MAX_PARTS_PER_OPTION, passages=passages,
                 findings=case_findings(case), library_warning=library_warning, logged_choices=logged,
                 source_types=_source_types(), checks=hard_stops.case_checks(case, plan),
                 lacks_lining={o.id: hard_stops.lacks_lining(case, o) for o in plan.options},
                 chosen_logged=request.args.get("chosen") is not None, **context)


@bp.route("/orthotics/<case_id>/options", methods=["GET", "POST"])
def options(case_id: str):
    record = _record(case_id)
    plan = _plan(record)
    if request.method == "POST":
        try:
            if request.form.get("form") == "fes":
                plan.set_fes(FesReferral(forms.lines(request.form.get("fes_checks"), "options.fes_checks"),
                                         forms.text(request.form.get("fes_note"), "options.fes_note")))
            else:
                plan.set_options(_options_from_form(request.form, plan))
        except (TranslatableError, PlanError) as e:
            return _options_page(record, plan, 400, error=pages.refused(e), form=request.form)
        return pages.save_plan(record, plan, "orthotic_modules.options")
    return _options_page(record, plan)


@bp.route("/orthotics/<case_id>/choice", methods=["POST"])
def choice(case_id: str):
    record = _record(case_id)
    plan = _plan(record)
    lang = language_from_cookies(request.cookies)
    option_id = request.form.get("chosen") or ""
    try:
        reason = forms.text(request.form.get("reason"), "options.reason")
        if option_id != FES_REFERRAL and plan.option(option_id) is None:
            raise TranslatableError("error.choice_needs_option")
        if reason is None:
            raise TranslatableError("error.choice_needs_reason")
        plan.choose(option_id, reason)
    except TranslatableError as e:
        return _options_page(record, plan, 400, error=e.message(lang), form=request.form)
    record.plan = plan
    store.save(record)
    record_design_choice(record, ui_language=lang)
    # The design's "Record and go to design →".
    return redirect(url_for("orthotic_modules.design", case_id=case_id, chosen=1))


# ---- Module 4: digital design -----------------------------------------------------


def _steps_from_form(form) -> dict[Step, StepRecord]:
    steps = {}
    for step in Step:
        prefix = f"step_{step.value}_"
        method = forms.member(Method, form.get(prefix + "method"))
        if method is not None and method not in STEP_METHODS[step]:
            raise TranslatableError("error.invalid_input")
        steps[step] = StepRecord(forms.member(StepStatus, form.get(prefix + "status")) or StepStatus.NOT_STARTED,
                                 method, forms.text(form.get(prefix + "notes"), f"step.{step.value}"))
    return steps


def _save_parameters(form, plan: OrthoticPlan) -> None:
    known = {r.id for r in plan.requirements}
    values, basis, basis_notes, links = {}, {}, {}, {}
    for key in PARAMETERS:
        values[key] = forms.text(form.get(f"param_{key}"), f"param.{key}") or ""
        kind = forms.member(Basis, form.get(f"param_{key}_basis"))
        if kind is not None:
            basis[key] = kind.value
        basis_notes[key] = forms.text(form.get(f"param_{key}_basis_note"), "design.basis_note") or ""
        serves = form.getlist(f"param_{key}_req")
        if set(serves) - known:
            raise TranslatableError("error.invalid_input")
        links[key] = serves
    note = forms.text(form.get("param_note"), "design.version_note")
    by = forms.text(form.get("param_by"), "design.by")
    try:
        plan.save_parameters(values, note, basis, basis_notes, links, by)
    except PlanError:
        raise TranslatableError("error.no_parameter_change") from None


def _design_page(record: CaseRecord, plan: OrthoticPlan, status: int = 200, **context):
    passages, library_warning = _passages({f"step.{s.value}": sources.STEPS[s] for s in Step})
    return _page("orthotics/design.html", record, plan, "design", status, steps=list(Step), statuses=list(StepStatus),
                 step_methods=STEP_METHODS, parameters=PARAMETERS, bases=list(Basis), passages=passages,
                 library_warning=library_warning, chosen=plan.option(plan.chosen), new_rows=NEW_ROWS,
                 chosen_logged=request.args.get("chosen") is not None, **context)


@bp.route("/orthotics/<case_id>/design", methods=["GET", "POST"])
def design(case_id: str):
    record = _record(case_id)
    plan = _plan(record)
    if request.method == "POST":
        action = request.form.get("action")
        try:
            if action == "parameters":
                _save_parameters(request.form, plan)
            elif action == "approve":
                key = request.form.get("key", "")
                if key not in plan.parameters:
                    raise TranslatableError("error.invalid_input")
                plan.approve(key)
            elif action == "simulation":
                rows = [SimulationRow(r["item"], r["result"]) for r in
                        forms.rows(request.form, "sim", ("item", "result"), "design.simulation", MAX_LIST)
                        if r["item"] and r["result"]]
                plan.set_simulation(rows, forms.lines(request.form.get("hot_spots"), "design.hot_spots"),
                                    forms.text(request.form.get("relief_note"), "design.relief_note"))
            elif action == "manufacture":
                try:
                    plan.send_to_manufacture()
                except PlanError:
                    raise TranslatableError("error.approve_first") from None
            else:
                plan.set_steps(_steps_from_form(request.form))
        except (TranslatableError, PlanError) as e:
            return _design_page(record, plan, 400, error=pages.refused(e), form=request.form)
        return pages.save_plan(record, plan, "orthotic_modules.design")
    return _design_page(record, plan)


@bp.route("/orthotics/<case_id>/fabrication-sheet", methods=["GET"])
def fabrication_sheet(case_id: str):
    record = _record(case_id)
    plan = _plan(record)
    return _page("orthotics/fabrication_sheet.html", record, plan, "design", parameters=PARAMETERS,
                 chosen=plan.option(plan.chosen))[0]


# ---- Module 5: fit, tune and train ------------------------------------------------


def _starting_rows(record: CaseRecord, plan: OrthoticPlan) -> dict[str, list]:
    """What the fit page's empty check-out starts from: the orthotist's own earlier words (the chosen option's
    checks at fitting, then the requirements), never the code's. The before-and-after table starts from the
    intake's gait speed and deviations, labelled by the page (fit.html)."""
    chosen = plan.option(plan.chosen)
    checkout = [CheckItem(text) for text in (chosen.checks if chosen else [])]
    checkout += [CheckItem(f"{r.id} {r.text}") for r in plan.requirements]
    return {"checkout": checkout}


def _fit_page(record: CaseRecord, plan: OrthoticPlan, status: int = 200, **context):
    return _page("orthotics/fit.html", record, plan, "fit", status, start=_starting_rows(record, plan), new_rows=NEW_ROWS,
                 chosen=plan.option(plan.chosen), **context)


@bp.route("/orthotics/<case_id>/fit", methods=["GET", "POST"])
def fit(case_id: str):
    record = _record(case_id)
    plan = _plan(record)
    if request.method == "POST":
        action, form, record_ = request.form.get("action"), request.form, plan.fit
        try:
            if action == "delivered":
                record_.delivered_on = forms.date(form.get("delivered_on"), "fit.delivered_on")
            elif action == "checkout":
                record_.checkout = [CheckItem(r["text"], r["done"], r["note"]) for r in
                                    forms.rows(form, "check", ("text", "note"), "fit.checkout", flags=("done",))
                                    if r["text"]]
            elif action == "tuning":
                record_.tuning = [TuningRow(r["step"] or "", r["change"] or "", r["seen"]) for r in
                                  forms.rows(form, "tune", ("step", "change", "seen"), "fit.tuning")]
            elif action == "measures":
                record_.measures = [BeforeAfter(r["measure"] or "", r["before"], r["after"], r["note"]) for r in
                                    forms.rows(form, "ba", ("measure", "before", "after", "note"), "fit.measures")]
            elif action == "training":
                record_.wearing = forms.lines(form.get("wearing"), "fit.wearing")
                record_.practice = forms.lines(form.get("practice"), "fit.practice")
                record_.training_by = forms.text(form.get("training_by"), "fit.training_by")
            elif action == "leaflet":
                record_.leaflet_ar = forms.long_text(form.get("leaflet_ar"), "fit.leaflet_ar")
                record_.leaflet_en = forms.long_text(form.get("leaflet_en"), "fit.leaflet_en")
                record_.leaflet_checked_by = forms.text(form.get("leaflet_checked_by"), "fit.checked_by")
            else:
                raise TranslatableError("error.invalid_input")
        except (TranslatableError, DateError) as e:
            return _fit_page(record, plan, 400, error=pages.refused(e), form=request.form)
        return pages.save_plan(record, plan, "orthotic_modules.fit")
    return _fit_page(record, plan)


@bp.route("/orthotics/<case_id>/leaflet", methods=["GET"])
def leaflet(case_id: str):
    record = _record(case_id)
    plan = _plan(record)
    language = request.args.get("lang", "ar")
    if language not in LANGUAGES:
        abort(404)
    # The leaflet's own words are in its language, whatever the page's: so is "next review".
    return _page("orthotics/leaflet.html", record, plan, "fit", leaflet_lang=language, next_review=plan.follow_up.next_due(),
                 next_review_label=t("leaflet.next_review", language))[0]


# ---- Module 6: follow-up ----------------------------------------------------------


def _follow_up_page(record: CaseRecord, plan: OrthoticPlan, status: int = 200, **context):
    return _page("orthotics/follow_up.html", record, plan, "follow_up", status, new_rows=NEW_ROWS, statuses=list(VisitStatus),
                 back_to=BACK_TO, **context)


@bp.route("/orthotics/<case_id>/follow-up", methods=["GET", "POST"])
def follow_up(case_id: str):
    record = _record(case_id)
    plan = _plan(record)
    if request.method == "POST":
        try:
            forms.follow_up_from_form(request.form, plan.follow_up, BACK_TO)
        except (TranslatableError, DateError, ValueError) as e:
            return _follow_up_page(record, plan, 400, error=pages.refused(e), form=request.form)
        return pages.save_plan(record, plan, "orthotic_modules.follow_up")
    return _follow_up_page(record, plan)


@bp.route("/orthotics/<case_id>/summary", methods=["GET"])
def summary(case_id: str):
    record = _record(case_id)
    plan = _plan(record)
    return _page("orthotics/summary.html", record, plan, "follow_up", chosen=plan.option(plan.chosen),
                 next_review=plan.follow_up.next_due())[0]

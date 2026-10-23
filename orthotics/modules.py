"""The orthotic modules after the analysis (added 2026-10-23), from the "Orthotics Module Design" canvas.

GET  /orthotics                      the module map: the brief's orthotics capabilities and where each is
GET  /orthotics/<id>/requirements    module 2: what the orthosis must do, tied to the case's findings
POST /orthotics/<id>/requirements
GET  /orthotics/<id>/options         module 3: up to three design options side by side, never ranked,
POST /orthotics/<id>/options         with their materials and parts tied to the requirements
POST /orthotics/<id>/choice          the option the orthotist chose and why (appended to the review log)
GET  /orthotics/<id>/design          module 4: the digital design workflow and versioned parameters
POST /orthotics/<id>/design          action "steps" or "parameters"

Module 1, functional case analysis, is the orthotic intake form and the review
page. Every value saved here is the orthotist's (orthotics/plan.py); the pages
add only what the source library says about each device type, part and step,
found by local search on fixed wording (orthotics/sources.py) and quoted as
printed. Nothing is sent to the AI. A refused form comes back as it was sent,
with a message in the page's language (400).
"""

from typing import Optional

from flask import Blueprint, abort, redirect, render_template, request, url_for

from knowledge.retrieval import KnowledgeBaseMissing
from orthotics import sources
from orthotics.plan import (
    MAX_PARTS_PER_OPTION,
    MAX_TEXT,
    OPTION_IDS,
    PARAMETERS,
    STEP_METHODS,
    DesignOption,
    DeviceType,
    Mark,
    Method,
    OptionPart,
    OrthoticPlan,
    Part,
    PlanError,
    Priority,
    Requirement,
    Step,
    StepRecord,
    StepStatus,
    case_findings,
)
from review.decision_log import read_decisions, record_design_choice
from shared.case_schema import GAIT_PHASES
from shared.field_guide import ORTHOTIC_FIELDS
from shared.i18n import TextKey, TranslatableError, language_from_cookies
from shared.store import CaseRecord, store

bp = Blueprint("orthotic_modules", __name__, template_folder="templates")

MAX_REQUIREMENTS = 30
NEW_ROWS = 3  # empty requirement rows offered for adding
CRITICAL = {info.path for info in ORTHOTIC_FIELDS if info.critical}

# Search the source library; replaced in the tests (no embedding model there).
find_passages = sources.find_passages


def _record(case_id: str) -> CaseRecord:
    record = store.get(case_id)
    if record is None or record.case.domain != "orthotics":
        abort(404, f"No orthotic case with id {case_id!r}")
    return record


def _plan(record: CaseRecord) -> OrthoticPlan:
    """The case's plan; a new one (from the intake's requirements) if none is saved yet."""
    return record.plan if record.plan is not None else OrthoticPlan.started_from(record.case)


def _text(raw: Optional[str], label: str, **params) -> Optional[str]:
    value = (raw or "").strip() or None
    if value is not None and len(value) > MAX_TEXT:
        raise TranslatableError("error.too_long", field=TextKey(label), n=MAX_TEXT, **params)
    return value


def _member(cls, raw: Optional[str]):
    """The vocabulary member a form sent, None if left empty; a value not offered is refused."""
    if not raw:
        return None
    try:
        return cls(raw)
    except ValueError:
        raise TranslatableError("error.invalid_input") from None


def _passages(items: dict[str, tuple[str, str]]):
    """(passages by key, None) or ({}, the reason the library couldn't be searched)."""
    if not items:
        return {}, None
    try:
        return find_passages(items), None
    except KnowledgeBaseMissing as e:
        return {}, str(e)


def _page(template: str, record: CaseRecord, plan: OrthoticPlan, module: str, **context):
    return render_template(
        template,
        case=record.case,
        record=record,
        plan=plan,
        domain="orthotics",
        module=module,
        critical=CRITICAL,
        gait_phases=GAIT_PHASES,
        here=request.path,
        form=context.pop("form", None) or {},
        error=context.pop("error", None),
        **context,
    )


# ---- Map --------------------------------------------------------------------------


@bp.route("/orthotics", methods=["GET"])
def module_map():
    return render_template("module_map.html", case=None, domain="orthotics", module="map", here=request.path)


# ---- Module 2: requirements -------------------------------------------------------


def _requirements_from_form(form, plan: OrthoticPlan, known: set[str]) -> list[Requirement]:
    try:
        rows = min(int(form.get("rows", "0")), MAX_REQUIREMENTS + NEW_ROWS)
    except ValueError:
        raise TranslatableError("error.invalid_input") from None
    existing = {r.id for r in plan.requirements}
    kept, numbers = [], [int(i[1:]) for i in existing if i[1:].isdigit()]
    next_number = max(numbers, default=0) + 1
    for n in range(1, rows + 1):
        text = _text(form.get(f"req_{n}_text"), "req.requirement")
        if text is None:
            continue  # an emptied row removes its requirement
        requirement_id = form.get(f"req_{n}_id") or ""
        if requirement_id not in existing:
            requirement_id, next_number = f"R{next_number}", next_number + 1
        findings = form.getlist(f"req_{n}_finding")
        if set(findings) - known:
            raise TranslatableError("error.invalid_input")
        kept.append(Requirement(requirement_id, text, findings, _member(Priority, form.get(f"req_{n}_priority"))))
    if len(kept) > MAX_REQUIREMENTS:
        raise TranslatableError("error.too_many_requirements", n=MAX_REQUIREMENTS)
    return kept


@bp.route("/orthotics/<case_id>/requirements", methods=["GET", "POST"])
def requirements(case_id: str):
    record = _record(case_id)
    plan = _plan(record)
    findings = case_findings(record.case)
    if request.method == "POST":
        lang = language_from_cookies(request.cookies)
        try:
            plan.set_requirements(_requirements_from_form(request.form, plan, {f.key for f in findings}),
                                  {f.key for f in findings})
        except TranslatableError as e:
            return _page("requirements.html", record, plan, "requirements", findings=findings,
                         priorities=list(Priority), new_rows=NEW_ROWS, error=e.message(lang), form=request.form), 400
        except PlanError:
            return _page("requirements.html", record, plan, "requirements", findings=findings,
                         priorities=list(Priority), new_rows=NEW_ROWS,
                         error=TranslatableError("error.invalid_input").message(lang), form=request.form), 400
        record.plan = plan
        store.save(record)
        return redirect(url_for("orthotic_modules.requirements", case_id=case_id, saved=1))
    return _page("requirements.html", record, plan, "requirements", findings=findings, priorities=list(Priority),
                 new_rows=NEW_ROWS, saved=request.args.get("saved") is not None)


# ---- Module 3: design options -----------------------------------------------------


def _options_from_form(form, plan: OrthoticPlan) -> list[DesignOption]:
    known = {r.id for r in plan.requirements}
    options = []
    for option_id in OPTION_IDS:
        prefix = f"opt_{option_id}_"
        device = _member(DeviceType, form.get(prefix + "device"))
        notes = _text(form.get(prefix + "notes"), "options.notes")
        marks = {}
        for requirement_id in known:
            mark = _member(Mark, form.get(f"{prefix}mark_{requirement_id}"))
            if mark is not None:
                marks[requirement_id] = mark
        parts = []
        for k in range(1, MAX_PARTS_PER_OPTION + 1):
            part = _member(Part, form.get(f"{prefix}part_{k}"))
            serves = form.getlist(f"{prefix}part_{k}_req")
            if set(serves) - known:
                raise TranslatableError("error.invalid_input")
            if part is None:
                if serves:
                    raise TranslatableError("error.part_needs_choice", option=option_id)
                continue
            parts.append(OptionPart(part, serves))
        if device is None:
            if notes or marks or parts:
                raise TranslatableError("error.option_needs_device", option=option_id)
            continue
        options.append(DesignOption(option_id, device, parts, marks, notes))
    return options


def _options_page(record: CaseRecord, plan: OrthoticPlan, status: int = 200, **context):
    devices = {o.device for o in plan.options}
    parts = {p.part for o in plan.options for p in o.parts}
    items = {f"device.{d.value}": sources.DEVICES[d] for d in devices}
    items |= {f"part.{p.value}": sources.PARTS[p] for p in parts}
    passages, library_warning = _passages(items)
    logged = [entry for entry in read_decisions(record.case.case_id) if entry["decision"] == "design_choice"]
    page = _page("options.html", record, plan, "options", devices=list(DeviceType), parts=list(Part),
                 marks=list(Mark), option_ids=OPTION_IDS, max_parts=MAX_PARTS_PER_OPTION, passages=passages,
                 findings=case_findings(record.case),
                 library_warning=library_warning, logged_choices=logged, **context)
    return page, status


@bp.route("/orthotics/<case_id>/options", methods=["GET", "POST"])
def options(case_id: str):
    record = _record(case_id)
    plan = _plan(record)
    if request.method == "POST":
        lang = language_from_cookies(request.cookies)
        try:
            plan.set_options(_options_from_form(request.form, plan))
        except TranslatableError as e:
            return _options_page(record, plan, 400, error=e.message(lang), form=request.form)
        except PlanError:
            return _options_page(record, plan, 400, error=TranslatableError("error.invalid_input").message(lang),
                                 form=request.form)
        record.plan = plan
        store.save(record)
        return redirect(url_for("orthotic_modules.options", case_id=case_id, saved=1))
    return _options_page(record, plan, saved=request.args.get("saved") is not None,
                         chosen_logged=request.args.get("chosen") is not None)


@bp.route("/orthotics/<case_id>/choice", methods=["POST"])
def choice(case_id: str):
    record = _record(case_id)
    plan = _plan(record)
    lang = language_from_cookies(request.cookies)
    option_id = request.form.get("chosen") or ""
    try:
        reason = _text(request.form.get("reason"), "options.reason")
        if plan.option(option_id) is None:
            raise TranslatableError("error.choice_needs_option")
        if reason is None:
            raise TranslatableError("error.choice_needs_reason")
        plan.choose(option_id, reason)
    except TranslatableError as e:
        return _options_page(record, plan, 400, error=e.message(lang), form=request.form)
    record.plan = plan
    store.save(record)
    record_design_choice(record, ui_language=lang)
    return redirect(url_for("orthotic_modules.options", case_id=case_id, chosen=1))


# ---- Module 4: digital design -----------------------------------------------------


def _steps_from_form(form) -> dict[Step, StepRecord]:
    steps = {}
    for step in Step:
        prefix = f"step_{step.value}_"
        method = _member(Method, form.get(prefix + "method"))
        if method is not None and method not in STEP_METHODS[step]:
            raise TranslatableError("error.invalid_input")
        steps[step] = StepRecord(_member(StepStatus, form.get(prefix + "status")) or StepStatus.NOT_STARTED,
                                 method, _text(form.get(prefix + "notes"), f"step.{step.value}"))
    return steps


def _design_page(record: CaseRecord, plan: OrthoticPlan, status: int = 200, **context):
    passages, library_warning = _passages({f"step.{s.value}": sources.STEPS[s] for s in Step})
    page = _page("design.html", record, plan, "design", steps=list(Step), statuses=list(StepStatus),
                 step_methods=STEP_METHODS, parameters=PARAMETERS, passages=passages,
                 library_warning=library_warning, chosen=plan.option(plan.chosen), **context)
    return page, status


@bp.route("/orthotics/<case_id>/design", methods=["GET", "POST"])
def design(case_id: str):
    record = _record(case_id)
    plan = _plan(record)
    if request.method == "POST":
        lang = language_from_cookies(request.cookies)
        try:
            if request.form.get("action") == "parameters":
                values = {key: _text(request.form.get(f"param_{key}"), f"param.{key}") or "" for key in PARAMETERS}
                note = _text(request.form.get("param_note"), "design.version_note")
                if {k: v for k, v in values.items() if v} == plan.parameters:
                    raise TranslatableError("error.no_parameter_change")
                plan.save_parameters(values, note)
            else:
                plan.set_steps(_steps_from_form(request.form))
        except TranslatableError as e:
            return _design_page(record, plan, 400, error=e.message(lang), form=request.form)
        except PlanError:
            return _design_page(record, plan, 400, error=TranslatableError("error.invalid_input").message(lang),
                                form=request.form)
        record.plan = plan
        store.save(record)
        return redirect(url_for("orthotic_modules.design", case_id=case_id, saved=1))
    return _design_page(record, plan, saved=request.args.get("saved") is not None)

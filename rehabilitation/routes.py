"""The rehabilitation pages (SYSTEM_DESIGN.md §6.4; docs/design/05-rehabilitation/; plan Part 9, 2026-10-27).

GET  /rehabilitation                          what it does, and the cases to open (either domain)
GET  /rehabilitation/<case>/plan              1 Plan: goals agreed with the person, interventions with what the
                                              sources say, phases and the team (POST: action agreed, goals,
                                              interventions, phases or team)
GET  /rehabilitation/<case>/progress          2 Progress: measures by session as recorded, goal attainment, alerts
                                              (POST: measures, visits, alerts, score)
GET  /rehabilitation/<case>/training          3 Training with the device: tasks tied to the device's requirements
                                              or the goals, the home programme, what was seen for the device
                                              specialist (POST: tasks, home, observation, answer)
GET  /rehabilitation/<case>/home-programme    the home programme to print (?lang=ar|en)
GET  /rehabilitation/<case>/team              4 Team record: one timeline (?kind=therapy|device|medical), the
                                              handover (written by a person, signed), next steps (POST: entry,
                                              handover, sign, next_steps)

Every value is the team's; the tool writes, scores, doses and ranks nothing, and nothing is sent to a language
model. A refused form comes back as it was sent (400).
"""

import json
from dataclasses import dataclass
from typing import Optional

from flask import Blueprint, abort, redirect, render_template, request, url_for

from knowledge.catalog import load_catalog
from knowledge.retrieval import KnowledgeBaseMissing
from rehabilitation import sources
from rehabilitation.plan import (
    BACK_TO,
    SCORES,
    EntryKind,
    Goal,
    GoalScore,
    Handover,
    IcfLevel,
    Intervention,
    InterventionKind,
    NextStep,
    Observation,
    Phase,
    PhaseRecord,
    PhaseStatus,
    PlanError,
    RehabPlan,
    TaskStatus,
    TeamEntry,
    TeamMember,
    TeamRole,
    TrainingTask,
    next_id,
    now,
)
from shared import domains, forms
from shared import module_pages as pages
from shared.config import CASES_DIR
from shared.dates import DateError
from shared.followup import VisitStatus
from shared.i18n import TextKey, TranslatableError
from shared.store import CaseRecord, store

bp = Blueprint("rehab", __name__, template_folder="templates")

# Search the source library; replaced in the tests (no embedding model there).
find_passages = sources.find_passages
MAX_ROWS = forms.MAX_ROWS
LISTED_CASES = 20  # cases the first page offers, newest first


# ---- Helpers ------------------------------------------------------------------------------------------


def _record(case_id: str) -> CaseRecord:
    record = store.get(case_id)
    if record is None:
        abort(404, f"No case with id {case_id!r}")
    return record


def _plan(record: CaseRecord) -> RehabPlan:
    """A working copy of the case's rehabilitation (a refused form changes nothing that is kept)."""
    return RehabPlan.from_dict(record.rehab.to_dict()) if record.rehab else RehabPlan()


def _save(record: CaseRecord, plan: RehabPlan, endpoint: str, anchor: str = ""):
    record.rehab = plan
    store.save(record)
    return redirect(url_for(endpoint, case_id=record.case.case_id, saved=1) + anchor)


def _page(template: str, record: CaseRecord, plan: RehabPlan, module: str, status: int = 200, **context):
    page = render_template(template, part="rehabilitation", module=module, here=request.full_path.rstrip("?"),
                           part_args={"case_id": record.case.case_id}, case=record.case, record=record, plan=plan,
                           form=context.pop("form", None) or {}, error=context.pop("error", None),
                           saved=request.args.get("saved") is not None, **context)
    return page, status


def _requirements(record: CaseRecord) -> list:
    """The device's requirements (R1 ...) as its specialist wrote them (<domain>/plan.py), or none yet."""
    return list(getattr(record.plan, "requirements", None) or [])


def _limb(record: CaseRecord) -> str:
    return "lower" if record.case.is_lower_limb else "upper"


# ---- The first page -----------------------------------------------------------------------------------


@bp.route("/rehabilitation", methods=["GET"], endpoint="map")
def first_page():
    """What rehabilitation does, and the cases on this machine to open (newest first)."""
    seen, records = set(), []
    folder = store.folder or CASES_DIR
    paths = sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True) if folder and folder.is_dir() else []
    for record in reversed(store.all()):
        seen.add(record.case.case_id)
        records.append(record)
    for path in paths:
        if len(records) >= LISTED_CASES:
            break
        if path.stem in seen:
            continue
        try:
            record = store.get(path.stem)
        except (ValueError, KeyError, json.JSONDecodeError):
            continue
        if record is not None:
            records.append(record)
    return render_template("rehabilitation/map.html", part="rehabilitation", module="map", here=request.path,
                           case=None, records=records[:LISTED_CASES])


# ---- 1 Plan ---------------------------------------------------------------------------------------------


def _goals_from_form(form, plan: RehabPlan) -> list[Goal]:
    existing, goals = {g.id for g in plan.goals}, []
    ids = list(existing)
    for n in range(1, forms.count(form, "goal_rows", MAX_ROWS) + 1):
        p = f"goal_{n}_"
        text = forms.text(form.get(p + "text"), "rplan.goal")
        if text is None:
            continue  # an emptied row removes its goal
        level = forms.member(IcfLevel, form.get(p + "level"))
        if level is None:
            raise TranslatableError("error.goal_needs_level")
        goal_id = form.get(p + "id") or ""
        if goal_id not in existing:
            goal_id = next_id("G", ids)
            ids.append(goal_id)
        goals.append(Goal(goal_id, level, text, forms.text(form.get(p + "within"), "rplan.within"),
                          forms.date(form.get(p + "review_on"), "rplan.review_on")))
    if len(goals) > MAX_ROWS:
        raise TranslatableError("error.too_many_rows", field=TextKey("rplan.goals"), n=MAX_ROWS)
    return goals


def _interventions_from_form(form, plan: RehabPlan) -> list[Intervention]:
    existing, kept = {i.id for i in plan.interventions}, []
    ids, goal_ids = list(existing), set(plan.goal_ids())
    for n in range(1, forms.count(form, "int_rows", MAX_ROWS) + 1):
        p = f"int_{n}_"
        kind = forms.member(InterventionKind, form.get(p + "kind"))
        name = forms.text(form.get(p + "name"), "rplan.intervention_name")
        dose = forms.text(form.get(p + "dose"), "rplan.dose")
        served = form.getlist(p + "goal")
        if kind is None:
            if name or dose or served:
                raise TranslatableError("error.intervention_needs_kind")
            continue  # an emptied row removes its intervention
        if kind is InterventionKind.OTHER and not name:
            raise TranslatableError("error.intervention_other_needs_name")
        if set(served) - goal_ids:
            raise TranslatableError("error.invalid_input")
        item_id = form.get(p + "id") or ""
        if item_id not in existing:
            item_id = next_id("I", ids)
            ids.append(item_id)
        kept.append(Intervention(item_id, kind, name, served, dose))
    if len(kept) > MAX_ROWS:
        raise TranslatableError("error.too_many_rows", field=TextKey("rplan.interventions"), n=MAX_ROWS)
    return kept


def _plan_page(record: CaseRecord, plan: RehabPlan, status: int = 200, **context):
    kinds = [i.kind for i in plan.interventions]
    try:
        passages, library_warning = find_passages(kinds, _limb(record)), None
    except KnowledgeBaseMissing as e:
        passages, library_warning = {}, str(e)
    return _page("rehabilitation/plan.html", record, plan, "plan", status, passages=passages,
                 library_warning=library_warning, source_types={doc.id: doc.source_type for doc in load_catalog()},
                 levels=list(IcfLevel), kinds=list(InterventionKind), phases=list(Phase),
                 phase_statuses=list(PhaseStatus), roles=list(TeamRole), new_rows=forms.NEW_ROWS, **context)


@bp.route("/rehabilitation/<case_id>/plan", methods=["GET", "POST"])
def plan(case_id: str):
    record = _record(case_id)
    plan_ = _plan(record)
    if request.method == "POST":
        form, action = request.form, request.form.get("action")
        try:
            if action == "agreed":
                plan_.agreed_on = forms.date(form.get("agreed_on"), "rplan.agreed_on")
                plan_.review_every = forms.text(form.get("review_every"), "rplan.review_every")
            elif action == "goals":
                plan_.goals = _goals_from_form(form, plan_)
                known = set(plan_.goal_ids())  # a goal taken out leaves the interventions and tasks that named it
                for item in plan_.interventions:
                    item.goals = [g for g in item.goals if g in known]
                for task in plan_.tasks:
                    task.trains = [x for x in task.trains if not x.startswith("G") or x in known]
            elif action == "interventions":
                plan_.interventions = _interventions_from_form(form, plan_)
            elif action == "phases":
                plan_.phases = {phase.value: PhaseRecord(
                    forms.member(PhaseStatus, form.get(f"phase_{phase.value}_status")) or PhaseStatus.NOT_STARTED,
                    forms.text(form.get(f"phase_{phase.value}_when"), "rplan.phase_when")) for phase in Phase}
            elif action == "team":
                team = []
                for n in range(1, forms.count(form, "team_rows", MAX_ROWS) + 1):
                    role = forms.member(TeamRole, form.get(f"team_{n}_role"))
                    does = forms.text(form.get(f"team_{n}_does"), "rplan.does")
                    if role is None:
                        if does:
                            raise TranslatableError("error.team_needs_role")
                        continue
                    team.append(TeamMember(role, does))
                plan_.team = team
            else:
                raise TranslatableError("error.invalid_input")
            plan_ = RehabPlan.from_dict(plan_.to_dict())  # checked as a whole before it is kept
        except (TranslatableError, PlanError, DateError) as e:
            return _plan_page(record, _plan(record), 400, error=pages.refused(e), form=form)
        return _save(record, plan_, "rehab.plan")
    return _plan_page(record, plan_)


# ---- 2 Progress ---------------------------------------------------------------------------------------


def _progress_page(record: CaseRecord, plan: RehabPlan, status: int = 200, **context):
    return _page("rehabilitation/progress.html", record, plan, "progress", status, new_rows=forms.NEW_ROWS,
                 statuses=list(VisitStatus), back_to=BACK_TO, scores=SCORES, **context)


@bp.route("/rehabilitation/<case_id>/progress", methods=["GET", "POST"])
def progress(case_id: str):
    record = _record(case_id)
    plan_ = _plan(record)
    if request.method == "POST":
        form = request.form
        try:
            if form.get("action") == "score":
                goal = form.get("goal")
                if goal not in plan_.goal_ids():
                    raise TranslatableError("error.invalid_input")
                raw = (form.get("score") or "").strip().replace("−", "-")  # the page shows a minus sign
                if raw not in {f"{n:+d}" for n in SCORES} | {str(n) for n in SCORES}:
                    raise TranslatableError("error.score_needed")
                on = forms.date(form.get("on"), "rprog.scored_on")
                if on is None:
                    raise TranslatableError("error.score_date_needed")
                plan_.scores.append(GoalScore(goal, int(raw), on, forms.text(form.get("note"), "rprog.note")))
            else:
                forms.follow_up_from_form(form, plan_.follow_up, BACK_TO)
        except (TranslatableError, PlanError, DateError) as e:
            return _progress_page(record, _plan(record), 400, error=pages.refused(e), form=form)
        return _save(record, plan_, "rehab.progress")
    return _progress_page(record, plan_)


# ---- 3 Training with the device ---------------------------------------------------------------------------


def _training_page(record: CaseRecord, plan: RehabPlan, status: int = 200, **context):
    return _page("rehabilitation/training.html", record, plan, "training", status, new_rows=forms.NEW_ROWS,
                 requirements=_requirements(record), task_statuses=list(TaskStatus),
                 device_roles=[TeamRole.PROSTHETIST, TeamRole.ORTHOTIST, TeamRole.OTHER],
                 specialist=domains.part(record.case.domain, "nav").SPECIALIST, **context)


@bp.route("/rehabilitation/<case_id>/training", methods=["GET", "POST"])
def training(case_id: str):
    record = _record(case_id)
    plan_ = _plan(record)
    if request.method == "POST":
        form, action = request.form, request.form.get("action")
        try:
            if action == "tasks":
                known = {r.id for r in _requirements(record)} | set(plan_.goal_ids())
                existing, ids, tasks = {t.id for t in plan_.tasks}, [t.id for t in plan_.tasks], []
                for n in range(1, forms.count(form, "task_rows", MAX_ROWS) + 1):
                    p = f"task_{n}_"
                    text = forms.text(form.get(p + "text"), "rtrain.task")
                    if text is None:
                        continue
                    trains = form.getlist(p + "trains")
                    if set(trains) - known:
                        raise TranslatableError("error.invalid_input")
                    task_id = form.get(p + "id") or ""
                    if task_id not in existing:
                        task_id = next_id("T", ids)
                        ids.append(task_id)
                    tasks.append(TrainingTask(task_id, text, trains, forms.text(form.get(p + "stage"), "rtrain.stage"),
                                              forms.member(TaskStatus, form.get(p + "status")) or TaskStatus.NOT_STARTED))
                if len(tasks) > MAX_ROWS:
                    raise TranslatableError("error.too_many_rows", field=TextKey("rtrain.tasks"), n=MAX_ROWS)
                plan_.tasks = tasks
            elif action == "home":
                plan_.home_en = forms.long_text(form.get("home_en"), "rtrain.home_en")
                plan_.home_ar = forms.long_text(form.get("home_ar"), "rtrain.home_ar")
                plan_.home_checked_by = forms.text(form.get("home_checked_by"), "rtrain.checked_by")
            elif action == "observation":
                text = forms.text(form.get("text"), "rtrain.seen")
                role = forms.member(TeamRole, form.get("for_role"))
                if text is None or role is None:
                    raise TranslatableError("error.observation_incomplete")
                plan_.observations.append(Observation(text, role, now()))
            elif action == "answer":
                n = form.get("n", "")
                if not n.isdigit() or not 1 <= int(n) <= len(plan_.observations):
                    raise TranslatableError("error.invalid_input")
                seen = plan_.observations[int(n) - 1]
                answer = forms.text(form.get("answer"), "rtrain.answer")
                if answer is None or seen.answered_at:
                    raise TranslatableError("error.answer_needed")
                seen.answer, seen.answered_at = answer, now()
            else:
                raise TranslatableError("error.invalid_input")
        except (TranslatableError, PlanError, DateError) as e:
            return _training_page(record, _plan(record), 400, error=pages.refused(e), form=form)
        return _save(record, plan_, "rehab.training")
    return _training_page(record, plan_)


@bp.route("/rehabilitation/<case_id>/home-programme", methods=["GET"])
def home_programme(case_id: str):
    record = _record(case_id)
    lang = request.args.get("lang") if request.args.get("lang") in ("en", "ar") else "ar"
    return _page("rehabilitation/home_programme.html", record, _plan(record), "training", sheet_lang=lang)


# ---- 4 Team record ------------------------------------------------------------------------------------


@dataclass(frozen=True)
class TimelineItem:
    on: str
    kind: str  # an EntryKind value
    role: Optional[str]  # a TeamRole value; None: from a page of the record (a session, a device version)
    text: Optional[str]  # as written
    label: Optional[str] = None  # a text key for what it is (a session, a device version)
    number: Optional[int] = None


def team_timeline(record: CaseRecord, plan: RehabPlan) -> list[TimelineItem]:
    """What the team recorded, newest first: their entries, the progress sessions, the device's versions."""
    items = [TimelineItem(e.on, e.kind.value, e.role.value, e.text) for e in plan.entries]
    items += [TimelineItem(v.date, EntryKind.THERAPY.value, None, v.name, "rteam.session")
              for v in plan.follow_up.visits if v.date]
    for name, text_key, _ in domains.part(record.case.domain, "nav").RECORD_VERSIONS:
        for version in getattr(record.plan, name, None) or []:
            items.append(TimelineItem(version.saved_at[:10], EntryKind.DEVICE.value, None, None, text_key,
                                      version.number))
    return sorted(items, key=lambda i: i.on, reverse=True)


def _team_page(record: CaseRecord, plan: RehabPlan, status: int = 200, **context):
    shown = request.args.get("kind") if request.args.get("kind") in {k.value for k in EntryKind} else None
    items = team_timeline(record, plan)
    return _page("rehabilitation/team.html", record, plan, "team", status, items=items, shown=shown,
                 shown_items=[i for i in items if shown is None or i.kind == shown], kinds=list(EntryKind),
                 roles=list(TeamRole), new_rows=forms.NEW_ROWS, **context)


@bp.route("/rehabilitation/<case_id>/team", methods=["GET", "POST"])
def team(case_id: str):
    record = _record(case_id)
    plan_ = _plan(record)
    if request.method == "POST":
        form, action = request.form, request.form.get("action")
        try:
            if action == "entry":
                on = forms.date(form.get("on"), "rteam.on")
                role, kind = forms.member(TeamRole, form.get("role")), forms.member(EntryKind, form.get("kind"))
                text = forms.text(form.get("text"), "rteam.entry")
                if not (on and role and kind and text):
                    raise TranslatableError("error.entry_incomplete")
                plan_.entries.append(TeamEntry(on, role, kind, text, now()))
            elif action == "handover":
                text = forms.long_text(form.get("text"), "rteam.handover")
                by = forms.member(TeamRole, form.get("written_by"))
                if text is None or by is None:
                    raise TranslatableError("error.handover_incomplete")
                plan_.handovers.append(Handover(len(plan_.handovers) + 1, text, by, now()))
            elif action == "sign":
                latest, by = plan_.handover, forms.member(TeamRole, form.get("signed_by"))
                if latest is None or latest.signed_at or by is None:
                    raise TranslatableError("error.nothing_to_sign")
                latest.signed_at, latest.signed_by = now(), by
            elif action == "next_steps":
                plan_.next_steps = [NextStep(r["text"], forms.date(r["on"], "rteam.step_on"), r["done"])
                                    for r in forms.rows(form, "step", ("text", "on"), "rteam.next_steps",
                                                        flags=("done",)) if r["text"]]
            else:
                raise TranslatableError("error.invalid_input")
        except (TranslatableError, PlanError, DateError) as e:
            return _team_page(record, _plan(record), 400, error=pages.refused(e), form=form)
        return _save(record, plan_, "rehab.team")
    return _team_page(record, plan_)

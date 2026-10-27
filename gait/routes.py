"""The gait analysis pages (SYSTEM_DESIGN.md §6.3; docs/design/04-gait-analysis/; plan Part 10, 2026-10-27).

GET  /gait                              what it does, the prototype's decisions, the cases to open (either domain)
GET  /gait/<case>/capture               1 Capture: the sessions with their source, conditions and quality checks;
                                        POST adds one (its measures typed, or imported as a table)
GET  /gait/<case>/template.csv          the table to fill in
GET  /gait/<case>/interpret?session=    2 Interpret: the gait cycle side by side, each measure next to its reference
                                        band and smallest real change (the owner's, from a source), the knee curve
GET  /gait/<case>/indicators?session=   3 Indicators: values past a threshold, for the specialist to mark reviewed or
                                        dismiss with a reason (POST)
GET  /gait/<case>/compare?first=&second=&kind=
                                        4 Device and performance: two sessions, their conditions checked, the setting
                                        that changed, each measure's difference; POST sends the comparison to the case

This app measures nothing (gait/session.py); nothing here is sent to a language model. A refused form comes back as
it was sent (400).
"""

from typing import Optional

from flask import Blueprint, Response, abort, redirect, render_template, request, url_for

from gait import rules
from gait.session import (
    CURVES,
    MEASURES,
    SIDES,
    VIDEO_SOURCES,
    Comparison,
    ComparisonKind,
    GaitError,
    GaitRecord,
    Mark,
    Marker,
    Pace,
    Quality,
    Review,
    Session,
    Source,
    curve_points,
    now,
    read_table,
    table_template,
)
from shared import config, domains, forms
from shared import module_pages as pages
from shared.config import CASES_DIR
from shared.i18n import TranslatableError
from shared.store import CaseRecord, store

bp = Blueprint("gait", __name__, template_folder="templates")
LISTED_CASES = 20


# ---- Helpers ------------------------------------------------------------------------------------------


def _record(case_id: str) -> CaseRecord:
    record = store.get(case_id)
    if record is None:
        abort(404, f"No case with id {case_id!r}")
    return record


def _gait(record: CaseRecord) -> GaitRecord:
    """A working copy of the case's gait record (a refused form changes nothing that is kept)."""
    return GaitRecord.from_dict(record.gait.to_dict()) if record.gait else GaitRecord()


def _save(record: CaseRecord, gait: GaitRecord, endpoint: str, **args):
    record.gait = gait
    store.save(record)
    return redirect(url_for(endpoint, case_id=record.case.case_id, saved=1, **args))


def _page(template: str, record: CaseRecord, gait: GaitRecord, module: str, status: int = 200, **context):
    page = render_template(template, part="gait", module=module, here=request.full_path.rstrip("?"),
                           part_args={"case_id": record.case.case_id}, case=record.case, record=record, gait=gait,
                           form=context.pop("form", None) or {}, error=context.pop("error", None),
                           saved=request.args.get("saved") is not None, measures=MEASURES, curves=CURVES,
                           sides=SIDES, **context)
    return page, status


def device_versions(record: CaseRecord) -> list[tuple[str, str, int, str]]:
    """The case's versioned device records (its domain's nav.py RECORD_VERSIONS): (value, text key, number, page)."""
    found = []
    for name, text_key, page in domains.part(record.case.domain, "nav").RECORD_VERSIONS:
        for version in getattr(record.plan, name, None) or []:
            found.append((f"{name}:{version.number}", text_key, version.number, page))
    return found


def _session_or_latest(gait: GaitRecord, session_id: Optional[str]) -> Optional[Session]:
    return gait.session(session_id) or (gait.sessions[-1] if gait.sessions else None)


def chart(points: list[float], width: int = 320, height: int = 140) -> dict:
    """A curve over the gait cycle as SVG polyline points, and the y scale it is drawn on (0 at the bottom unless a
    value is below it)."""
    low = min(0.0, min(points))
    high = max(70.0, max(points))
    high = (int(high / 10) + (1 if high % 10 else 0)) * 10
    span = (high - low) or 1
    step = width / (len(points) - 1)
    xy = [f"{i * step:.1f},{height - (value - low) / span * height:.1f}" for i, value in enumerate(points)]
    return {"points": " ".join(xy), "low": low, "high": high, "width": width, "height": height}


# ---- The first page -----------------------------------------------------------------------------------


@bp.route("/gait", methods=["GET"], endpoint="map")
def first_page():
    return render_template("gait/map.html", part="gait", module="map", here=request.path, case=None,
                           records=pages.recent_records(LISTED_CASES, CASES_DIR), thresholds=rules.load_thresholds(),
                           references=rules.load_references())


# ---- 1 Capture ----------------------------------------------------------------------------------------


def _number(form, name: str, label: str, whole: bool = False):
    return forms.optional_number(form.get(name), label, whole=whole)


def session_from_form(form, files, gait: GaitRecord, record: CaseRecord) -> Session:
    """A new session from the capture form, its measures typed or imported (an imported table wins)."""
    on = forms.date(form.get("on"), "gcap.on")
    if on is None:
        raise TranslatableError("error.gait_date_needed")
    source = forms.member(Source, form.get("source"))
    if source is None:
        raise TranslatableError("error.gait_source_needed")
    consent = bool(form.get("filming_consent"))
    if source in VIDEO_SOURCES and not consent:
        raise TranslatableError("error.gait_consent_needed")
    version = form.get("device_version") or None
    if version and version not in {v for v, _, _, _ in device_versions(record)}:
        raise TranslatableError("error.invalid_input")
    hidden_side = form.get("hidden_side") or None
    if hidden_side and hidden_side not in SIDES:
        raise TranslatableError("error.invalid_input")
    try:
        quality = Quality(_number(form, "frame_rate", "gcap.frame_rate"), _number(form, "trials", "gcap.trials", True),
                          _number(form, "trials_whole_body", "gcap.trials_whole_body", True),
                          _number(form, "steps", "gcap.steps", True),
                          _number(form, "hidden_foot_trials", "gcap.hidden_foot_trials", True), hidden_side,
                          forms.member(Marker, form.get("scale_marker")))
    except GaitError:
        raise TranslatableError("error.gait_trials") from None
    values: dict[str, dict[str, float]] = {}
    for measure, (_, sided) in MEASURES.items():
        by_side = {side: _number(form, f"m_{measure}_{side}", f"gait_measure.{measure}")
                   for side in (SIDES if sided else ("both",))}
        by_side = {side: value for side, value in by_side.items() if value is not None}
        if by_side:
            values[measure] = by_side
    curves: dict[str, dict[str, list[float]]] = {}
    try:
        for curve in CURVES:
            by_side = {side: curve_points(form.get(f"c_{curve}_{side}"), curve) for side in SIDES}
            by_side = {side: points for side, points in by_side.items() if points}
            if by_side:
                curves[curve] = by_side
        upload = files.get("table")
        if upload and upload.filename:
            raw = upload.read(config.GAIT_MAX_UPLOAD + 1)
            if len(raw) > config.GAIT_MAX_UPLOAD:
                raise TranslatableError("error.gait_table_too_big", n=config.GAIT_MAX_UPLOAD // 1000)
            try:
                text = raw.decode("utf-8")
            except UnicodeDecodeError:
                raise TranslatableError("error.gait_table_encoding") from None
            imported_values, imported_curves = read_table(text)
            values.update(imported_values)
            curves.update(imported_curves)
    except GaitError as e:
        raise TranslatableError("error.gait_table", detail=str(e)) from None
    if not values and not curves:
        raise TranslatableError("error.gait_no_measures")
    texts = {name: forms.text(form.get(name), f"gcap.{name}") for name in ("walkway", "device_state", "footwear",
                                                                             "aid", "notes")}
    return Session(gait.next_id(), on, source, texts["walkway"], forms.member(Pace, form.get("pace")),
                   texts["device_state"], version, texts["footwear"], texts["aid"],
                   consent if source in VIDEO_SOURCES else None, quality, values, curves, texts["notes"], now())


def _capture_page(record: CaseRecord, gait: GaitRecord, status: int = 200, **context):
    thresholds = rules.load_thresholds()
    return _page("gait/capture.html", record, gait, "capture", status, sources=list(Source), paces=list(Pace),
                 markers=list(Marker), versions=device_versions(record), min_steps=rules.min_steps(thresholds),
                 video_sources=[s.value for s in VIDEO_SOURCES], **context)


@bp.route("/gait/<case_id>/capture", methods=["GET", "POST"])
def capture(case_id: str):
    record = _record(case_id)
    gait = _gait(record)
    if request.method == "POST":
        try:
            gait.sessions.append(session_from_form(request.form, request.files, gait, record))
        except (TranslatableError, GaitError) as e:
            return _capture_page(record, _gait(record), 400, error=pages.refused(e), form=request.form)
        return _save(record, gait, "gait.capture")
    return _capture_page(record, gait)


@bp.route("/gait/<case_id>/template.csv", methods=["GET"])
def template(case_id: str):
    _record(case_id)
    return Response(table_template(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment; filename=gait_measures.csv"})


# ---- 2 Interpret --------------------------------------------------------------------------------------


@bp.route("/gait/<case_id>/interpret", methods=["GET"])
def interpret(case_id: str):
    record = _record(case_id)
    gait = _gait(record)
    session = _session_or_latest(gait, request.args.get("session"))
    charts = {}
    if session:
        for curve, by_side in session.curves.items():
            charts[curve] = {side: chart(points) for side, points in by_side.items()}
    references = rules.load_references()
    return _page("gait/interpret.html", record, gait, "interpret", session=session, charts=charts,
                 references=references, reference_for=lambda m, s: rules.reference_for(references, m, s))


# ---- 3 Indicators -------------------------------------------------------------------------------------


@bp.route("/gait/<case_id>/indicators", methods=["GET", "POST"])
def indicators(case_id: str):
    record = _record(case_id)
    gait = _gait(record)
    session = _session_or_latest(gait, request.values.get("session"))
    thresholds, references = rules.load_thresholds(), rules.load_references()
    found = rules.indicators(session, thresholds, references) if session else []
    error = None
    if request.method == "POST":
        try:
            if session is None or request.form.get("indicator") not in {i.id for i in found}:
                raise TranslatableError("error.invalid_input")
            mark = forms.member(Mark, request.form.get("mark"))
            words = forms.text(request.form.get("words"), "gind.words")
            if mark is None:
                raise TranslatableError("error.invalid_input")
            if mark is Mark.DISMISSED and not words:
                raise TranslatableError("error.gait_dismiss_reason")
            session.reviews.append(Review(request.form["indicator"], mark, words, now()))
        except (TranslatableError, GaitError) as e:
            error = pages.refused(e)
        else:
            return _save(record, gait, "gait.indicators", session=session.id)
    return _page("gait/indicators.html", record, _gait(record) if error else gait, "indicators",
                 400 if error else 200, error=error, form=request.form if error else None, session=session,
                 found=found, min_steps=rules.min_steps(thresholds))


# ---- 4 Device and performance -------------------------------------------------------------------------


@bp.route("/gait/<case_id>/compare", methods=["GET", "POST"])
def compare(case_id: str):
    record = _record(case_id)
    gait = _gait(record)
    values = request.values
    first, second = gait.session(values.get("first")), gait.session(values.get("second"))
    if first is None and second is None and len(gait.sessions) >= 2:
        first, second = gait.sessions[-2], gait.sessions[-1]
    raw_kind = values.get("kind")
    kind = ComparisonKind(raw_kind) if raw_kind in {k.value for k in ComparisonKind} else ComparisonKind.DEVICE_SETTING
    error = None
    if request.method == "POST":
        try:
            if first is None or second is None or first.id == second.id:
                raise TranslatableError("error.gait_two_sessions")
            gait.comparisons.append(Comparison(first.id, second.id, kind, now(),
                                               forms.text(request.form.get("note"), "gcmp.note")))
        except (TranslatableError, GaitError) as e:
            error = pages.refused(e)
        else:
            return _save(record, gait, "gait.compare", first=first.id, second=second.id, kind=kind.value)
    references = rules.load_references()
    same = first is not None and second is not None and first.id != second.id
    labels = {v: (key, n, page) for v, key, n, page in device_versions(record)}
    return _page("gait/compare.html", record, _gait(record) if error else gait, "compare", 400 if error else 200,
                 error=error, first=first, second=second, kind=kind, kinds=list(ComparisonKind),
                 differing=rules.differing_conditions(first, second) if same else [],
                 rows=rules.compared_values(first, second, references) if same else [], labels=labels)

"""Intake: Flask route + form for entering case data.

GET  /intake        -> show the intake form
POST /intake         -> build a Case from the form, run it through
                        knowledge -> reasoning, store the result, and
                        redirect to the review page for that case.
                        A form that can't be used comes back filled in as
                        it was sent, with a message (400).
                        With "switch_language" (the language button), the
                        form comes back filled in, in the other language,
                        and nothing is saved.

v1 thin-slice status: the form has an input for every Case field the gap
analysis checks. Prior devices get MAX_PRIOR_DEVICES fixed rows (no
JavaScript), which is enough to tell "not asked" from "asked, none" from
"has used a prosthesis".
"""

import math

from flask import Blueprint, abort, current_app, g, redirect, render_template, request, url_for

from knowledge.retrieval import KnowledgeBaseMissing, retrieve_relevant_chunks
from reasoning.component_support import component_support
from reasoning.fitting_support import fitting_support
from reasoning.gap_analysis import analyze_gaps
from shared.case_schema import (
    ActivityLevel,
    ActivityProfile,
    AmputationLevel,
    Case,
    Etiology,
    PriorDevice,
    ResidualLimb,
    Side,
    VolumeStability,
    WoundStatus,
)
from shared.i18n import LANGUAGES, TextKey, TranslatableError, language_from_cookies, set_language_cookie
from shared.store import CaseRecord, store

bp = Blueprint("intake", __name__, template_folder="templates")

MAX_PRIOR_DEVICES = 3  # device rows on the form
# Typed alone in the comorbidities box: asked, none reported. The Arabic
# form tells the user to type لا يوجد.
NONE_ANSWERS = ("none", "لا يوجد", "لا شيء")


def _required(form, name: str) -> str:
    # form[name] would raise KeyError, which Flask's debug mode shows as a
    # crash page (500) instead of the form with a message.
    value = form.get(name)
    if not value:
        raise TranslatableError(f"error.required.{name}")
    return value


# Each parser below refuses a value with the form's own label for the field
# (a shared/i18n.py key), never with Python's wording.

def _choice(enum_cls, raw: str, label: str):
    try:
        return enum_cls(raw)
    except ValueError:
        raise TranslatableError("error.unknown_choice", field=TextKey(label)) from None


def _optional_enum(enum_cls, raw: str | None, label: str):
    if not raw:
        return None
    return _choice(enum_cls, raw, label)


def _optional_number(raw: str | None, label: str, whole: bool = False, positive: bool = False):
    """The number typed, or None if left empty. 0 or more; greater than 0 if `positive`."""
    if not raw or not raw.strip():
        return None
    try:
        value = int(raw) if whole else float(raw)
    except ValueError:
        raise TranslatableError("error.whole_number" if whole else "error.number",
                                field=TextKey(label)) from None
    if not math.isfinite(value):  # "nan", "inf"
        raise TranslatableError("error.number", field=TextKey(label))
    if positive and value <= 0:
        raise TranslatableError("error.positive", field=TextKey(label))
    if value < 0:
        raise TranslatableError("error.not_negative", field=TextKey(label))
    return value


def _optional_list(raw: str | None) -> list[str] | None:
    # One item per line. Blank -> None (not recorded); "none" -> [] (asked, none reported).
    items = [line.strip() for line in (raw or "").splitlines() if line.strip()]
    if not items:
        return None
    if len(items) == 1 and items[0].lower() in NONE_ANSWERS:
        return []
    return items


def _optional_bool(raw: str | None) -> bool | None:
    if not raw:
        return None
    if raw not in ("yes", "no"):
        raise TranslatableError("error.yes_no", value=raw)
    return raw == "yes"


def _prior_devices(form) -> list[PriorDevice] | None:
    """The device rows as a list.

    Nothing filled in -> None (not recorded). "No prior prosthesis" ticked
    -> [] (asked, none used). A row's details without its description, or
    the box ticked together with a device, is refused.
    """
    devices = []
    for n in range(1, MAX_PRIOR_DEVICES + 1):
        raw = {part: (form.get(f"device_{n}_{part}") or "").strip()
               for part in ("description", "years", "current", "issues")}
        if not raw["description"]:
            if any(raw.values()):
                raise TranslatableError("error.device_details_only", n=n)
            continue
        try:
            devices.append(PriorDevice(
                device_description=raw["description"],
                years_used=_optional_number(raw["years"], "intake.years_used"),
                currently_using=_optional_bool(raw["current"]),
                issues=raw["issues"] or None,
            ))
        except TranslatableError as e:
            raise TranslatableError("error.device_invalid", n=n, detail=e) from e
    if form.get("no_prior_devices"):
        if devices:
            raise TranslatableError("error.no_prior_but_device")
        return []
    return devices or None


def _case_from_form(form) -> Case:
    return Case(
        amputation_level=_choice(AmputationLevel, _required(form, "amputation_level"),
                                 "intake.amputation_level"),
        side=_choice(Side, _required(form, "side"), "intake.side"),
        age_years=_optional_number(form.get("age_years"), "intake.age", whole=True),
        body_weight_kg=_optional_number(form.get("body_weight_kg"), "intake.body_weight", positive=True),
        etiology=_optional_enum(Etiology, form.get("etiology"), "intake.etiology"),
        months_since_amputation=_optional_number(form.get("months_since_amputation"),
                                                 "intake.months_since_amputation"),
        residual_limb=ResidualLimb(
            wound_status=_optional_enum(WoundStatus, form.get("wound_status"), "intake.wound_status"),
            volume_stability=_optional_enum(VolumeStability, form.get("volume_stability"),
                                            "intake.volume_stability"),
            skin_condition=form.get("skin_condition") or None,
            length_description=form.get("length_description") or None,
            pain=form.get("pain") or None,
            sensation=form.get("sensation") or None,
        ),
        activity=ActivityProfile(
            k_level=_optional_enum(ActivityLevel, form.get("k_level"), "intake.k_level"),
            description=form.get("activity_description") or None,
            functional_goals=form.get("functional_goals") or None,
        ),
        prior_devices=_prior_devices(form),
        comorbidities=_optional_list(form.get("comorbidities")),
        contralateral_limb_status=form.get("contralateral_limb_status") or None,
        cognitive_status=form.get("cognitive_status") or None,
        intake_notes=form.get("intake_notes") or None,
    )


def _render_form(error: str | None = None, form=None):
    return render_template(
        "intake_form.html",
        error=error,
        form=form or {},  # what was sent, so the form comes back filled in
        amputation_levels=list(AmputationLevel),
        sides=list(Side),
        etiologies=list(Etiology),
        wound_statuses=list(WoundStatus),
        volume_stabilities=list(VolumeStability),
        k_levels=list(ActivityLevel),
        max_prior_devices=MAX_PRIOR_DEVICES,
    )


@bp.route("/intake", methods=["GET"])
def show_form():
    return _render_form()


@bp.route("/intake", methods=["POST"])
def submit_form():
    switch_to = request.form.get("switch_language")
    if switch_to:
        # The language button: show the same form, filled in, in the other language.
        if switch_to not in LANGUAGES:
            abort(404)
        g.lang = switch_to  # the page is drawn in it before the browser has the cookie
        response = current_app.make_response(_render_form(form=request.form))
        set_language_cookie(response, switch_to)
        return response

    lang = language_from_cookies(request.cookies)
    try:
        case = _case_from_form(request.form)
    except ValueError as e:  # a value the form can't use (TranslatableError is a ValueError)
        if not isinstance(e, TranslatableError):
            # Not expected: the parsers above translate every refusal. Python's
            # wording goes to the server log only.
            current_app.logger.warning("intake value refused: %s", e)
            e = TranslatableError("error.invalid_input")
        return _render_form(error=e.message(lang), form=request.form), 400
    store.save(analyse_case(case))
    return redirect(url_for("review.show_case", case_id=case.case_id))


def analyse_case(case: Case) -> CaseRecord:
    """Everything the review page shows for a case: search, gaps, components, fitting.

    Used for a submitted form and for the prepared trial cases
    (intake/load_trial_cases.py), so both are analysed the same way.
    """
    warning = None
    try:
        chunks = retrieve_relevant_chunks(case)
    except KnowledgeBaseMissing as e:
        # Still list the gaps, but say plainly that no sources were searched.
        chunks, warning = {}, f"The source library was not searched: {e}"
    gaps = analyze_gaps(case, chunks)
    return CaseRecord(case=case, retrieved_chunks=chunks, gaps=gaps, knowledge_warning=warning,
                      components=component_support(case), fitting=fitting_support(case))

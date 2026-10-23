"""Orthotic intake: the form for an orthotic case (use case 03, stroke AFO; added 2026-10-22).

GET  /intake/orthotics  -> show the orthotic intake form
POST /intake/orthotics  -> build an OrthoticCase from the form, analyse it the
                           same way as a prosthetic case (search, AI summaries,
                           quote check: intake/routes.py analyse_case), store
                           it and redirect to its review page. A form that
                           can't be used comes back filled in as it was sent,
                           with a message in the page's language (400). With
                           "switch_language" it comes back in the other
                           language and nothing is saved.

The fields are a PROPOSAL awaiting the owner's and an orthotist's review
(shared/case_schema.py OrthoticCase). Every refusal names the field with the
form's own label, never Python's wording.
"""

import math

from flask import Blueprint, abort, current_app, g, redirect, render_template, request, url_for

from intake.routes import (
    MAX_PRIOR_DEVICES,
    _choice,
    _optional_bool,
    _optional_enum,
    _optional_list,
    _optional_number,
    _required,
    analyse_case,
)
from shared.case_schema import (
    GAIT_PHASES,
    MAX_ANKLE_DEGREES,
    DonningAbility,
    GaitDeviation,
    KneeInStance,
    OrthoticCase,
    OrthoticCondition,
    OrthoticExam,
    PriorDevice,
    SensationStatus,
    Side,
    ToneScale,
    Walking,
    WalkingStatus,
    YesNoUnknown,
)
from shared.i18n import LANGUAGES, TextKey, TranslatableError, language_from_cookies, set_language_cookie
from shared.store import store

bp = Blueprint("orthotic_intake", __name__, template_folder="templates")


def _degrees(raw: str | None, label: str) -> float | None:
    """A signed ankle angle in degrees (dorsiflexion positive), or None if left empty."""
    if not raw or not raw.strip():
        return None
    try:
        value = float(raw)
    except ValueError:
        raise TranslatableError("error.number", field=TextKey(label)) from None
    if not math.isfinite(value) or abs(value) > MAX_ANKLE_DEGREES:
        raise TranslatableError("error.angle", field=TextKey(label))
    return value


def _deviations(form) -> list[GaitDeviation] | None:
    """Ticked deviations. Nothing ticked -> None (gait not observed); "observed, none" -> []."""
    ticked = [_choice(GaitDeviation, raw, "ort.gait") for raw in form.getlist("deviation")]
    if form.get("no_deviations"):
        if ticked:
            raise TranslatableError("error.no_deviations_but_ticked")
        return []
    return ticked or None


def _prior_orthoses(form) -> list[PriorDevice] | None:
    """The device rows, as on the prosthetic form, with their own "none used" box."""
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
    if form.get("no_prior_orthoses"):
        if devices:
            raise TranslatableError("error.no_prior_orthosis_but_device")
        return []
    return devices or None


def _lines(raw: str | None) -> list[str] | None:
    items = [line.strip() for line in (raw or "").splitlines() if line.strip()]
    return items or None


def _case_from_form(form) -> OrthoticCase:
    speed = _optional_number(form.get("gait_speed_m_s"), "ort.gait_speed")
    speed_test = (form.get("gait_speed_test") or "").strip() or None
    if speed is not None and speed_test is None:
        raise TranslatableError("error.speed_needs_test")
    tone_scale = _optional_enum(ToneScale, form.get("tone_scale"), "ort.tone_scale")
    tone_grade = (form.get("tone_grade") or "").strip() or None
    if tone_grade is not None and tone_scale is None:
        raise TranslatableError("error.tone_needs_scale")
    return OrthoticCase(
        condition=_choice(OrthoticCondition, _required(form, "condition"), "ort.condition"),
        side=_choice(Side, _required(form, "side"), "ort.side"),
        months_since_onset=_optional_number(form.get("months_since_onset"), "ort.months_since_onset"),
        functional_goals=form.get("functional_goals") or None,
        age_years=_optional_number(form.get("age_years"), "intake.age", whole=True),
        body_weight_kg=_optional_number(form.get("body_weight_kg"), "intake.body_weight", positive=True),
        walking=Walking(
            status=_optional_enum(WalkingStatus, form.get("walking_status"), "ort.walking_status"),
            walking_aid=form.get("walking_aid") or None,
            gait_speed_m_s=speed,
            gait_speed_test=speed_test,
            falls_last_6_months=_optional_number(form.get("falls"), "ort.falls", whole=True),
            deviations=_deviations(form),
            other_deviations=form.get("other_deviations") or None,
        ),
        exam=OrthoticExam(
            dorsiflexion_knee_extended_deg=_degrees(form.get("df_knee_ext"), "ort.df_knee_ext"),
            dorsiflexion_knee_flexed_deg=_degrees(form.get("df_knee_flex"), "ort.df_knee_flex"),
            plantarflexor_tone_scale=tone_scale,
            plantarflexor_tone_grade=tone_grade,
            plantarflexor_tone_notes=form.get("tone_notes") or None,
            dorsiflexor_strength=form.get("df_strength") or None,
            knee_extensor_strength=form.get("ke_strength") or None,
            knee_in_stance=_optional_enum(KneeInStance, form.get("knee_in_stance"), "ort.knee_in_stance"),
            foot_posture=form.get("foot_posture") or None,
            protective_sensation=_optional_enum(SensationStatus, form.get("protective_sensation"),
                                                "ort.protective_sensation"),
            proprioception=_optional_enum(SensationStatus, form.get("proprioception"), "ort.proprioception"),
            skin_condition=form.get("skin_condition") or None,
        ),
        footwear=form.get("footwear") or None,
        donning=_optional_enum(DonningAbility, form.get("donning"), "ort.donning"),
        prior_orthoses=_prior_orthoses(form),
        implanted_electronic_device=_optional_enum(YesNoUnknown, form.get("implanted"), "ort.implanted"),
        requirements=_lines(form.get("requirements")),
        comorbidities=_optional_list(form.get("comorbidities")),
        cognitive_status=form.get("cognitive_status") or None,
        intake_notes=form.get("intake_notes") or None,
    )


def _render_form(error: str | None = None, form=None):
    return render_template(
        "orthotic_intake_form.html",
        error=error,
        form=form or {},  # what was sent, so the form comes back filled in
        conditions=list(OrthoticCondition),
        sides=list(Side),
        walking_statuses=list(WalkingStatus),
        deviations=list(GaitDeviation),
        gait_phases=GAIT_PHASES,
        ticked_deviations=form.getlist("deviation") if hasattr(form, "getlist") else [],
        tone_scales=list(ToneScale),
        knee_choices=list(KneeInStance),
        sensations=list(SensationStatus),
        donning_choices=list(DonningAbility),
        yes_no_unknown=list(YesNoUnknown),
        max_prior_devices=MAX_PRIOR_DEVICES,
    )


@bp.route("/intake/orthotics", methods=["GET"])
def show_form():
    return _render_form()


@bp.route("/intake/orthotics", methods=["POST"])
def submit_form():
    switch_to = request.form.get("switch_language")
    if switch_to:
        if switch_to not in LANGUAGES:
            abort(404)
        g.lang = switch_to
        response = current_app.make_response(_render_form(form=request.form))
        set_language_cookie(response, switch_to)
        return response

    lang = language_from_cookies(request.cookies)
    try:
        case = _case_from_form(request.form)
    except ValueError as e:  # TranslatableError is a ValueError
        if not isinstance(e, TranslatableError):
            current_app.logger.warning("orthotic intake value refused: %s", e)
            e = TranslatableError("error.invalid_input")
        return _render_form(error=e.message(lang), form=request.form), 400
    store.save(analyse_case(case, writer=current_app.config.get("RAG_WRITER")))
    return redirect(url_for("review.show_case", case_id=case.case_id))

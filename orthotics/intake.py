"""Orthotic intake: the form for an orthotic case (use case 03, stroke AFO; added 2026-10-22).

GET  /intake/orthotics            -> show the orthotic intake form
GET  /intake/orthotics?case=<id>  -> the same form, filled in from that case: re-assess
                                     (the design's "Re-assess, module 1")
POST /intake/orthotics            -> build an OrthoticCase from the form, analyse it the
                           same way as a prosthetic case (search, AI summaries,
                           quote check: reasoning/pathway.py analyse_case), store
                           it and redirect to its analysis page (module 1). A
                           re-assessed case keeps its id, its creation time and
                           its plan. A form that can't be used comes back filled
                           in as it was sent, with a message in the page's
                           language (400). With "switch_language" it comes back
                           in the other language and nothing is saved.

The fields are a PROPOSAL awaiting the owner's and an orthotist's review
(orthotics/case.py OrthoticCase). Every refusal names the field with the
form's own label, never Python's wording.
"""

import math

from flask import Blueprint, abort, current_app, g, redirect, render_template, request, url_for

from orthotics.case import (
    GAIT_PHASES,
    MAX_ANKLE_DEGREES,
    MEASURED_PATHS,
    DonningAbility,
    GaitDeviation,
    KneeInStance,
    OrthoticCase,
    OrthoticCondition,
    OrthoticExam,
    SensationStatus,
    ToneScale,
    Walking,
    WalkingStatus,
)
from orthotics.plan import linkable
from reasoning.pathway import analyse_case
from record import people
from record.access import log_access
from shared.case_schema import PriorDevice, Side, YesNoUnknown
from shared.forms import (
    MAX_PRIOR_DEVICES,
    choice,
    optional_bool,
    optional_enum,
    optional_list,
    optional_number,
    required,
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
    ticked = [choice(GaitDeviation, raw, "ort.gait") for raw in form.getlist("deviation")]
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
                years_used=optional_number(raw["years"], "intake.years_used"),
                currently_using=optional_bool(raw["current"]),
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


def how_field(path: str) -> str:
    """The form's name for "how it was measured" of a value (MEASURED_PATHS)."""
    return "how_" + path.replace(".", "__")


def _measured_how(form) -> dict[str, str]:
    how = {}
    for path in MEASURED_PATHS:
        text = (form.get(how_field(path)) or "").strip()
        if len(text) > 200:
            raise TranslatableError("error.too_long", field=TextKey("ort.how_measured"), n=200)
        if text:
            how[path] = text
    return how


def _case_from_form(form, case_id: str | None = None, created_at: str | None = None) -> OrthoticCase:
    kept = {"case_id": case_id, "created_at": created_at} if case_id else {}
    speed = optional_number(form.get("gait_speed_m_s"), "ort.gait_speed")
    speed_test = (form.get("gait_speed_test") or "").strip() or None
    if speed is not None and speed_test is None:
        raise TranslatableError("error.speed_needs_test")
    tone_scale = optional_enum(ToneScale, form.get("tone_scale"), "ort.tone_scale")
    tone_grade = (form.get("tone_grade") or "").strip() or None
    if tone_grade is not None and tone_scale is None:
        raise TranslatableError("error.tone_needs_scale")
    return OrthoticCase(
        condition=choice(OrthoticCondition, required(form, "condition"), "ort.condition"),
        side=choice(Side, required(form, "side"), "ort.side"),
        months_since_onset=optional_number(form.get("months_since_onset"), "ort.months_since_onset"),
        functional_goals=form.get("functional_goals") or None,
        goal_participation=form.get("goal_participation") or None,
        goal_body_function=form.get("goal_body_function") or None,
        measured_how=_measured_how(form),
        age_years=optional_number(form.get("age_years"), "intake.age", whole=True),
        body_weight_kg=optional_number(form.get("body_weight_kg"), "intake.body_weight", positive=True),
        walking=Walking(
            status=optional_enum(WalkingStatus, form.get("walking_status"), "ort.walking_status"),
            walking_aid=form.get("walking_aid") or None,
            gait_speed_m_s=speed,
            gait_speed_test=speed_test,
            falls_last_6_months=optional_number(form.get("falls"), "ort.falls", whole=True),
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
            knee_in_stance=optional_enum(KneeInStance, form.get("knee_in_stance"), "ort.knee_in_stance"),
            foot_posture=form.get("foot_posture") or None,
            protective_sensation=optional_enum(SensationStatus, form.get("protective_sensation"),
                                                "ort.protective_sensation"),
            proprioception=optional_enum(SensationStatus, form.get("proprioception"), "ort.proprioception"),
            skin_condition=form.get("skin_condition") or None,
            ulcer_infection_or_poor_blood_supply=optional_enum(YesNoUnknown, form.get("ulcer"), "ort.ulcer"),
        ),
        footwear=form.get("footwear") or None,
        donning=optional_enum(DonningAbility, form.get("donning"), "ort.donning"),
        prior_orthoses=_prior_orthoses(form),
        implanted_electronic_device=optional_enum(YesNoUnknown, form.get("implanted"), "ort.implanted"),
        requirements=_lines(form.get("requirements")),
        comorbidities=optional_list(form.get("comorbidities")),
        cognitive_status=form.get("cognitive_status") or None,
        intake_notes=form.get("intake_notes") or None,
        **kept,
    )


def form_from_case(case: OrthoticCase) -> dict:
    """The form's fields filled in from a saved case (re-assess): the names _case_from_form reads."""
    def text(value):
        if value is None:
            return ""
        if hasattr(value, "value"):
            return value.value
        return f"{value:g}" if isinstance(value, (int, float)) and not isinstance(value, bool) else str(value)

    walking, exam = case.walking, case.exam
    form = {
        "case_id": case.case_id, "condition": text(case.condition), "side": text(case.side),
        "months_since_onset": text(case.months_since_onset), "functional_goals": text(case.functional_goals),
        "goal_participation": text(case.goal_participation), "goal_body_function": text(case.goal_body_function),
        "age_years": text(case.age_years), "body_weight_kg": text(case.body_weight_kg),
        "walking_status": text(walking.status), "walking_aid": text(walking.walking_aid),
        "gait_speed_m_s": text(walking.gait_speed_m_s), "gait_speed_test": text(walking.gait_speed_test),
        "falls": text(walking.falls_last_6_months), "other_deviations": text(walking.other_deviations),
        "df_knee_ext": text(exam.dorsiflexion_knee_extended_deg), "df_knee_flex": text(exam.dorsiflexion_knee_flexed_deg),
        "tone_scale": text(exam.plantarflexor_tone_scale), "tone_grade": text(exam.plantarflexor_tone_grade),
        "tone_notes": text(exam.plantarflexor_tone_notes), "df_strength": text(exam.dorsiflexor_strength),
        "ke_strength": text(exam.knee_extensor_strength), "knee_in_stance": text(exam.knee_in_stance),
        "foot_posture": text(exam.foot_posture), "protective_sensation": text(exam.protective_sensation),
        "proprioception": text(exam.proprioception), "skin_condition": text(exam.skin_condition),
        "ulcer": text(exam.ulcer_infection_or_poor_blood_supply), "footwear": text(case.footwear),
        "donning": text(case.donning), "implanted": text(case.implanted_electronic_device),
        "requirements": "\n".join(case.requirements or []), "comorbidities": "\n".join(case.comorbidities or []),
        "cognitive_status": text(case.cognitive_status), "intake_notes": text(case.intake_notes),
    }
    if walking.deviations == []:
        form["no_deviations"] = "1"
    if case.prior_orthoses == []:
        form["no_prior_orthoses"] = "1"
    for n, device in enumerate(case.prior_orthoses or [], 1):
        form.update({f"device_{n}_description": device.device_description, f"device_{n}_years": text(device.years_used),
                     f"device_{n}_current": "" if device.currently_using is None else
                     ("yes" if device.currently_using else "no"), f"device_{n}_issues": text(device.issues)})
    for path, how in case.measured_how.items():
        form[how_field(path)] = how
    return form


class _Prefilled(dict):
    """A dict that answers getlist() like a submitted form (the ticked deviations)."""

    def __init__(self, data: dict, deviations: list[str]):
        super().__init__(data)
        self._deviations = deviations

    def getlist(self, name):
        return list(self._deviations) if name == "deviation" else []


def _render_form(error: str | None = None, form=None):
    return render_template(
        "orthotics/intake_form.html",
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
        measured_paths=MEASURED_PATHS,
        how_field=how_field,
        editing=(form or {}).get("case_id") or None,
    )


def _existing(case_id: str):
    record = store.get(case_id)
    if record is None or record.case.domain != "orthotics":
        abort(404)
    return record


@bp.route("/intake/orthotics", methods=["GET"])
def show_form():
    case_id = request.args.get("case")
    if case_id:  # re-assess: the case's own values, to change
        case = _existing(case_id).case
        return _render_form(form=_Prefilled(form_from_case(case), [d.value for d in case.walking.deviations or []]))
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
    existing = _existing(request.form["case_id"]) if request.form.get("case_id") else None
    try:
        if existing is not None:  # re-assess: the same case, its id and creation time kept
            case = _case_from_form(request.form, existing.case.case_id, existing.case.created_at)
        else:
            case = _case_from_form(request.form)
        # A new case may be attached to a person; a re-assessed one keeps the person it has.
        person = None if existing is not None else people.person_for_intake(request.form.get("person_code"))
    except ValueError as e:  # TranslatableError is a ValueError
        if not isinstance(e, TranslatableError):
            current_app.logger.warning("orthotic intake value refused: %s", e)
            e = TranslatableError("error.invalid_input")
        return _render_form(error=e.message(lang), form=request.form), 400
    if person is not None:  # attached before the analysis, so the person's consent to the cloud model applies
        people.attach_case(person, case)
        log_access(person.code, "attached_case", case.case_id)
    record = analyse_case(case, writer=current_app.config.get("RAG_WRITER"))
    if existing is not None and existing.plan is not None:
        # The orthotist's plan stays; a requirement keeps only what the re-assessed case still has.
        record.plan = existing.plan
        known = linkable(case)
        for requirement in record.plan.requirements:
            requirement.findings = [key for key in requirement.findings if key in known]
    store.save(record)
    return redirect(url_for("orthotic_modules.analysis", case_id=case.case_id))

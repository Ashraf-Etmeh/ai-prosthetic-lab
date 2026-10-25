"""Prosthetic intake: Flask route + form for entering case data.

GET  /prosthetics   -> the prosthetics map: the brief's prosthetics capabilities and where each is
GET  /intake        -> show the intake form
POST /intake         -> build a Case from the form, run it through
                        knowledge -> reasoning (reasoning/pathway.py), store
                        the result, and redirect to the review page for that case.
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

from flask import Blueprint, abort, current_app, g, redirect, render_template, request, url_for

from prosthetics.case import (
    ActivityLevel,
    ActivityProfile,
    AmputationLevel,
    Case,
    Etiology,
    ResidualLimb,
    VolumeStability,
    WoundStatus,
)
from prosthetics.modules import latest_case_id
from reasoning.pathway import analyse_case
from shared.case_schema import PriorDevice, Side
from shared.forms import (
    MAX_PRIOR_DEVICES,
    choice,
    optional_bool,
    optional_enum,
    optional_list,
    optional_number,
    required,
)
from shared.i18n import LANGUAGES, TranslatableError, language_from_cookies, set_language_cookie
from shared.store import store

bp = Blueprint("prosthetic_intake", __name__, template_folder="templates")


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
                years_used=optional_number(raw["years"], "intake.years_used"),
                currently_using=optional_bool(raw["current"]),
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
        amputation_level=choice(AmputationLevel, required(form, "amputation_level"),
                                 "intake.amputation_level"),
        side=choice(Side, required(form, "side"), "intake.side"),
        age_years=optional_number(form.get("age_years"), "intake.age", whole=True),
        body_weight_kg=optional_number(form.get("body_weight_kg"), "intake.body_weight", positive=True),
        etiology=optional_enum(Etiology, form.get("etiology"), "intake.etiology"),
        months_since_amputation=optional_number(form.get("months_since_amputation"),
                                                 "intake.months_since_amputation"),
        residual_limb=ResidualLimb(
            wound_status=optional_enum(WoundStatus, form.get("wound_status"), "intake.wound_status"),
            volume_stability=optional_enum(VolumeStability, form.get("volume_stability"),
                                            "intake.volume_stability"),
            skin_condition=form.get("skin_condition") or None,
            length_description=form.get("length_description") or None,
            pain=form.get("pain") or None,
            sensation=form.get("sensation") or None,
        ),
        activity=ActivityProfile(
            k_level=optional_enum(ActivityLevel, form.get("k_level"), "intake.k_level"),
            description=form.get("activity_description") or None,
            functional_goals=form.get("functional_goals") or None,
        ),
        prior_devices=_prior_devices(form),
        comorbidities=optional_list(form.get("comorbidities")),
        contralateral_limb_status=form.get("contralateral_limb_status") or None,
        cognitive_status=form.get("cognitive_status") or None,
        intake_notes=form.get("intake_notes") or None,
    )


def _render_form(error: str | None = None, form=None):
    return render_template(
        "prosthetics/intake_form.html",
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


@bp.route("/prosthetics", methods=["GET"])
def prosthetics_map():
    """The four modules and the brief's prosthetics capabilities they cover (since 2026-10-23; pages since 2026-10-24)."""
    return render_template("prosthetics/map.html", case=None, domain="prosthetics", module="map", here=request.path,
                           latest=latest_case_id())


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
            # Not expected: the parsers (shared/forms.py) translate every refusal. Python's
            # wording goes to the server log only.
            current_app.logger.warning("intake value refused: %s", e)
            e = TranslatableError("error.invalid_input")
        return _render_form(error=e.message(lang), form=request.form), 400
    # The app's writer can be replaced (tests: a fake one; the golden cases: none).
    store.save(analyse_case(case, writer=current_app.config.get("RAG_WRITER")))
    return redirect(url_for("review.show_case", case_id=case.case_id))

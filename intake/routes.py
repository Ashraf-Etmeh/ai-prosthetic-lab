"""Intake: Flask route + form for entering case data.

GET  /intake        -> show the intake form
POST /intake         -> build a Case from the form, run it through
                        knowledge -> reasoning, store the result, and
                        redirect to the review page for that case.

v1 thin-slice status: form covers the required fields (amputation level,
side) plus the most commonly-filled optional fields. It does not yet expose
every Case field (e.g. prior_devices has no form input yet) — see
FUTURE_WORK.md.
"""

from flask import Blueprint, redirect, render_template, request, url_for

from knowledge.retrieval import retrieve_relevant_chunks
from reasoning.gap_analysis import analyze_gaps
from shared.case_schema import (
    ActivityLevel,
    ActivityProfile,
    AmputationLevel,
    Case,
    Etiology,
    ResidualLimb,
    Side,
    VolumeStability,
    WoundStatus,
)
from shared.store import CaseRecord, store

bp = Blueprint("intake", __name__, template_folder="templates")


def _optional_enum(enum_cls, raw: str | None):
    if not raw:
        return None
    return enum_cls(raw)


def _optional_float(raw: str | None) -> float | None:
    if not raw:
        return None
    return float(raw)


def _optional_int(raw: str | None) -> int | None:
    if not raw:
        return None
    return int(raw)


def _optional_list(raw: str | None) -> list[str] | None:
    # One item per line. Blank -> None (not recorded); "none" -> [] (asked, none reported).
    items = [line.strip() for line in (raw or "").splitlines() if line.strip()]
    if not items:
        return None
    if len(items) == 1 and items[0].lower() == "none":
        return []
    return items


def _case_from_form(form) -> Case:
    return Case(
        amputation_level=AmputationLevel(form["amputation_level"]),
        side=Side(form["side"]),
        age_years=_optional_int(form.get("age_years")),
        body_weight_kg=_optional_float(form.get("body_weight_kg")),
        etiology=_optional_enum(Etiology, form.get("etiology")),
        months_since_amputation=_optional_float(form.get("months_since_amputation")),
        residual_limb=ResidualLimb(
            wound_status=_optional_enum(WoundStatus, form.get("wound_status")),
            volume_stability=_optional_enum(
                VolumeStability, form.get("volume_stability")
            ),
            skin_condition=form.get("skin_condition") or None,
            length_description=form.get("length_description") or None,
            pain=form.get("pain") or None,
            sensation=form.get("sensation") or None,
        ),
        activity=ActivityProfile(
            k_level=_optional_enum(ActivityLevel, form.get("k_level")),
            description=form.get("activity_description") or None,
            functional_goals=form.get("functional_goals") or None,
        ),
        comorbidities=_optional_list(form.get("comorbidities")),
        contralateral_limb_status=form.get("contralateral_limb_status") or None,
        cognitive_status=form.get("cognitive_status") or None,
        intake_notes=form.get("intake_notes") or None,
    )


def _render_form(error: str | None = None):
    return render_template(
        "intake_form.html",
        error=error,
        amputation_levels=list(AmputationLevel),
        sides=list(Side),
        etiologies=list(Etiology),
        wound_statuses=list(WoundStatus),
        volume_stabilities=list(VolumeStability),
        k_levels=list(ActivityLevel),
    )


@bp.route("/intake", methods=["GET"])
def show_form():
    return _render_form()


@bp.route("/intake", methods=["POST"])
def submit_form():
    try:
        case = _case_from_form(request.form)
    except ValueError as e:  # bad number or enum value
        return _render_form(error=str(e)), 400
    chunks = retrieve_relevant_chunks(case)
    gaps = analyze_gaps(case, chunks)
    store.save(CaseRecord(case=case, retrieved_chunks=chunks, gaps=gaps))
    return redirect(url_for("review.show_case", case_id=case.case_id))

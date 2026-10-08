"""Intake: Flask route + form for entering case data.

GET  /intake        -> show the intake form
POST /intake         -> build a Case from the form, run it through
                        knowledge -> reasoning, store the result, and
                        redirect to the review page for that case.

v1 thin-slice status: the form has an input for every Case field the gap
analysis checks. Prior devices get MAX_PRIOR_DEVICES fixed rows (no
JavaScript), which is enough to tell "not asked" from "asked, none" from
"has used a prosthesis".
"""

from flask import Blueprint, redirect, render_template, request, url_for

from knowledge.retrieval import KnowledgeBaseMissing, retrieve_relevant_chunks
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
from shared.store import CaseRecord, store

bp = Blueprint("intake", __name__, template_folder="templates")

MAX_PRIOR_DEVICES = 3  # device rows on the form


def _required(form, name: str) -> str:
    # form[name] would raise KeyError, which Flask's debug mode shows as a
    # crash page (500) instead of the form with a message.
    value = form.get(name)
    if not value:
        raise ValueError(f"{name} is required")
    return value


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


def _optional_bool(raw: str | None) -> bool | None:
    if not raw:
        return None
    if raw not in ("yes", "no"):
        raise ValueError(f"expected yes or no, got {raw!r}")
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
                raise ValueError(f"prior device {n}: describe the device, not only its details")
            continue
        try:
            devices.append(PriorDevice(
                device_description=raw["description"],
                years_used=_optional_float(raw["years"]),
                currently_using=_optional_bool(raw["current"]),
                issues=raw["issues"] or None,
            ))
        except ValueError as e:
            raise ValueError(f"prior device {n}: {e}") from e
    if form.get("no_prior_devices"):
        if devices:
            raise ValueError('"No prior prosthesis" is ticked, but a device is described')
        return []
    return devices or None


def _case_from_form(form) -> Case:
    return Case(
        amputation_level=AmputationLevel(_required(form, "amputation_level")),
        side=Side(_required(form, "side")),
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
        prior_devices=_prior_devices(form),
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
        max_prior_devices=MAX_PRIOR_DEVICES,
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
    warning = None
    try:
        chunks = retrieve_relevant_chunks(case)
    except KnowledgeBaseMissing as e:
        # Still list the gaps, but say plainly that no sources were searched.
        chunks, warning = {}, f"The source library was not searched: {e}"
    gaps = analyze_gaps(case, chunks)
    store.save(CaseRecord(case=case, retrieved_chunks=chunks, gaps=gaps, knowledge_warning=warning))
    return redirect(url_for("review.show_case", case_id=case.case_id))

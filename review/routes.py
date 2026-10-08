"""Review: page showing case + gap list, with approve/edit/reject buttons.

GET  /review/<case_id>            -> show case + gap list, and the decisions
                                     already logged for this case
POST /review/<case_id>/decision   -> validate the reviewer's decision and the
                                     per-gap judgements, append them to the
                                     review log, then redisplay the page with
                                     a confirmation banner. An invalid
                                     submission is refused (400) and nothing
                                     is logged.

v1 thin-slice status: "edit" records the decision plus a required note
rather than opening an editable form for the gap list itself — see
FUTURE_WORK.md.
"""

from typing import Optional

from flask import Blueprint, abort, redirect, render_template, request, url_for

from reasoning.gap_analysis import explain_gap
from review import decision_log
from review.decision_log import InvalidDecision, read_decisions, record_decision
from shared.i18n import DEFAULT_LANGUAGE, error_message, language_from_cookies, t
from shared.store import CaseRecord, store

bp = Blueprint("review", __name__, template_folder="templates")

# Form field name for a gap's judgement, e.g. "gap:residual_limb.wound_status"
GAP_FIELD_PREFIX = "gap:"


def _get_record(case_id: str) -> CaseRecord:
    record = store.get(case_id)
    if record is None:
        abort(404, f"No case found with id {case_id!r}")
    return record


def judgement_summary(entry: dict, lang: str = DEFAULT_LANGUAGE) -> str:
    """E.g. "2 needed, 1 not needed, 12 not marked" for one logged entry."""
    judgements = [gap["reviewer_judgement"] for gap in entry["gaps"]]
    parts = [
        (judgements.count("needed"), "summary.needed"),
        (judgements.count("not_needed"), "summary.not_needed"),
        (judgements.count(None), "summary.not_marked"),
    ]
    separator = t("summary.separator", lang)
    return separator.join(t(key, lang, n=count) for count, key in parts if count) or t(
        "summary.no_gaps", lang
    )


def _render_review(record: CaseRecord, error: Optional[str] = None, form=None):
    lang = language_from_cookies(request.cookies)
    logged = read_decisions(record.case.case_id)
    return render_template(
        "review.html",
        case=record.case,
        gaps=record.gaps,
        explain=lambda gap: explain_gap(gap, lang),
        chunks=record.retrieved_chunks,
        knowledge_warning=record.knowledge_warning,
        logged=[(entry, judgement_summary(entry, lang)) for entry in logged],
        log_name=decision_log.REVIEW_LOG_PATH.name,
        saved=request.args.get("saved") is not None and bool(logged),
        error=error,
        form=form or {},  # what was submitted, so a refused form keeps its choices
        gap_prefix=GAP_FIELD_PREFIX,
        here=url_for("review.show_case", case_id=record.case.case_id),
    )


@bp.route("/review/<case_id>", methods=["GET"])
def show_case(case_id: str):
    return _render_review(_get_record(case_id))


@bp.route("/review/<case_id>/decision", methods=["POST"])
def submit_decision(case_id: str):
    record = _get_record(case_id)
    # Gaps left on "not marked" send an empty value and are left out.
    judgements = {
        gap.field: request.form[GAP_FIELD_PREFIX + gap.field]
        for gap in record.gaps
        if request.form.get(GAP_FIELD_PREFIX + gap.field)
    }
    lang = language_from_cookies(request.cookies)
    try:
        record_decision(
            record,
            decision=request.form.get("decision", ""),
            note=request.form.get("note"),
            gap_judgements=judgements,
            ui_language=lang,
        )
    except InvalidDecision as e:
        return _render_review(record, error=error_message(e, lang), form=request.form), 400
    return redirect(url_for("review.show_case", case_id=case_id, saved=1))

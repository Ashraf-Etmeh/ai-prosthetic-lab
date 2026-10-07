"""Review: page showing case + gap list, with approve/edit/reject buttons.

GET  /review/<case_id>            -> show case + gap list
POST /review/<case_id>/decision   -> record the reviewer's decision, then
                                     redisplay the same page with a
                                     confirmation banner.

v1 thin-slice status: "edit" currently records the decision plus a free-text
note rather than opening an editable form for the gap list itself — see
FUTURE_WORK.md.
"""

from flask import Blueprint, abort, redirect, render_template, request, url_for

from review.decision_log import record_decision
from shared.config import DISCLAIMER
from shared.store import store

bp = Blueprint("review", __name__, template_folder="templates")


@bp.route("/review/<case_id>", methods=["GET"])
def show_case(case_id: str):
    record = store.get(case_id)
    if record is None:
        abort(404, f"No case found with id {case_id!r}")
    return render_template(
        "review.html",
        case=record.case,
        gaps=record.gaps,
        chunks=record.retrieved_chunks,
        knowledge_warning=record.knowledge_warning,
        disclaimer=DISCLAIMER,
        decision_recorded=request.args.get("decision"),
    )


@bp.route("/review/<case_id>/decision", methods=["POST"])
def submit_decision(case_id: str):
    record = store.get(case_id)
    if record is None:
        abort(404, f"No case found with id {case_id!r}")

    decision = request.form["decision"]  # "approve" | "edit" | "reject"
    note = request.form.get("note") or None
    record_decision(case_id=case_id, decision=decision, note=note)

    return redirect(url_for("review.show_case", case_id=case_id, decision=decision))

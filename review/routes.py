"""Review: page showing case + gap list + what the sources say, with approve/edit/reject buttons.

Since the RAG (2026-10-11) every statement and gap citation shows the AI's
short summary, labelled as AI, above the source's own words (checked word
for word, reasoning/quote_check.py). Where the AI could not answer, a banner
says why and the passages found are listed without summaries.

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

import json
from typing import Optional

from flask import Blueprint, abort, redirect, render_template, request, url_for

from knowledge.clinic_rules import load_rules
from knowledge.library import library_version
from orthotics.fields import FIELDS as ORTHOTIC_FIELDS
from quality import measures, results
from quality.releases import load_releases
from reasoning.gap_analysis import explain_gap
from reasoning.writer import configured_model
from review import decision_log
from review.decision_log import InvalidDecision, read_decisions, record_decision
from shared import domains
from shared.case_schema import DEFAULT_DOMAIN
from shared.config import CASES_DIR
from shared.fitting import GAIT_PHASES
from shared.i18n import DEFAULT_LANGUAGE, TEXT, error_message, language_from_cookies, t
from shared.module_pages import latest_case_id
from shared.store import CaseRecord, store

bp = Blueprint("review", __name__, template_folder="templates")

# Form field name for a gap's judgement, e.g. "gap:residual_limb.wound_status"
GAP_FIELD_PREFIX = "gap:"
# ... and for a component or fitting statement's, e.g. "opt:va_dod_ll_17_microprocessor_knee"
STATEMENT_FIELD_PREFIX = "opt:"
# ... and for the reason the reviewer gives with a gap's mark (log version 11), e.g. "why:residual_limb.pain"
GAP_REASON_PREFIX = "why:"


def _get_record(case_id: str) -> CaseRecord:
    record = store.get(case_id)
    if record is None:
        abort(404, f"No case found with id {case_id!r}")
    return record


def judgement_summary(entry: dict, lang: str = DEFAULT_LANGUAGE) -> str:
    """E.g. "2 needed, 12 not marked; components: 1 relevant, 6 not marked; design and
    fitting: 20 not marked" for one logged entry."""
    separator = t("summary.separator", lang)

    def counts(judgements: list, keys: list[tuple[str, str]]) -> str:
        return separator.join(
            t(key, lang, n=judgements.count(value)) for value, key in keys if judgements.count(value)
        )

    gaps = [gap["reviewer_judgement"] for gap in entry["gaps"]]
    summary = counts(gaps, [("needed", "summary.needed"), ("not_needed", "summary.not_needed"),
                            (None, "summary.not_marked")]) or t("summary.no_gaps", lang)
    # "components" is not in entries logged before version 3, "fitting" not before version 4.
    # An orthotic entry (version 6, "domain") holds the orthosis and FES options in "components".
    options = "summary.orthotic_options" if entry.get("domain") == "orthotics" else "summary.components"
    for part, heading in (("components", options), ("fitting", "summary.fitting")):
        statements = [s["reviewer_judgement"] for section in (entry.get(part) or {}).get("sections", [])
                      for s in section["statements"]]
        if statements:
            summary += t(heading, lang) + counts(
                statements, [("relevant", "summary.relevant"), ("not_relevant", "summary.not_relevant"),
                             ("summary_wrong", "summary.summary_wrong"), (None, "summary.not_marked")])
    return summary


def _render_review(record: CaseRecord, error: Optional[str] = None, form=None):
    lang = language_from_cookies(request.cookies)
    logged = read_decisions(record.case.case_id)
    return render_template(
        "review/review.html",
        case=record.case,
        orthotic=record.case.domain == "orthotics",
        gait_phases=GAIT_PHASES,
        # Orthotic gaps marked critical (a draft proposal; orthotics/fields.py FIELDS).
        critical={info.path for info in ORTHOTIC_FIELDS if info.critical}
        if record.case.domain == "orthotics" else set(),
        gaps=record.gaps,
        explain=lambda gap: explain_gap(gap, lang),
        chunks=record.retrieved_chunks,
        knowledge_warning=record.knowledge_warning,
        logged=[(entry, judgement_summary(entry, lang)) for entry in logged],
        log_name=decision_log.REVIEW_LOG_PATH.name,
        saved=request.args.get("saved") is not None and bool(logged),
        error=error,
        components=record.components,
        fitting=record.fitting,
        # The AI's answer per part: "ok", "unavailable" or "no passages" (empty: made before the RAG).
        generation=record.generation,
        ai_status={name: part.status for name, part in record.generation.parts.items()}
        if record.generation else {},
        passage=record.passage,  # a retrieved passage by its id, for the full text under a statement
        form=form or {},  # what was submitted, so a refused form keeps its choices
        gap_prefix=GAP_FIELD_PREFIX,
        statement_prefix=STATEMENT_FIELD_PREFIX,
        reason_prefix=GAP_REASON_PREFIX,
        max_reason=decision_log.MAX_REASON,
        library=library_version(),  # the source library's build, signed with the decision
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
    # A reason typed with a gap's mark, as typed (an empty one is left out).
    reasons = {gap.field: request.form[GAP_REASON_PREFIX + gap.field] for gap in record.gaps
               if (request.form.get(GAP_REASON_PREFIX + gap.field) or "").strip()}
    # Every marked statement is passed on, so one that isn't on the page is refused.
    statement_judgements = {
        name[len(STATEMENT_FIELD_PREFIX):]: value
        for name, value in request.form.items()
        if name.startswith(STATEMENT_FIELD_PREFIX) and value
    }
    lang = language_from_cookies(request.cookies)
    try:
        record_decision(
            record,
            decision=request.form.get("decision", ""),
            note=request.form.get("note"),
            gap_judgements=judgements,
            ui_language=lang,
            statement_judgements=statement_judgements,
            gap_reasons=reasons,
        )
    except InvalidDecision as e:
        return _render_review(record, error=error_message(e, lang), form=request.form), 400
    return redirect(url_for("review.show_case", case_id=case_id, saved=1))


# ---- The reasoning and review part's own pages (plan Part 4, 2026-10-25; docs/design/07-reasoning-and-review/) ----


@bp.route("/reasoning", methods=["GET"])
def pathway():
    """The six-step pathway every domain shares, its guards, what the system never outputs, the checks every
    answer passes (each with whether it is built), and where data goes, read from the settings."""
    return render_template(
        "review/pathway.html", part="review", module="pathway", here=request.path, case=None,
        model=configured_model(), library=library_version(), rules=load_rules(),
        clouds=[(domain, domains.part(domain, "rag").PROFILE.cloud_ai()) for domain in domains.DOMAINS])


@bp.route("/review", methods=["GET"])
def latest():
    """The review page of the case saved last, of any domain; the default domain's intake if there is none."""
    case_id = latest_case_id(None, CASES_DIR)
    if case_id is None:
        return redirect(url_for(domains.nav(DEFAULT_DOMAIN).INTAKE))
    return redirect(url_for("review.show_case", case_id=case_id))


def _case_files() -> list[dict]:
    """The case files on this machine (counts are taken from them, never their content)."""
    folder = store.folder or CASES_DIR
    files = []
    for path in sorted(folder.glob("*.json")) if folder and folder.is_dir() else []:
        try:
            files.append(json.loads(path.read_text(encoding="utf-8")))
        except ValueError:
            continue
    return files


@bp.route("/quality", methods=["GET"])
def quality():
    """Quality and audit: the measures before a release, the audit trail and the release gate, all read from what
    was recorded (quality/results.py, the review log, the case files, the owner's files): nothing is run here."""
    runs = results.read_runs()
    entries = read_decisions()
    owner_releases = load_releases()
    quoted = measures.quote_check_counts(_case_files())
    marks = measures.summary_wrong_counts(entries)
    return render_template(
        "review/quality.html", part="review", module="quality", here=request.path, case=None,
        versions=results.current_versions(),
        development=results.latest(runs, results.GOLDEN_CASES, set=results.DEVELOPMENT),
        held_out=results.latest(runs, results.GOLDEN_CASES, set=results.HELD_OUT),
        rag=results.latest(runs, results.GOLDEN_CASES, mode=results.RAG),
        quoted=quoted, removed_share=measures.share(quoted["removed"], quoted["kept"] + quoted["removed"]),
        marks=marks, wrong_share=measures.share(marks["wrong"], marks["marked"]),
        gate=measures.release_gate(runs, owner_releases[-1] if owner_releases else None),
        audit=measures.audit_rows(entries, runs, library_version(), load_rules(), owner_releases),
        texts=len(TEXT))

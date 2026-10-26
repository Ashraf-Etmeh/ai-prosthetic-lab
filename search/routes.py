"""The smart search page (use case 05; docs/design/08-search-and-education/Main.html; plan Part 6, 2026-10-25).

GET  /search          ?q=<question>&domain=..&kind=..&language=both|en|ar&year=2015|2020: the passages found
                      (order of match), what the sources say (AI sentences over checked quotes, only while the
                      owner's SEARCH_CLOUD_AI is on), and when nothing answers, a way to suggest a source. Each
                      search is logged (search/log.py), never who asked. "logged=<id>" re-shows a search already
                      logged (after a mark or a suggestion) without logging it again.
POST /search/mark     a mark on a search's answer: useful, not useful, or a summary is wrong
POST /search/suggest  a source suggested to the curator (shown on the knowledge sources page)

Nothing here ranks or recommends. Pinning a passage to a case comes in a later part (owner, 2026-10-25).
"""

from flask import Blueprint, abort, current_app, redirect, render_template, request, url_for

from knowledge.catalog import load_catalog
from knowledge.library import library_version
from knowledge.retrieval import KnowledgeBaseMissing
from knowledge.routes import KINDS
from reasoning.writer import default_writer
from search import engine
from search import log as search_log
from shared import config
from shared.i18n import language_from_cookies

bp = Blueprint("search", __name__, template_folder="templates")

DOMAIN_CHOICES = ("prosthetics", "orthotics", "gait", "rehabilitation")  # the catalog's, in the design's order
MAX_QUESTION = 500  # characters kept of a question
# The search; replaced in the tests (no embedding model there).
find = engine.find


def _filters(args) -> engine.Filters:
    year = args.get("year", "")
    return engine.Filters(
        domains=tuple(d for d in DOMAIN_CHOICES if d in args.getlist("domain")),
        kinds=tuple(k for k in KINDS if k in args.getlist("kind")),
        language=args.get("language") if args.get("language") in engine.LANGUAGES else "both",
        from_year=int(year) if year.isdigit() and int(year) in engine.FROM_YEARS else None,
    )


def _query(question: str, filters: engine.Filters, **extra) -> dict:
    """The search's own URL parameters, to come back to it."""
    return {"q": question, "domain": list(filters.domains), "kind": list(filters.kinds),
            "language": filters.language if filters.language != "both" else None, "year": filters.from_year, **extra}


@bp.route("/search", methods=["GET"])
def smart_search():
    question = (request.args.get("q") or "").strip()[:MAX_QUESTION]
    filters = _filters(request.args)
    catalog = load_catalog()
    kinds = {doc.id: doc.source_type for doc in catalog}
    context = {"question": question, "filters": filters, "domain_choices": DOMAIN_CHOICES, "kind_choices": KINDS,
               "languages": engine.LANGUAGES, "years": engine.FROM_YEARS, "library": library_version(),
               "sources": len(catalog), "kinds": kinds, "cloud": config.SEARCH_CLOUD_AI,
               "marked": request.args.get("marked") is not None, "suggested": request.args.get("suggested") is not None,
               "passages": [], "answer": None, "warning": None, "search_id": None, "ai_off": engine.AI_OFF_REASON}
    if question:
        try:
            passages = find(question, filters)
        except KnowledgeBaseMissing as error:
            passages, context["warning"] = [], str(error)
        answer = engine.summarise(question, passages, current_app.config.get("RAG_WRITER") or default_writer())
        search_id = request.args.get("logged")
        if not search_log.SEARCH_ID.fullmatch(search_id or ""):
            part = answer.part
            search_id = search_log.log_search(
                question, filters.to_dict(), [chunk.chunk_id for chunk in passages],
                {"status": part.status, "reason": part.reason, "model": part.model, "kept": len(part.items),
                 "removed": part.removed_items},
                {"prompt": config.SEARCH_PROMPT_VERSION, "library": library_version()},
                language_from_cookies(request.cookies))["id"]
        context.update(passages=passages, answer=answer, search_id=search_id,
                       documents=len({chunk.doc_id for chunk in passages}))
    return render_template("search/search.html", part="search", module="search", here=request.full_path.rstrip("?"),
                           case=None, **context)


def _back(**extra):
    question = (request.form.get("q") or "").strip()[:MAX_QUESTION]
    return redirect(url_for("search.smart_search", **_query(question, _filters(request.form), **extra)))


@bp.route("/search/mark", methods=["POST"])
def mark():
    search_id = request.form.get("search_id", "")
    try:
        search_log.log_mark(search_id, request.form.get("mark", ""))
    except ValueError:
        abort(400)
    return _back(logged=search_id, marked=1)


@bp.route("/search/suggest", methods=["POST"])
def suggest():
    search_id = request.form.get("search_id") or None
    question = (request.form.get("q") or "").strip()[:MAX_QUESTION]
    try:
        search_log.log_suggestion(search_id, question, request.form.get("note"))
    except ValueError:
        abort(400)
    return _back(logged=search_id, suggested=1)

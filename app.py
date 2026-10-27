"""AI Prosthetic Lab — Flask entry point.

Run locally with:
    python app.py

Wires together each part's pages (Flask blueprints): each domain's intake
and modules, the review and quality pages, the knowledge pages and the search and learning pages.
reasoning/ has no routes of its own: an intake calls reasoning/pathway.py as
part of handling a submitted case. The pages every part shares (header, style, base page) are
in shared/templates/; each part's own are in <part>/templates/<part>/.

The pages are in English or Arabic (shared/i18n.py). GET /language/<code>
remembers the choice in a cookie and goes back to the page it came from.
The intake forms switch language by posting themselves instead, so what was
typed stays in the form (prosthetics/intake.py, orthotics/intake.py).
"""

from flask import Flask, abort, g, redirect, request, url_for

from knowledge.catalog import attributions
from knowledge.routes import bp as knowledge_bp
from orthotics.intake import bp as orthotic_intake_bp
from orthotics.modules import bp as orthotic_modules_bp
from prosthetics.intake import bp as prosthetic_intake_bp
from prosthetics.modules import bp as prosthetic_modules_bp
from review.routes import bp as review_bp
from search.learning_routes import bp as learning_bp
from search.routes import bp as search_bp
from shared import domains
from shared.case_schema import DEFAULT_DOMAIN
from shared.i18n import (
    LANGUAGES,
    field_label,
    language_from_cookies,
    set_language_cookie,
    t,
    text_direction,
    value_label,
)


def _local_page(target: str) -> bool:
    """True for a page of this app ("/review/abc"), not another site.

    "//other.site" and "/\\other.site" look like local paths but browsers
    treat both as a link to other.site.
    """
    return target.startswith("/") and not target.startswith("//") and "\\" not in target


def create_app() -> Flask:
    app = Flask(__name__, template_folder="shared/templates")
    app.register_blueprint(prosthetic_intake_bp)  # /intake and /prosthetics (use cases 01, 02)
    app.register_blueprint(prosthetic_modules_bp)  # /prosthetics/<id>/...: modules 1-5 (plan Part 3)
    app.register_blueprint(orthotic_intake_bp)  # /intake/orthotics (use case 03, stroke AFO)
    app.register_blueprint(orthotic_modules_bp)  # /orthotics: the map and modules 1-6
    app.register_blueprint(review_bp)  # /review/<id>: what the sources say, and the reviewer's marks
    app.register_blueprint(knowledge_bp)  # /knowledge: sources, evidence, graph and expertise (plan Part 5)
    app.register_blueprint(search_bp)  # /search: smart search in the specialist library (plan Part 6)
    app.register_blueprint(learning_bp)  # /learn: case-based learning with teaching cases (plan Part 7)

    @app.context_processor
    def interface_language():
        # Available in every template: the chosen language and its helpers.
        # g.lang: a language chosen in this very request, before the browser has its cookie.
        lang = g.get("lang") or language_from_cookies(request.cookies)
        return {
            "lang": lang,
            "text_dir": text_direction(lang),
            "t": lambda key, **params: t(key, lang, **params),
            "field_label": lambda path: field_label(path, lang),
            "value_label": lambda member: value_label(member, lang),
            # (authors, licence) of a licensed source document, or None (knowledge/catalog.py).
            "attribution": lambda doc_id: attributions().get(doc_id),
            # The header's domains and what each shows (<domain>/nav.py), without naming a domain.
            "all_domains": domains.DOMAINS,
            "shared_parts": domains.SHARED_PARTS,  # the shared parts with pages (review/: reasoning and review)
            "default_domain": DEFAULT_DOMAIN,
            "domain_nav": domains.nav,
        }

    @app.route("/")
    def index():
        return redirect(url_for("prosthetic_intake.show_form"))

    @app.route("/language/<code>")
    def set_language(code: str):
        if code not in LANGUAGES:
            abort(404)
        target = request.args.get("next", "")
        response = redirect(target if _local_page(target) else url_for("index"))
        set_language_cookie(response, code)
        return response

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

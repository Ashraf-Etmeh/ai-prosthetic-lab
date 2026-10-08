"""AI Prosthetic Lab — Flask entry point.

Run locally with:
    python app.py

Wires together the intake and review blueprints. knowledge/ and reasoning/
have no routes of their own — they're called directly by intake/routes.py
as part of handling a submitted case.

The pages are in English or Arabic (shared/i18n.py). GET /language/<code>
remembers the choice in a cookie and goes back to the page it came from.
"""

from flask import Flask, abort, redirect, request, url_for

from intake.routes import bp as intake_bp
from review.routes import bp as review_bp
from shared.i18n import (
    LANGUAGE_COOKIE,
    LANGUAGES,
    field_label,
    language_from_cookies,
    t,
    text_direction,
    value_label,
)

LANGUAGE_COOKIE_DAYS = 365


def _local_page(target: str) -> bool:
    """True for a page of this app ("/review/abc"), not another site.

    "//other.site" and "/\\other.site" look like local paths but browsers
    treat both as a link to other.site.
    """
    return target.startswith("/") and not target.startswith("//") and "\\" not in target


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(intake_bp)
    app.register_blueprint(review_bp)

    @app.context_processor
    def interface_language():
        # Available in every template: the chosen language and its helpers.
        lang = language_from_cookies(request.cookies)
        return {
            "lang": lang,
            "text_dir": text_direction(lang),
            "t": lambda key, **params: t(key, lang, **params),
            "field_label": lambda path: field_label(path, lang),
            "value_label": lambda member: value_label(member, lang),
        }

    @app.route("/")
    def index():
        return redirect(url_for("intake.show_form"))

    @app.route("/language/<code>")
    def set_language(code: str):
        if code not in LANGUAGES:
            abort(404)
        target = request.args.get("next", "")
        response = redirect(target if _local_page(target) else url_for("index"))
        response.set_cookie(
            LANGUAGE_COOKIE, code, max_age=LANGUAGE_COOKIE_DAYS * 24 * 3600, samesite="Lax"
        )
        return response

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

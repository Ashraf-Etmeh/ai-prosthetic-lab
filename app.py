"""AI Prosthetic Lab — Flask entry point.

Run locally with:
    python app.py

Wires together the intake and review blueprints. knowledge/ and reasoning/
have no routes of their own — they're called directly by intake/routes.py
as part of handling a submitted case.
"""

from flask import Flask, redirect, url_for

from intake.routes import bp as intake_bp
from review.routes import bp as review_bp


def create_app() -> Flask:
    app = Flask(__name__)
    app.register_blueprint(intake_bp)
    app.register_blueprint(review_bp)

    @app.route("/")
    def index():
        return redirect(url_for("intake.show_form"))

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=True)

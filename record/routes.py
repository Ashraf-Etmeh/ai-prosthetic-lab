"""The patient record and governance pages (use case 07; SYSTEM_DESIGN.md §7.4; docs/design/09-patient-record/;
plan Part 8, 2026-10-27).

GET  /record                      the records on this machine; POST /record/new opens one under a new code
GET  /record/<code>               1 Record and follow-up: summary, timeline across domains (?domain=), outcome
                                  measures, follow-up schedule, hand-over notes; POST /record/<code>/note adds one
GET  /record/governance           2 Consent and governance, without a person: where data goes, who may see what,
                                  retention
GET  /record/<code>/governance    the same for a person, with their consent (POST /record/<code>/consent), the
                                  access trail and requests (POST /record/<code>/request: a copy, or a deletion)
GET  /record/<code>/copy          everything held about the person, for them to keep

Every look at or change to a person's record adds a line to the access trail (record/access.py). Nothing on
these pages is sent to a language model, and nothing is enforced by role until sign-in exists.
"""

from flask import Blueprint, abort, redirect, render_template, request, url_for

from record import access, governance, people
from record.timeline import record_view
from shared import domains
from shared.case_schema import recorded_value
from shared.i18n import LANGUAGES, language_from_cookies, t

bp = Blueprint("record", __name__, template_folder="templates")


def _person(code: str) -> people.Person:
    person = people.get_person(code)
    if person is None:
        abort(404)
    return person


def _page(template: str, module: str, person=None, error=None, status: int = 200, **context):
    page = render_template(template, part="record", module=module, here=request.full_path.rstrip("?"), case=None,
                           person=person, part_args={"code": person.code} if person else {}, error=error, **context)
    return page, status


def _error(e: people.PersonError) -> str:
    return e.message(language_from_cookies(request.cookies))


# ---- 1 Record and follow-up ----------------------------------------------------------------


@bp.route("/record", defaults={"code": None}, methods=["GET"])
@bp.route("/record/<code>", methods=["GET"])
def person(code, error=None, status=200):
    if code is None:
        return _page("record/people.html", "record", records=people.all_people())
    person_ = _person(code)
    if error is None:
        access.log_access(person_.code, "opened_record")
    view = record_view(person_)
    shown = request.args.get("domain")
    shown = shown if shown in view.domains_here() else None
    return _page("record/person.html", "record", person_, error, status, view=view, shown=shown,
                 events=[e for e in view.events if shown is None or e.domain == shown],
                 note_form=request.form if error else {})


@bp.route("/record/new", methods=["POST"])
def new():
    person_ = people.new_person()
    access.log_access(person_.code, "created")
    return redirect(url_for("record.governance", code=person_.code, created=1))


@bp.route("/record/<code>/note", methods=["POST"])
def note(code):
    person_ = _person(code)
    try:
        people.add_note(person_, request.form.get("text"))
    except people.PersonError as e:
        return person(code, error=_error(e), status=400)
    access.log_access(person_.code, "added_note")
    return redirect(url_for("record.person", code=code, saved=1) + "#notes")


# ---- 2 Consent and governance --------------------------------------------------------------


def _consent_language(person_) -> str:
    """The language the consent text is shown in: as asked, else the one it was last shown in, else the page's."""
    asked = request.values.get("consent_lang")
    if asked in LANGUAGES:
        return asked
    last = person_.consent[-1].language if person_ and person_.consent else None
    return last or language_from_cookies(request.cookies)


@bp.route("/record/governance", defaults={"code": None}, methods=["GET"], endpoint="governance")
@bp.route("/record/<code>/governance", methods=["GET"], endpoint="governance")
def governance_page(code, error=None, status=200):
    person_ = _person(code) if code else None
    if person_ is not None and error is None:
        access.log_access(person_.code, "opened_governance")
    consent_lang = _consent_language(person_)
    return _page("record/governance.html", "governance", person_, error, status,
                 roles=governance.load_roles(), retention=governance.load_retention(),
                 clouds=governance.cloud_uses(), provider=governance.provider(),
                 trail=access.trail(person_.code) if person_ else [],
                 consent_lang=consent_lang, consent_t=lambda key, **p: t(key, consent_lang, **p),
                 created=request.args.get("created") is not None, items=people.CONSENT_ITEMS)



@bp.route("/record/<code>/consent", methods=["POST"])
def consent(code):
    person_ = _person(code)
    item = request.form.get("item")
    try:
        people.record_consent(person_, item, request.form.get("answer"), request.form.get("consent_lang"))
    except people.PersonError as e:
        return governance_page(code, error=_error(e), status=400)
    access.log_access(person_.code, "consent", item)
    return redirect(url_for("record.governance", code=code, consent_lang=request.form.get("consent_lang"),
                            saved=1) + "#consent")


@bp.route("/record/<code>/request", methods=["POST"], endpoint="request")
def record_request(code):
    person_ = _person(code)
    kind = request.form.get("kind")
    try:
        people.record_request(person_, kind, request.form.get("by"))
    except people.PersonError as e:
        return governance_page(code, error=_error(e), status=400)
    if kind == "copy":
        access.log_access(person_.code, "copy_given")
        return redirect(url_for("record.copy", code=code))
    access.log_access(person_.code, "deletion_requested", request.form.get("by"))
    return redirect(url_for("record.governance", code=code, saved=1) + "#requests")


@bp.route("/record/<code>/copy", methods=["GET"])
def copy(code):
    person_ = _person(code)
    access.log_access(person_.code, "opened_copy")
    view = record_view(person_)
    shown_values = {}
    for case_id, record in view.records:
        if record is not None:
            fields = domains.part(record.case.domain, "fields").FIELDS
            values = [(info.path, recorded_value(record.case, info.path)) for info in fields]
            shown_values[case_id] = [(p, v) for p, v in values if v is not None]
    return _page("record/copy.html", "governance", person_, view=view, shown_values=shown_values,
                 trail=access.trail(person_.code))

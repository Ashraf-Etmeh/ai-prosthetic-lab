"""What every domain's module pages share on the server (SYSTEM_DESIGN.md §5): find the case, draw a page with
the header's context, save the specialist's plan, and say why a form was refused.

A domain's pages (prosthetics/modules.py, orthotics/modules.py) call these with
their own templates; the values on the forms are read by shared/forms.py. A
refused form comes back as it was sent, with a message in the page's language (400).
"""

import json
from typing import Optional

from flask import abort, redirect, render_template, request, url_for

from shared.case_schema import DEFAULT_DOMAIN
from shared.i18n import TranslatableError, language_from_cookies
from shared.store import CaseRecord, store


def record_for(case_id: str, domain: str) -> CaseRecord:
    """The saved case, if it is one of `domain`'s; 404 otherwise."""
    record = store.get(case_id)
    if record is None or record.case.domain != domain:
        abort(404, f"No {domain} case with id {case_id!r}")
    return record


def render_module(template: str, record: CaseRecord, plan, module: str, status: int = 200, **context):
    """(the page, its status): the module page with what the shared header and case bar read."""
    page = render_template(
        template,
        case=record.case,
        record=record,
        plan=plan,
        domain=record.case.domain,
        module=module,
        here=request.path,
        form=context.pop("form", None) or {},
        error=context.pop("error", None),
        saved=request.args.get("saved") is not None,
        **context,
    )
    return page, status


def refused(error: Exception) -> str:
    """Why a form was refused, in the page's language (never Python's wording)."""
    lang = language_from_cookies(request.cookies)
    if isinstance(error, TranslatableError):
        return error.message(lang)
    return TranslatableError("error.invalid_input").message(lang)


def save_plan(record: CaseRecord, plan, endpoint: str, **args):
    """Keep the plan with the case (memory and its file), then show the page again with "Saved"."""
    record.plan = plan
    store.save(record)
    return redirect(url_for(endpoint, case_id=record.case.case_id, saved=1, **args))


def ui_language() -> str:
    return language_from_cookies(request.cookies)


def latest_case_id(domain: str, folder) -> Optional[str]:
    """The case of `domain` saved last (in memory, else in the cases folder), for a map page's links."""
    in_memory = [r for r in store.all() if r.case.domain == domain]
    if in_memory:
        return in_memory[-1].case.case_id
    folder = store.folder or folder
    if not folder or not folder.is_dir():
        return None
    for path in sorted(folder.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            saved = json.loads(path.read_text(encoding="utf-8"))["case"]
        except (ValueError, KeyError):
            continue
        if saved.get("domain", DEFAULT_DOMAIN) == domain:  # a case file without "domain" is the default's
            return path.stem
    return None

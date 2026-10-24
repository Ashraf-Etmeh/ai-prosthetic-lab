"""What every intake form shares: reading a submitted value, refused in the form's own words.

Each parser refuses a value with the form's own label for the field (a
shared/i18n.py key), never with Python's wording. Used by each domain's intake
(prosthetics/intake.py, orthotics/intake.py).
"""

import math

from shared.i18n import TextKey, TranslatableError

MAX_PRIOR_DEVICES = 3  # device rows on the form
# Typed alone in the comorbidities box: asked, none reported. The Arabic
# form tells the user to type لا يوجد.
NONE_ANSWERS = ("none", "لا يوجد", "لا شيء")


def required(form, name: str) -> str:
    # form[name] would raise KeyError, which Flask's debug mode shows as a
    # crash page (500) instead of the form with a message.
    value = form.get(name)
    if not value:
        raise TranslatableError(f"error.required.{name}")
    return value


# Each parser below refuses a value with the form's own label for the field
# (a shared/i18n.py key), never with Python's wording.

def choice(enum_cls, raw: str, label: str):
    try:
        return enum_cls(raw)
    except ValueError:
        raise TranslatableError("error.unknown_choice", field=TextKey(label)) from None


def optional_enum(enum_cls, raw: str | None, label: str):
    if not raw:
        return None
    return choice(enum_cls, raw, label)


def optional_number(raw: str | None, label: str, whole: bool = False, positive: bool = False):
    """The number typed, or None if left empty. 0 or more; greater than 0 if `positive`."""
    if not raw or not raw.strip():
        return None
    try:
        value = int(raw) if whole else float(raw)
    except ValueError:
        raise TranslatableError("error.whole_number" if whole else "error.number",
                                field=TextKey(label)) from None
    if not math.isfinite(value):  # "nan", "inf"
        raise TranslatableError("error.number", field=TextKey(label))
    if positive and value <= 0:
        raise TranslatableError("error.positive", field=TextKey(label))
    if value < 0:
        raise TranslatableError("error.not_negative", field=TextKey(label))
    return value


def optional_list(raw: str | None) -> list[str] | None:
    # One item per line. Blank -> None (not recorded); "none" -> [] (asked, none reported).
    items = [line.strip() for line in (raw or "").splitlines() if line.strip()]
    if not items:
        return None
    if len(items) == 1 and items[0].lower() in NONE_ANSWERS:
        return []
    return items


def optional_bool(raw: str | None) -> bool | None:
    if not raw:
        return None
    if raw not in ("yes", "no"):
        raise TranslatableError("error.yes_no", value=raw)
    return raw == "yes"

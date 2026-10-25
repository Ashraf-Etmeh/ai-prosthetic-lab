"""A date as the forms and the records keep it: YYYY-MM-DD (fit, follow-up and the visits of every domain)."""

from datetime import date
from typing import Optional


class DateError(ValueError):
    """A value that isn't a date written as YYYY-MM-DD."""


def check_date(value: Optional[str]) -> Optional[str]:
    """A date as YYYY-MM-DD, or None. Raises DateError otherwise."""
    if value is None:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise DateError(f"not a date: {value!r}") from None

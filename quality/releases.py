"""The owner's release sign-offs (SYSTEM_DESIGN.md §7.2, the release gate: "Arabic texts checked, owner's sign-off").

data/quality/releases.csv is the owner's: one row per release, with the columns
release, signed_off_by, signed_on, arabic_checked_by, arabic_checked_on and
note. Code never writes or changes it, and the yardstick hook asks the owner
before Claude edits it (CLAUDE.md). The quality page shows its last row: who
checked the Arabic texts and when, and who signed the release off and when. A
row without a sign-off is a release awaiting the owner.

To sign a release off, the owner adds a row: the release (any name, e.g. the
commit or a date), their name and the date (YYYY-MM-DD); the Arabic check
likewise, by the Arabic-reading specialist who did it.
"""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from shared import config
from shared.dates import DateError, check_date

COLUMNS = ("release", "signed_off_by", "signed_on", "arabic_checked_by", "arabic_checked_on", "note")


@dataclass(frozen=True)
class Release:
    """One row of the owner's file, as written."""

    release: str
    signed_off_by: str
    signed_on: str
    arabic_checked_by: str
    arabic_checked_on: str
    note: str

    def __post_init__(self) -> None:
        if not self.release:
            raise ValueError("a row names its release")
        for who, when in (("signed_off_by", "signed_on"), ("arabic_checked_by", "arabic_checked_on")):
            if bool(getattr(self, who)) != bool(getattr(self, when)):
                raise ValueError(f"{self.release}: {who} and {when} go together")
            try:
                check_date(getattr(self, when) or None)
            except DateError:
                raise ValueError(f"{self.release}: {when} must be a date (YYYY-MM-DD), "
                                 f"got {getattr(self, when)!r}") from None

    @property
    def signed_off(self) -> bool:
        return bool(self.signed_on)

    @property
    def arabic_checked(self) -> bool:
        return bool(self.arabic_checked_on)


def load_releases(path: Optional[Path] = None) -> list[Release]:
    """The owner's rows, oldest first ([] if the file has none). ValueError if one is not valid."""
    path = path or config.RELEASES_PATH
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError(f"{path}: the columns must be exactly {', '.join(COLUMNS)}")
        rows = list(reader)
    releases = []
    for number, row in enumerate(rows, start=2):  # row 1 is the header
        if None in row:
            raise ValueError(f"{path}, row {number}: more cells than columns")
        values = {name: (row[name] or "").strip() for name in COLUMNS}
        if not any(values.values()):
            continue  # an empty line, e.g. left by a spreadsheet
        try:
            releases.append(Release(**values))
        except ValueError as error:
            raise ValueError(f"{path}, row {number}: {error}") from None
    return releases


def latest_release(path: Optional[Path] = None) -> Optional[Release]:
    releases = load_releases(path)
    return releases[-1] if releases else None

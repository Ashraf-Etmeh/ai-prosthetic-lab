"""Who may see what, how long a record is kept, and where each piece of data goes (SYSTEM_DESIGN.md §7.4 and §8;
plan Part 8, 2026-10-27).

data/governance/roles.csv and retention.csv are the owner's (protected by the yardstick hook); code never writes
them. Each row has a status: a draft is shown as a draft awaiting the owner's approval, an approved row names its
owner and approval date, as data/knowledge/clinic_rules.csv does. Nothing here is enforced until roles and
sign-in exist (owner, 2026-10-27): every page is open to whoever uses this machine, and the pages say so.

The table of where data goes is not a file: it is read from the settings the code follows (each domain's cloud
switch, the search's, the language model in use), so it can't say something the code does not do.
"""

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from shared import config, domains
from shared.dates import DateError, check_date

DRAFT, APPROVED = "draft", "approved"
STATUSES = (DRAFT, APPROVED)
# The roles of SYSTEM_DESIGN.md §2 that may open a record, in the order the page shows them.
ROLES = ("treating_specialist", "therapist", "rehab_physician", "gait_lab", "learner_educator", "curator",
         "owner_quality")
# What each column may say (an empty cell: not set).
ACCESS = {
    "record": ("yes", "sessions_only", "counts_only", "no"),
    "notes": ("yes", "no"),
    "sign": ("own_domain", "rehabilitation", "medical_review", "gait_reports", "rules_and_releases", "no"),
    "export": ("with_reason", "reports", "no"),
}
ROLE_COLUMNS = ("role", *ACCESS, "status", "version", "owner", "approved_on", "note")
SETTINGS = ("retention_period", "law")
RETENTION_COLUMNS = ("setting", "value", "status", "owner", "approved_on", "note")


@dataclass(frozen=True)
class RoleRow:
    role: str
    access: dict[str, Optional[str]]  # column -> its value, None: not set
    status: str
    version: int
    owner: str
    approved_on: str
    note: str


@dataclass(frozen=True)
class Setting:
    setting: str
    value: Optional[str]  # as the owner writes it (e.g. a period and the law's name); None: not set
    status: str
    owner: str
    approved_on: str
    note: str


def _check_status(where: str, status: str, owner: str, approved_on: str) -> None:
    if status not in STATUSES:
        raise ValueError(f"{where}: status must be one of {list(STATUSES)}, got {status!r}")
    if status == APPROVED:
        if not owner.strip():
            raise ValueError(f"{where}: an approved row names its owner")
        try:
            check_date(approved_on)
        except DateError:
            raise ValueError(f"{where}: approved_on must be a date (YYYY-MM-DD), got {approved_on!r}") from None
    elif approved_on:
        raise ValueError(f"{where}: a draft has no approved_on")


def _rows(path: Path, columns: tuple[str, ...]) -> list[dict]:
    if not path.is_file():
        return []
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != columns:
            raise ValueError(f"{path.name}: the columns must be {', '.join(columns)}")
        return [{k: (v or "").strip() for k, v in row.items()} for row in reader]


def load_roles(path: Optional[Path] = None) -> list[RoleRow]:
    """The owner's table of who may see what, each row checked (ValueError if one is not valid)."""
    rows = []
    for raw in _rows(path or config.ROLES_PATH, ROLE_COLUMNS):
        role = raw["role"]
        if role not in ROLES:
            raise ValueError(f"roles: role must be one of {list(ROLES)}, got {role!r}")
        access = {}
        for column, allowed in ACCESS.items():
            value = raw[column] or None
            if value is not None and value not in allowed:
                raise ValueError(f"roles, {role}: {column} must be one of {list(allowed)} or empty, got {value!r}")
            access[column] = value
        _check_status(f"roles, {role}", raw["status"], raw["owner"], raw["approved_on"])
        if not raw["version"].isdigit() or int(raw["version"]) < 1:
            raise ValueError(f"roles, {role}: version must be a whole number from 1")
        rows.append(RoleRow(role, access, raw["status"], int(raw["version"]), raw["owner"], raw["approved_on"],
                            raw["note"]))
    if len({r.role for r in rows}) != len(rows):
        raise ValueError("roles: a role is listed twice")
    return rows


def load_retention(path: Optional[Path] = None) -> dict[str, Setting]:
    """The owner's retention settings by name; a setting missing from the file is not set."""
    found = {}
    for raw in _rows(path or config.RETENTION_PATH, RETENTION_COLUMNS):
        if raw["setting"] not in SETTINGS:
            raise ValueError(f"retention: setting must be one of {list(SETTINGS)}, got {raw['setting']!r}")
        _check_status(f"retention, {raw['setting']}", raw["status"], raw["owner"], raw["approved_on"])
        if raw["status"] == APPROVED and not raw["value"]:
            raise ValueError(f"retention, {raw['setting']}: an approved setting has a value")
        found[raw["setting"]] = Setting(raw["setting"], raw["value"] or None, raw["status"], raw["owner"],
                                        raw["approved_on"], raw["note"])
    return {name: found.get(name) or Setting(name, None, DRAFT, "", "", "") for name in SETTINGS}


@dataclass(frozen=True)
class CloudUse:
    """Whether coded fields of one kind may go to the cloud model, as the code is set now."""

    what: str  # a domain, or "search"
    on: bool


def cloud_uses() -> list[CloudUse]:
    """Each domain's cloud switch and the search's, as the code reads them."""
    uses = [CloudUse(domain, bool(domains.part(domain, "rag").PROFILE.cloud_ai())) for domain in domains.DOMAINS]
    return uses + [CloudUse("search", bool(config.SEARCH_CLOUD_AI))]


def provider() -> str:
    """The language model in use (shared/config.py LLM_PROVIDER)."""
    return config.LLM_PROVIDER

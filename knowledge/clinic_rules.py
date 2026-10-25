"""The clinic's rules (SYSTEM_DESIGN.md §5 and §7.1): hard stops so far, each with its status, version, owner
and approval date.

data/knowledge/clinic_rules.csv is the owner's: one row per rule, with the
columns rule_id, domain, kind, status, version, owner, approved_on and source.
Code never writes or changes it, and the yardstick hook asks the owner before
Claude edits it (CLAUDE.md). The code that applies a rule is keyed by its id
(orthotics/hard_stops.py); this file says whether the rule is a draft or
approved, in which version, by whom and when. A draft is shown as a draft
awaiting the owner's approval; only an approved rule is shown as the clinic's.
A rule's wording on the page is the interface text "hard_rule.<rule_id>", in
English and Arabic (shared/i18n.py).

To approve a rule, the owner sets its status to "approved", its owner (who
approves it) and approved_on (YYYY-MM-DD); to change an approved rule, a new
version.
"""

import csv
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from shared import domains
from shared import config
from shared.dates import DateError, check_date

COLUMNS = ("rule_id", "domain", "kind", "status", "version", "owner", "approved_on", "source")
KINDS = ("hard_stop",)  # later: thresholds, checklists, follow-up intervals (SYSTEM_DESIGN.md §11.3)
DRAFT, APPROVED = "draft", "approved"
STATUSES = (DRAFT, APPROVED)
_RULE_ID = re.compile(r"[a-z][a-z0-9_]*")


@dataclass(frozen=True)
class ClinicRule:
    """One row of the owner's table, as written."""

    rule_id: str
    domain: str
    kind: str
    status: str
    version: int
    owner: str
    approved_on: str
    source: str

    def __post_init__(self) -> None:
        if not _RULE_ID.fullmatch(self.rule_id):
            raise ValueError(f"rule_id must be lower-case words joined by _, got {self.rule_id!r}")
        if self.domain not in domains.DOMAINS:
            raise ValueError(f"{self.rule_id}: domain must be one of {list(domains.DOMAINS)}, got {self.domain!r}")
        if self.kind not in KINDS:
            raise ValueError(f"{self.rule_id}: kind must be one of {list(KINDS)}, got {self.kind!r}")
        if self.status not in STATUSES:
            raise ValueError(f"{self.rule_id}: status must be one of {list(STATUSES)}, got {self.status!r}")
        if not isinstance(self.version, int) or self.version < 1:
            raise ValueError(f"{self.rule_id}: version must be a whole number from 1, got {self.version!r}")
        if self.approved:
            if not self.owner.strip() or not self.approved_on:
                raise ValueError(f"{self.rule_id}: an approved rule names its owner and approved_on")
            try:
                check_date(self.approved_on)
            except DateError:
                raise ValueError(f"{self.rule_id}: approved_on must be a date (YYYY-MM-DD), "
                                 f"got {self.approved_on!r}") from None
        elif self.approved_on:
            raise ValueError(f"{self.rule_id}: a draft has no approved_on")

    @property
    def approved(self) -> bool:
        return self.status == APPROVED


def load_rules(path: Optional[Path] = None) -> list[ClinicRule]:
    """The owner's rules (data/knowledge/clinic_rules.csv unless another file is given), each checked.
    ValueError if any is not valid."""
    path = path or config.CLINIC_RULES_PATH
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != COLUMNS:
            raise ValueError(f"{path}: the columns must be exactly {', '.join(COLUMNS)}; "
                             f"got {', '.join(reader.fieldnames or ())}")
        rows = list(reader)
    rules = []
    for number, row in enumerate(rows, start=2):  # row 1 is the header
        if None in row:  # csv puts cells beyond the header under None
            raise ValueError(f"{path}, row {number}: more cells than columns")
        if not any((value or "").strip() for value in row.values()):
            continue  # an empty line, e.g. left by a spreadsheet
        values = {name: (row[name] or "").strip() for name in COLUMNS}
        try:
            values["version"] = int(values["version"])
        except ValueError:
            raise ValueError(f"{path}, row {number}: version must be a whole number, got {row['version']!r}") from None
        try:
            rules.append(ClinicRule(**values))
        except ValueError as error:
            raise ValueError(f"{path}, row {number}: {error}") from None
    keys = [(rule.domain, rule.rule_id) for rule in rules]
    repeated = sorted({f"{d}/{r}" for d, r in keys if keys.count((d, r)) > 1})
    if repeated:
        raise ValueError(f"{path}: rules listed more than once: {', '.join(repeated)}")
    return rules


def rules_for(domain: str, kind: str, path: Optional[Path] = None) -> dict[str, ClinicRule]:
    """One domain's rules of one kind, by rule id."""
    return {rule.rule_id: rule for rule in load_rules(path) if rule.domain == domain and rule.kind == kind}

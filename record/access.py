"""The access trail (SYSTEM_DESIGN.md §7.4; plan Part 8, 2026-10-27): every look at or change to a person's
record, one line each in data/records/access_log.jsonl, only ever added to (protected by the yardstick hook), as
clinical record systems keep an audit trail the person can ask for.

Who did it is not recorded until roles and sign-in come (owner, 2026-10-27): each line says so ("who": null).
"""

import json
import threading
from datetime import datetime, timezone

from shared import config

ACCESS_VERSION = 1
ACTIONS = ("created", "opened_record", "opened_governance", "opened_copy", "consent", "attached_case", "added_note",
           "copy_given", "deletion_requested")
_write_lock = threading.Lock()


def log_access(code: str, action: str, detail: str | None = None) -> dict:
    """Add a line: when, which person's record, what was done (an ACTIONS key), and what to (e.g. a case id)."""
    if action not in ACTIONS:
        raise ValueError(f"unknown action {action!r}")
    line = {"access_version": ACCESS_VERSION, "at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "person": code, "action": action, "detail": detail, "who": None}
    path = config.ACCESS_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock, path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")
    return line


def trail(code: str) -> list[dict]:
    """One person's lines, newest first."""
    path = config.ACCESS_LOG_PATH
    if not path.is_file():
        return []
    lines = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    return [line for line in reversed(lines) if line.get("person") == code]

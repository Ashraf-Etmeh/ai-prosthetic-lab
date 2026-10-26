"""The search log (SYSTEM_DESIGN.md §7.3: "searches are logged without who asked"; owner's answer, 2026-10-25).

One JSON line per event in data/records/search_log.jsonl (config.SEARCH_LOG_PATH; on
this machine only, not in git; lines are only ever added, and the yardstick hook asks
before Claude edits it):

  search      id, logged_at, ui_language, question (as typed), filters, passages (chunk ids, in order of
              match), summary (whether the AI answered and why not, the sentences kept and removed),
              versions (prompt, library build)
  mark        logged_at, search_id, mark: "useful", "not_useful" or "summary_wrong"
  suggestion  logged_at, search_id, question, note: a source suggested to the curator

Never who asked: there is no login, and nothing names the person.
"""

import json
import re
import secrets
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from shared import config

SEARCH, MARK, SUGGESTION = "search", "mark", "suggestion"
MARKS = ("useful", "not_useful", "summary_wrong")
MAX_NOTE = 500  # characters in a suggestion's note
SEARCH_ID = re.compile(r"[0-9a-f]{12}")

_write_lock = threading.Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _append(entry: dict, path: Optional[Path] = None) -> dict:
    path = path or config.SEARCH_LOG_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock, path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def log_search(question: str, filters: dict, passages: list[str], summary: dict, versions: dict, ui_language: str,
               path: Optional[Path] = None) -> dict:
    return _append({"kind": SEARCH, "id": secrets.token_hex(6), "logged_at": _now(), "ui_language": ui_language,
                    "question": question, "filters": filters, "passages": passages, "summary": summary,
                    "versions": versions}, path)


def log_mark(search_id: str, mark: str, path: Optional[Path] = None) -> dict:
    if not SEARCH_ID.fullmatch(search_id or "") or mark not in MARKS:
        raise ValueError(f"a mark names a logged search and one of {MARKS}")
    return _append({"kind": MARK, "logged_at": _now(), "search_id": search_id, "mark": mark}, path)


def log_suggestion(search_id: Optional[str], question: str, note: Optional[str], path: Optional[Path] = None) -> dict:
    if search_id is not None and not SEARCH_ID.fullmatch(search_id):
        raise ValueError("not a search id")
    return _append({"kind": SUGGESTION, "logged_at": _now(), "search_id": search_id, "question": question,
                    "note": (note or "").strip()[:MAX_NOTE] or None}, path)


def read_log(path: Optional[Path] = None) -> list[dict]:
    path = path or config.SEARCH_LOG_PATH
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def counts(entries: list[dict]) -> dict:
    """{"searches", "answered" (with AI sentences), "no_passage", "suggestions", "marks": {mark: n}}: counts only."""
    searches = [e for e in entries if e.get("kind") == SEARCH]
    return {
        "searches": len(searches),
        "answered": sum(1 for e in searches if (e.get("summary") or {}).get("kept")),
        "no_passage": sum(1 for e in searches if not e.get("passages")),
        "suggestions": sum(1 for e in entries if e.get("kind") == SUGGESTION),
        "marks": {mark: sum(1 for e in entries if e.get("kind") == MARK and e.get("mark") == mark) for mark in MARKS},
    }

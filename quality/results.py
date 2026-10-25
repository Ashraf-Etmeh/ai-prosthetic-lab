"""Recorded results: what the quality page shows (SYSTEM_DESIGN.md §7.2, "measured before every release").

The page never runs anything itself. Each measuring run that is asked to record
itself appends one JSON line to data/quality/results/runs.jsonl
(config.QUALITY_RESULTS_PATH, in git; lines are only ever added):

  python scripts/verify_all.py --record          kind "release_check": the unit tests, the checks for
                                                 prompts 0-2 and the golden cases, each passed or failed
  python -m quality.golden_cases --record        kind "golden_cases": which set (development or held out),
                                                 how (without search, with search, with the AI), the cases
                                                 that passed, and with the AI the answer key covered and what
                                                 the quote check kept and removed
  python -m knowledge.evaluate --record          kind "search_quality" (plan Part 5): the search-quality
                                                 queries' hit@1 and hit@5, or (--orthotics) the orthotic topic
                                                 searches that found a right passage; the source page says a
                                                 test is due when the library was built after the last one

Every line carries the versions it ran with (current_versions(): the language
model set, each domain's prompt version, the library build), so a result is
always read next to what it measured. Held-out runs are made only when the owner
asks (CLAUDE.md); recording one never changes how it is run.
"""

import json
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from knowledge.library import library_version
from reasoning.writer import configured_model
from shared import config, domains

RELEASE_CHECK, GOLDEN_CASES, SEARCH_QUALITY = "release_check", "golden_cases", "search_quality"
KINDS = (RELEASE_CHECK, GOLDEN_CASES, SEARCH_QUALITY)
DEVELOPMENT, HELD_OUT = "development", "held_out"
NO_SEARCH, SEARCH, RAG = "no_search", "search", "rag"

_write_lock = threading.Lock()


def current_versions() -> dict:
    """What a result is measured with: the model set, each domain's prompt version, the library build."""
    return {
        "model": configured_model(),
        "prompts": {domain: domains.part(domain, "rag").PROFILE.prompt_version for domain in domains.DOMAINS},
        "library": library_version(),
    }


def record_run(kind: str, data: dict, path: Optional[Path] = None) -> dict:
    """Append one result line (with the time and the versions) and return it."""
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
    entry = {"recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "kind": kind, **data,
             "versions": current_versions()}
    path = path or config.QUALITY_RESULTS_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    with _write_lock, path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return entry


def read_runs(path: Optional[Path] = None) -> list[dict]:
    """Every recorded result, oldest first ([] before the first)."""
    path = path or config.QUALITY_RESULTS_PATH
    if not path.is_file():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def latest(runs: list[dict], kind: str, **match) -> Optional[dict]:
    """The last recorded result of a kind whose fields equal `match` (e.g. set="held_out")."""
    found = [run for run in runs if run.get("kind") == kind and all(run.get(k) == v for k, v in match.items())]
    return found[-1] if found else None

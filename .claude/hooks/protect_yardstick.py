"""Claude Code PreToolUse hook: ask the owner before Claude changes the evaluation yardstick.

The answer key, the golden cases, the owner's rule tables and the review logs
measure the app; an agent must not "fix" a failing measurement by editing
them (CLAUDE.md working rules; blueprint §5). For Edit, Write and
NotebookEdit on one of these paths, and for a shell command that names one
together with a write (a redirect, sed -i, mv, cp, rm, git checkout/restore,
Set-Content, ...), this hook answers "ask", so Claude Code shows the owner a
permission prompt with the reason. Reading them is never stopped.

Limits: a script that writes one of these files without naming it on the
command line is not seen here. The held-out cases are also hash-frozen
(quality/tests/test_golden_cases.py), and the app itself writes the review log
through review/decision_log.py, which this hook does not touch.

Reads the hook JSON on stdin; prints a decision only when it asks.
"""

import json
import os
import re
import sys
from pathlib import Path

PROTECTED = (
    "data/quality/golden_cases/",  # the development golden cases (their expectations)
    "data/quality/golden_cases_held_out/",  # the frozen held-out cases
    "data/quality/golden_cases_held_out.json",  # their freeze manifest (hashes)
    "prosthetics/component_guide.py",  # the answer key's component statements
    "prosthetics/fitting_guide.py",  # the answer key's fitting statements
    "data/knowledge/evidence_rules.csv",  # the owner's rule table
    "data/knowledge/clinic_rules.csv",  # the owner's clinic rules: each rule's status, version and approval
    "data/quality/releases.csv",  # the owner's release sign-offs and Arabic checks (the release gate)
    "data/quality/results/",  # recorded results: the measuring runs add lines, nobody edits them
    "data/records/review_log.jsonl",  # append-only: the app adds lines, nobody edits them
    "data/records/search_log.jsonl",  # append-only: the search page adds lines, nobody edits them
    "data/records/review_log.test.jsonl",
    "data/records/review_log.test-2026-10-23.jsonl",  # the 2 test lines moved out before the trial
)
FILE_TOOLS = ("Edit", "Write", "MultiEdit", "NotebookEdit")
SHELL_TOOLS = ("Bash", "PowerShell")
# What makes a shell command a write. Generous on purpose: a false "ask" costs one click.
WRITES = re.compile(
    r">|\b(sed\s+-i|perl\s+-[a-z]*i|tee|mv|cp|rm|rmdir|del|truncate|dd|patch|touch|"
    r"git\s+(mv|rm|checkout|restore|apply|reset|stash)|"
    r"set-content|add-content|out-file|remove-item|move-item|copy-item|rename-item|clear-content|new-item|"
    r"write_text|write_bytes|open\([^)]*['\"][wa])\b",
    re.IGNORECASE,
)


def native(path: str) -> str:
    """A Git Bash path such as /c/Users/x as Windows reads it (C:/Users/x); others unchanged."""
    match = re.match(r"^[/\\]([a-zA-Z])([/\\]|$)(.*)", path) if os.name == "nt" else None
    return f"{match.group(1).upper()}:/{match.group(3)}" if match else path


def project_relative(path: str, root: Path) -> str:
    """The path relative to the project, with forward slashes ("" if outside it)."""
    try:
        path, root = native(path), Path(native(str(root)))
        full = (root / path).resolve() if not os.path.isabs(path) else Path(path).resolve()
        return full.relative_to(root.resolve()).as_posix()
    except (ValueError, OSError):
        return ""


def protected(relative: str) -> str:
    """The protected entry this project-relative path falls under, or ""."""
    for entry in PROTECTED:
        if relative == entry.rstrip("/") or (entry.endswith("/") and relative.startswith(entry)):
            return entry
    return ""


def named_in(command: str) -> str:
    """The protected entry a shell command names, or "" (slashes either way, any case)."""
    text = command.replace("\\", "/").lower()
    return next((entry for entry in PROTECTED if entry.rstrip("/").lower() in text), "")


def decide(event: dict, root: Path) -> str:
    """The reason to ask, or "" to let the tool call go through its normal permission check."""
    tool, given = event.get("tool_name", ""), event.get("tool_input") or {}
    if tool in FILE_TOOLS:
        path = given.get("file_path") or given.get("notebook_path") or ""
        entry = protected(project_relative(path, root)) if path else ""
        if entry:
            return f"{entry} is part of the evaluation yardstick (CLAUDE.md): the owner approves every change to it."
    elif tool in SHELL_TOOLS:
        command = str(given.get("command", ""))
        entry = named_in(command)
        if entry and WRITES.search(command):
            return (f"This command may change {entry}, part of the evaluation yardstick (CLAUDE.md): "
                    "the owner approves every change to it.")
    return ""


def main() -> int:
    try:
        event = json.load(sys.stdin)
    except ValueError:
        return 0  # not a tool event this hook understands: say nothing
    root = Path(native(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or os.getcwd()))
    reason = decide(event, root)
    if reason:
        print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "ask",
                                                 "permissionDecisionReason": reason}}))
    return 0


if __name__ == "__main__":
    sys.exit(main())

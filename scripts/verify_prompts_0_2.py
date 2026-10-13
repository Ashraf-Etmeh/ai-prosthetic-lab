"""Verify that Prompts 0, 1 and 2 were done correctly. Read-only: it changes nothing.

  python scripts/verify_prompts_0_2.py                every check, without the search model
  python scripts/verify_prompts_0_2.py --with-model   also runs the real search over the trial cases (2.3m)
  python scripts/verify_prompts_0_2.py --practice-server [--practice-dir DIR] [--port 5001]
                                                      the app with the trial cases, on temporary data,
                                                      for the manual checks (docs/manual_checks_prompts_0_2.md)

Prompt 0 oriented the work (tests, CLAUDE.md, the design-and-fitting commit),
Prompt 1 stabilised the app for a trial, Prompt 2 built the trial tooling.
Each check prints one line: PASS / FAIL / SKIP / MANUAL, its id and the
evidence; details are indented below it. The MANUAL checks are described in
docs/manual_checks_prompts_0_2.md.

Safety. Nothing here writes to data/review_log.jsonl,
data/review_log.test.jsonl, data/cases/, data/trial/ or shared/i18n.py:
- cases, review logs, term sheets and copies of i18n.py live in temporary
  folders, and the app's case folder and review log are pointed at a
  temporary folder before any check runs;
- an audit hook refuses (and records) any attempt by this process to change
  a protected path, and check S.1 compares their fingerprints before and
  after, which also covers the test suite and report runs in subprocesses;
- git is only read (status, log, show, archive, rev-list, reflog, check-ignore);
- the embedding model is never loaded unless --with-model (or the practice server).

Exit status 1 if any check failed, else 0.
"""

import argparse
import contextlib
import csv
import difflib
import hashlib
import html
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import traceback
import unittest
from collections import Counter, defaultdict
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

DATA = ROOT / "data"
REAL_TRIAL_LOG = DATA / "review_log.jsonl"
REAL_TEST_LOG = DATA / "review_log.test.jsonl"
TERM_SHEET = DATA / "trial" / "arabic_terms.csv"
TRIAL_CASES = DATA / "trial" / "cases"
I18N_FILE = ROOT / "shared" / "i18n.py"
PROTECTED_FILES = (REAL_TRIAL_LOG, REAL_TEST_LOG, I18N_FILE)
PROTECTED_DIRS = (DATA / "cases", DATA / "trial")
VERIFICATION_FILES = {"scripts/verify_prompts_0_2.py", "docs/manual_checks_prompts_0_2.md"}
BASELINE_TEST_COUNT = 219  # when Prompt 0 ran
# The Claude API is never called from here (the RAG, 2026-10-11): the app's AI
# writer is switched off (shared/config.py OFFLINE_ENV), so every page shows
# the passages found without summaries, and nothing is sent anywhere.
os.environ["AI_PROSTHETIC_LAB_OFFLINE"] = "1"
CHILD_ENV = {**os.environ, "PYTHONIOENCODING": "utf-8"}


# ---- Safety net, installed before the project is imported -------------------

def _norm(path) -> str:
    return os.path.normcase(os.path.abspath(os.fsdecode(path)))


_PROTECTED = {_norm(p) for p in PROTECTED_FILES}
_PROTECTED_TREES = tuple(_norm(p) for p in PROTECTED_DIRS)
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
write_attempts: list[str] = []  # protected paths something in this process tried to change


def is_protected(path) -> bool:
    try:
        p = _norm(path)
    except TypeError:
        return False
    return p in _PROTECTED or any(p == tree or p.startswith(tree + os.sep) for tree in _PROTECTED_TREES)


def _audit(event: str, args: tuple) -> None:
    targets = []
    if event == "open":
        path, mode, flags = args
        if path is None or isinstance(path, int):
            return
        writing = flags & _WRITE_FLAGS if isinstance(flags, int) else any(c in (mode or "") for c in "wax+")
        if writing:
            targets = [path]
    elif event == "os.rename":  # also os.replace: (src, dst, ...)
        targets = list(args[:2])
    elif event == "shutil.copyfile":  # (src, dst)
        targets = [args[1]]
    elif event in ("os.remove", "os.rmdir", "os.mkdir", "shutil.rmtree", "os.truncate"):
        targets = [args[0]]
    for target in targets:
        if target is not None and not isinstance(target, int) and is_protected(target):
            write_attempts.append(f"{event}: {target}")
            raise PermissionError(f"verify_prompts_0_2 refused to change a protected path: {target}")


sys.addaudithook(_audit)

from markupsafe import escape  # noqa: E402  (Flask's own escaping, to match what the templates print)

from app import create_app  # noqa: E402
from intake import load_trial_cases  # noqa: E402
from intake.routes import analyse_case  # noqa: E402
from knowledge.models import ProtocolChunk  # noqa: E402
from reasoning.component_support import component_support  # noqa: E402
from reasoning.fitting_support import fitting_support  # noqa: E402
from reasoning.gap_analysis import analyze_gaps  # noqa: E402
from review import decision_log, trial_report  # noqa: E402
from shared import arabic_terms, config, i18n  # noqa: E402
from shared.case_schema import Case  # noqa: E402
from shared.field_guide import FIELDS_BY_PATH  # noqa: E402
from shared.store import CaseRecord, store  # noqa: E402

# Everything the app would write by default goes to a temporary folder instead.
REPORT_DEFAULT_LOG = trial_report.REVIEW_LOG_PATH  # the report's default --log, kept for check 2.7
_SCRATCH = Path(tempfile.mkdtemp(prefix="verify_prompts_0_2_"))
store.folder = _SCRATCH / "cases"
decision_log.REVIEW_LOG_PATH = _SCRATCH / "review_log.jsonl"
trial_report.REPORT_PATH = _SCRATCH / "report.csv"
arabic_terms.TERMS_PATH = _SCRATCH / "arabic_terms.csv"


# ---- Results ----------------------------------------------------------------

results: list[tuple[str, str, str]] = []  # (check id, status, evidence)
state: dict = {}  # facts one check finds and a later one uses
CHECKS = []


def report(status: str, check_id: str, evidence: str, details=()) -> None:
    results.append((check_id, status, evidence))
    print(f"{status:<6} {check_id:<5} {evidence}", flush=True)
    for line in details:
        print(f"{'':13}{line}", flush=True)


def verdict(passed: bool) -> str:
    return "PASS" if passed else "FAIL"


def check(check_id: str):
    def register(function):
        CHECKS.append((check_id, function))
        return function
    return register


# ---- Helpers ----------------------------------------------------------------

def git(*args: str) -> str:
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, encoding="utf-8",
                          check=True).stdout


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def rel(path: Path) -> str:
    return path.relative_to(ROOT).as_posix()


def visible_text(page: str) -> str:
    """The page without its tags, entities and bidi isolate marks: roughly what a reader sees."""
    return html.unescape(re.sub(r"<[^>]+>|[\u2068\u2069]", "", page))


def non_empty_lines(path: Path) -> list[str]:
    return [line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.is_file() else []


def run_capturing_stdout(function, *args):
    """Run a command's main(); it reconfigures sys.stdout, so give it a real text stream."""
    stream = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    with contextlib.redirect_stdout(stream):
        result = function(*args)
    stream.flush()
    return result, stream.buffer.getvalue().decode("utf-8")


def csv_sections(path: Path) -> dict[str, list[list[str]]]:
    """The trial report CSV as {section title: [header, rows...]}."""
    sections, title = {}, None
    with path.open(encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f):
            if row and row[0].startswith("# "):
                title = row[0][2:]
                sections[title] = []
            elif row and title:
                sections[title].append(row)
    return sections


def fingerprint() -> dict[str, str]:
    """sha256 of every protected file, or "absent"."""
    prints = {rel(p): sha256(p) if p.is_file() else "absent" for p in PROTECTED_FILES}
    for folder in PROTECTED_DIRS:
        if not folder.exists():
            prints[rel(folder) + "/"] = "absent"
            continue
        for path in sorted(folder.rglob("*")):
            if path.is_file():
                prints[rel(path)] = sha256(path)
    return prints


FAKE_PASSAGE = ProtocolChunk(
    chunk_id="verify_fake_guideline_2024-0001",
    text="Residual limb volume should be stable before the definitive socket is cast.",
    source="verify/fake_guideline.pdf",
    title="Fake Guideline for Verification",
    year=2024,
    page=3,
    end_page=3,
    language="en",
    score=0.71,
)
VOLUME, WOUND, PAIN = "residual_limb.volume_stability", "residual_limb.wound_status", "residual_limb.pain"


def one_fake_passage(case):
    """Stands in for the search: a passage for the volume gap only, so some gaps cite a source."""
    return {VOLUME: [FAKE_PASSAGE]}


def no_passages(case):
    return {}


@contextlib.contextmanager
def sandbox(retrieval=one_fake_passage, log: Path | None = None):
    """A test app whose case folder, review log and search are temporary or fake."""
    with tempfile.TemporaryDirectory(prefix="verify_") as tmp:
        tmp = Path(tmp)
        box = SimpleNamespace(tmp=tmp, cases=tmp / "cases", log=log or tmp / "review_log.jsonl")
        with patch.object(store, "folder", box.cases), \
                patch.object(decision_log, "REVIEW_LOG_PATH", box.log), \
                patch("intake.routes.retrieve_relevant_chunks", side_effect=retrieval):
            store._records.clear()
            app = create_app()
            app.testing = True
            box.client = app.test_client()
            try:
                yield box
            finally:
                store._records.clear()


def case_id_from(response) -> str:
    return response.headers["Location"].rsplit("/", 1)[-1]


# Every input on the intake form filled in (fake values, one in Arabic).
FULL_FORM = {
    "amputation_level": "transtibial", "side": "left",
    "etiology": "vascular", "months_since_amputation": "5", "age_years": "64", "body_weight_kg": "81",
    "wound_status": "healed", "volume_stability": "stable", "skin_condition": "intact",
    "length_description": "mid-length", "pain": "ألم شبحي خفيف", "sensation": "reduced",
    "k_level": "K2", "activity_description": "walks indoors", "functional_goals": "walk to the shop",
    "device_1_description": "PTB socket, SACH foot", "device_1_years": "2", "device_1_current": "no",
    "device_1_issues": "loose fit", "comorbidities": "Diabetes", "contralateral_limb_status": "foot ulcer healed",
    "cognitive_status": "intact", "intake_notes": "fake verification case",
}
# Filled in except two fields, so the case has gaps and one of them cites the fake passage.
FORM_WITH_GAPS = FULL_FORM | {"volume_stability": "", "age_years": ""}
TEXTAREAS = {"activity_description", "functional_goals", "comorbidities", "intake_notes"}
SELECTS = {"amputation_level", "side", "etiology", "wound_status", "volume_stability", "k_level", "device_1_current"}


def value_kept(page: str, name: str, value: str) -> bool:
    """Is `value` back in the form field `name` (an input, a textarea or a chosen option)?"""
    shown = re.escape(str(escape(value)))
    if name in TEXTAREAS:
        pattern = rf'<textarea id="{name}"[^>]*>{shown}</textarea>'
    elif name in SELECTS:
        pattern = rf'(?s)<select id="{name}"[^>]*>(?:(?!</select>).)*<option value="{re.escape(value)}" selected>'
    else:
        pattern = rf'name="{name}"[^>]*value="{shown}"'
    return re.search(pattern, page) is not None


IDENTIFIER_KEY = re.compile(
    r"(^|_)(name|first_?name|last_?name|surname|full_?name|dob|birth\w*|address|street|post_?code|zip_?code|"
    r"mrn|record_?(number|no|id)|medical_record\w*|national_id|ssn|phone\w*|mobile|telephone|e_?mail|"
    r"passport\w*)($|_)", re.IGNORECASE)
IDENTIFIER_VALUES = (
    ("an email address", re.compile(r"[\w.+-]+@[\w-]+\.[A-Za-z]{2,}")),
    ("a phone number", re.compile(r"(?<![\w.])\+?\d[\d ()-]{7,}\d(?![\w.])")),
    ("a calendar date", re.compile(r"\b(19|20)\d\d[-/.](0?[1-9]|1[0-2])[-/.](0?[1-9]|[12]\d|3[01])\b"
                                   r"|\b(0?[1-9]|[12]\d|3[01])[-/.](0?[1-9]|1[0-2])[-/.](19|20)\d\d\b")),
    ("an identifier label", re.compile(r"\b(name|d\.?o\.?b\.?|date of birth|born|address|mrn|medical record|"
                                       r"record (no|number)|phone|e-?mail)\s*[:#]", re.IGNORECASE)),
    ("an Arabic identifier label", re.compile(r"الاسم|اسم المريض|تاريخ الميلاد|العنوان|رقم الملف|رقم السجل|"
                                              r"الرقم الطبي|رقم الهاتف|الجوال|البريد الإلكتروني")),
)


def identifier_findings(value, path: str = "") -> list[str]:
    """Keys or values that look like a patient identifier. created_at (when the record was made) is skipped."""
    found = []
    if isinstance(value, dict):
        for key, item in value.items():
            if IDENTIFIER_KEY.search(str(key)):
                found.append(f"key {path}{key}")
            if key != "created_at":
                found += identifier_findings(item, f"{path}{key}.")
    elif isinstance(value, list):
        for number, item in enumerate(value):
            found += identifier_findings(item, f"{path}{number}.")
    elif isinstance(value, str):
        for what, pattern in IDENTIFIER_VALUES:
            if pattern.search(value):
                found.append(f"{what} in {path.rstrip('.')}: {value[:50]!r}")
    return found


def count_keys(value) -> int:
    if isinstance(value, dict):
        return len(value) + sum(count_keys(item) for item in value.values())
    if isinstance(value, list):
        return sum(count_keys(item) for item in value)
    return 0


def load_module(path: Path, name: str):
    """A copy of shared/i18n.py, imported on its own."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def i18n_texts(module) -> dict[str, str]:
    """Every text in an i18n module, flattened: "TEXT[review.approve][ar]" -> text."""
    flat = {}
    for key, texts in module.TEXT.items():
        for lang, text in texts.items():
            flat[f"TEXT[{key}][{lang}]"] = text
    for lang, labels in module.FIELD_LABELS.items():
        for path, label in labels.items():
            flat[f"FIELD_LABELS[{lang}][{path}]"] = label
    for lang, enums in module.VALUE_LABELS.items():
        for enum, choices in enums.items():
            for value, label in choices.items():
                flat[f"VALUE_LABELS[{lang}][{enum}][{value}]"] = label
    return flat


_old_sources: dict = {}


def source_at(commit: str, path: str) -> str | None:
    """A file as it was at `commit`, or None if it didn't exist."""
    if (commit, path) not in _old_sources:
        proc = subprocess.run(["git", "show", f"{commit}:{path}"], cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8")
        _old_sources[(commit, path)] = proc.stdout if proc.returncode == 0 else None
    return _old_sources[(commit, path)]


# ---- Prompt 0: orient -------------------------------------------------------

@check("0.1")
def unit_tests():
    started = time.perf_counter()
    proc = subprocess.run([sys.executable, "-m", "unittest"], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", errors="replace", env=CHILD_ENV)
    output = proc.stderr + proc.stdout
    ran = re.search(r"Ran (\d+) tests? in ([\d.]+)s", output)
    last = (output.strip().splitlines() or [""])[-1]
    count = int(ran.group(1)) if ran else 0
    state["test_count"] = count
    failures = [line for line in output.splitlines() if line.startswith(("FAIL:", "ERROR:"))]
    report(verdict(proc.returncode == 0 and last.startswith("OK")), "0.1",
           f"python -m unittest: {last}; {count} tests (baseline {BASELINE_TEST_COUNT}), "
           f"{time.perf_counter() - started:.1f} s with start-up", failures[:20])


CLAUDE_ITEMS = [  # (what CLAUDE.md must cover, words that must all be in one paragraph or list item)
    ("decision support only: no diagnosing, prescribing, choosing or ranking components, judging readiness",
     ("never makes it", "diagnose", "prescribe", "choose a component", "rank components", "ready for fitting")),
    # Principles 2-3 and the quote rule reworded by the owner on 2026-10-11
    # (RAG: retrieval plus Claude summaries, each backed by a checked quote).
    # Before: "only the sources speak"; "no language model" ... "cloud";
    # "every new quote gets a word-for-word test".
    ("every sentence backed by the source's words, quoted with page",
     ("every sentence is backed by the source's own words", "word for word", "page")),
    ("search local, one cloud language model for the summaries", ("search stays local", "language model", "claude api")),
    ("fake data only, no patient identifiers", ("fake test data only", "identifiers")),
    ("English/Arabic interface, quotes kept in the source's language",
     ("english and arabic", "quotes", "language of their source")),
    ("rule: tests keep passing", ("all tests keep passing",)),
    ("rule: every quote checked word for word", ("every quote is checked word for word",)),
    ("rule: Arabic entry for new interface text", ("every new interface text gets its arabic entry",)),
    ("rule: log lines never edited or removed", ("append-only", "never edited or removed")),
    ("rule: LOG_VERSION raised on format changes", ("log_version", "raises")),
    # Reworded by the owner in step 3a (2026-10-10): "come only from the owner".
    ("rule: clinical judgements only from the owner", ("clinical judgements come only from the owner",)),
]
ROADMAP_WORDS = ("stabilise", "trial", "evidence fields", "golden-case", "smart search", "split", "orthotics")


def markdown_blocks(text: str) -> list[tuple[int, str]]:
    """(first line number, text) of each paragraph, heading or list item, markup removed."""
    blocks, current, start = [], [], 0
    for number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or re.match(r"(-|\d+\.)\s", stripped):
            if current:
                blocks.append((start, " ".join(current)))
            current = []
            if not stripped:
                continue
        if not current:
            start = number
        current.append(stripped.replace("**", "").replace("`", ""))
    if current:
        blocks.append((start, " ".join(current)))
    return blocks


@check("0.2")
def claude_md():
    path = ROOT / "CLAUDE.md"
    if not path.is_file():
        report("FAIL", "0.2", "CLAUDE.md is missing")
        return
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    blocks = markdown_blocks(text)
    details, found = [], 0
    for what, words in CLAUDE_ITEMS:
        hit = next((start for start, block in blocks if all(w in block.lower() for w in words)), None)
        found += hit is not None
        details.append(f"found   line {hit:>3}: {what} -- {lines[hit - 1].strip()[:70]}" if hit
                       else f"MISSING           {what} (looked for: {', '.join(words)})")
    roadmap = text.split("## Roadmap", 1)[1].split("\n## ", 1)[0] if "## Roadmap" in text else ""
    items = re.findall(r"^(\d+)\.\s+(.*)$", roadmap, re.MULTILINE)
    numbers = [int(n) for n, _ in items]
    in_order = numbers == list(range(1, 8)) and all(
        word in item.lower().replace("**", "") for word, (_, item) in zip(ROADMAP_WORDS, items))
    first_line = next((i for i, line in enumerate(lines, 1) if line.startswith("## Roadmap")), 0)
    details.append(f"{'found  ' if in_order else 'MISSING'} line {first_line:>3}: roadmap items {numbers} "
                   f"{'in order' if in_order else '(expected 1-7 in order)'}:")
    details += [f"          {n}. {item.strip()[:80]}" for n, item in items]
    report(verdict(found == len(CLAUDE_ITEMS) and in_order), "0.2",
           f"CLAUDE.md covers {found}/{len(CLAUDE_ITEMS)} principles and rules; roadmap 1-7 "
           f"{'in order' if in_order else 'NOT in order'}", details)


@check("0.3")
def git_status_clean():
    lines = git("status", "--porcelain", "--untracked-files=all").splitlines()
    others = [line for line in lines if line[3:].strip('"') not in VERIFICATION_FILES]
    added = sorted(line[3:] for line in lines if line[3:].strip('"') in VERIFICATION_FILES)
    report(verdict(not others), "0.3",
           f"git status: clean apart from this verification's files ({', '.join(added) or 'none yet'})"
           if not others else f"git status: {len(others)} other change(s), first: {others[0]}", others[:20])


@check("0.4")
def design_and_fitting_commit():
    added = git("log", "--diff-filter=A", "--format=%H", "--", "reasoning/fitting_guide.py").split()
    if not added:
        report("FAIL", "0.4", "no commit adds reasoning/fitting_guide.py")
        return
    commit = added[-1]
    state["design_commit"] = commit
    header = git("show", "-s", "--format=%h %ad %s", "--date=short", commit).strip()
    entries = [line.split("\t") for line in git("show", "--name-status", "--format=", commit).splitlines() if line]
    paths = {entry[-1] for entry in entries}
    wanted = ["reasoning/fitting_guide.py", "reasoning/fitting_support.py", "tests/test_fitting_support.py",
              "tests/test_component_guide.py", "review/templates/review.html"]
    missing = [p for p in wanted if p not in paths]
    report(verdict(not missing), "0.4",
           f"{header}: {len(entries)} files, incl. {', '.join(p for p in wanted if p in paths)}"
           + (f"; MISSING {', '.join(missing)}" if missing else ""),
           [f"{entry[0]}  {entry[-1]}" for entry in entries])


@check("0.5")
def nothing_pushed():
    try:
        origin = git("rev-parse", "--short", "origin/main").strip()
    except subprocess.CalledProcessError:
        report("SKIP", "0.5", "no origin/main branch to compare with")
        return
    main = git("rev-parse", "--short", "main").strip()
    ahead = int(git("rev-list", "--count", "origin/main..main"))
    behind = int(git("rev-list", "--count", "main..origin/main"))
    reflog = git("reflog", "show", "--date=iso", "-n", "3", "origin/main").splitlines()
    head = git("show", "-s", "--format=%h committed %ci: %s", "origin/main").strip()
    report(verdict(ahead > 0), "0.5",
           f"main ({main}) is {ahead} commit(s) ahead of origin/main ({origin}), {behind} behind"
           + ("" if ahead else "; so everything on main has been pushed")
           + " (local tracking ref, not fetched)",
           [f"origin/main is {head}"] + [f"origin/main reflog: {line}" for line in reflog])


SECTION_4_5 = [  # name, level, side, K-level, fitting statements, component statements (None: 4.5 gives none)
    ("transtibial", "transtibial", "left", None, 22, 11),
    ("transfemoral K2", "transfemoral", "left", "K2", 23, 14),
    ("bilateral transfemoral", "transfemoral", "bilateral", None, 24, 12),
    ("knee disarticulation", "knee_disarticulation", "left", None, 16, None),
    ("hip disarticulation", "hip_disarticulation", "left", None, 16, None),
    ("partial foot", "partial_foot", "left", None, 16, None),
    ("Syme", "syme", "left", None, 16, None),
    *[(f"upper limb: {level.replace('_', ' ')}", level, "left", None, 7, None)
      for level in ("partial_hand", "wrist_disarticulation", "transradial", "elbow_disarticulation",
                    "transhumeral", "shoulder_disarticulation")],
]

BASELINE_CODE = """
import json, sys
from reasoning.component_support import component_support
from reasoning.fitting_support import fitting_support
from shared.case_schema import ActivityProfile, Case
result = {}
for name, level, side, k_level in json.loads(sys.argv[1]):
    case = Case(amputation_level=level, side=side, activity=ActivityProfile(k_level=k_level))
    result[name] = {"components": [c.statement.id for c in component_support(case).statements],
                    "fitting": [c.statement.id for c in fitting_support(case).statements]}
print(json.dumps(result))
"""


def statement_ids_at(commit: str, cases: list) -> dict:
    """The statement ids each case got from the code as it was at `commit` (read with git archive)."""
    archive = subprocess.run(["git", "archive", "--format=tar", commit, "reasoning", "shared", "knowledge",
                              "data/sources/catalog.json"], cwd=ROOT, capture_output=True, check=True).stdout
    with tempfile.TemporaryDirectory(prefix="verify_baseline_") as tmp:
        with tarfile.open(fileobj=io.BytesIO(archive)) as tar:
            tar.extractall(tmp, filter="data")
        proc = subprocess.run([sys.executable, "-c", BASELINE_CODE, json.dumps(cases)], cwd=tmp,
                              capture_output=True, text=True, encoding="utf-8", env=CHILD_ENV)
    if proc.returncode:
        raise RuntimeError(f"baseline at {commit[:7]} failed: {proc.stderr.strip().splitlines()[-1]}")
    return json.loads(proc.stdout)


def heading_count(page_text: str, key: str) -> int | None:
    """The number in a heading such as "... ({n} statements)", as the reviewer sees it."""
    pattern = re.escape(i18n.TEXT[key]["en"]).replace(re.escape("{n}"), r"(\d+)")
    match = re.search(pattern, page_text)
    return int(match.group(1)) if match else None


@check("0.6")
def section_4_5_counts():
    # Since the RAG (2026-10-11) the page's statements come from the search and the AI, and the
    # hand-written statements are the answer key: section 4.5 counts the answer key, which
    # component_support() and fitting_support() still give for the stored case. The page headings
    # are checked against the statements the page shows.
    commit = state.get("design_commit")
    baseline = statement_ids_at(commit, [[n, lv, s, k] for n, lv, s, k, _, _ in SECTION_4_5]) if commit else None
    details, matching = [], 0
    with sandbox(no_passages) as box:
        for name, level, side, k_level, want_fitting, want_components in SECTION_4_5:
            response = box.client.post("/intake", data={"amputation_level": level, "side": side,
                                                        "k_level": k_level or ""})
            case_id = case_id_from(response)
            record = store.get(case_id)
            page = visible_text(box.client.get(f"/review/{case_id}").get_data(as_text=True))
            shown = {"fitting": [c.statement.id for c in fitting_support(record.case).statements],
                     "components": [c.statement.id for c in component_support(record.case).statements]}
            on_record = {"fitting": len(record.fitting.statements),
                         "components": sum(len(s.statements) for s in record.components.component_sections)}
            on_page = {"fitting": heading_count(page, "fitting.heading"),
                       "components": heading_count(page, "components.heading")}
            problems = []
            if len(shown["fitting"]) != want_fitting:
                problems.append(f"4.5 says {want_fitting} fitting")
            if want_components is not None and len(shown["components"]) != want_components:
                problems.append(f"4.5 says {want_components} component")
            for part in ("fitting", "components"):
                if on_page[part] != on_record[part]:
                    problems.append(f"page heading says {on_page[part]} {part}, the page shows {on_record[part]}")
                if baseline:
                    old = baseline[name][part]
                    added = [i for i in shown[part] if i not in old]
                    missing = [i for i in old if i not in shown[part]]
                    if added or missing:
                        problems.append(f"{part} vs {commit[:7]}: added {added}, missing {missing}")
            matching += not problems
            expected = f"{want_fitting} + {want_components if want_components is not None else 'not given'}"
            details.append(f"{'ok  ' if not problems else 'DIFF'} {name:34} level={level}, side={side}, "
                           f"K-level={k_level or 'not recorded'} -> {len(shown['fitting'])} fitting + "
                           f"{len(shown['components'])} component (4.5: {expected})"
                           + (f"; {'; '.join(problems)}" if problems else ""))
    same_ids = f"; statement ids identical to {commit[:7]}" if baseline else "; no baseline commit to compare ids"
    report(verdict(matching == len(SECTION_4_5)), "0.6",
           f"{matching}/{len(SECTION_4_5)} cases through the test client: answer key matches section 4.5, page "
           f"headings match the page{same_ids if matching == len(SECTION_4_5) else ''}. Inputs: side left unless "
           "bilateral, K-level only where named, every other field empty, search replaced by no passages, "
           "AI switched off", details)


# ---- Prompt 1: stabilise ----------------------------------------------------

def test_ids(suite):
    for test in suite:
        if isinstance(test, unittest.TestSuite):
            yield from test_ids(test)
        else:
            yield test.id()


TEST_GROUPS = {
    "persistence": ("tests.test_store.", "tests.test_routes.RestartTests."),
    "form refill (and language switch)": ("tests.test_routes.FormKeptTests.",),
    "translated errors": ("tests.test_routes.IntakeErrorTests.",
                          "tests.test_routes.ArabicPageTests.test_number_error_in_arabic",
                          "tests.test_routes.ArabicPageTests.test_intake_errors_in_arabic"),
}


@check("1.1")
def new_tests():
    ids = list(test_ids(unittest.defaultTestLoader.discover(str(ROOT / "tests"), top_level_dir=str(ROOT))))
    commit = state.get("design_commit")

    def is_new(test_id: str) -> bool:
        module, cls, method = test_id.rsplit(".", 2)
        old = source_at(commit, module.replace(".", "/") + ".py") if commit else None
        return old is None or f"class {cls}(" not in old or f"def {method}(" not in old

    total = state.get("test_count") or len(ids)
    details, summary, every_group_new = [], [], True
    for group, prefixes in TEST_GROUPS.items():
        members = [i for i in ids if i.startswith(prefixes)]
        new = [i for i in members if is_new(i)]
        every_group_new &= bool(new)
        summary.append(f"{group} {len(members)} ({len(new)} new)")
        details.append(f"{group}:")
        details += [f"  {'new ' if i in new else 'old '} {i.removeprefix('tests.')}" for i in members]
    since = f" since {commit[:7]}" if commit else ""
    report(verdict(total > BASELINE_TEST_COUNT and every_group_new), "1.1",
           f"{total} tests (> {BASELINE_TEST_COUNT}); {'; '.join(summary)}{since}", details)


def restart_probe(cases_dir: str, log_path: str, case_id: str) -> int:
    """Run in a new process by check 1.2: a fresh app reading the same case folder."""
    store.folder, decision_log.REVIEW_LOG_PATH = Path(cases_dir), Path(log_path)
    app = create_app()
    app.testing = True
    response = app.test_client().get(f"/review/{case_id}")
    record = store.get(case_id)
    print(json.dumps({"pid": os.getpid(), "status": response.status_code,
                      "page_sha256": hashlib.sha256(response.data).hexdigest(),
                      "case": record.case.to_dict() if record else None}))
    return 0


@check("1.2")
def persistence_after_restart():
    with sandbox() as box:
        case_id = case_id_from(box.client.post("/intake", data=FORM_WITH_GAPS))
        before = box.client.get(f"/review/{case_id}")
        case = store.get(case_id).case.to_dict()
        path = box.cases / f"{case_id}.json"
        file_saved = path.is_file()
        proc = subprocess.run([sys.executable, str(Path(__file__).resolve()), "--restart-probe", str(box.cases),
                               str(box.log), case_id], cwd=ROOT, capture_output=True, text=True,
                              encoding="utf-8", env=CHILD_ENV)
        if proc.returncode:
            report("FAIL", "1.2", "the restarted app failed", proc.stderr.strip().splitlines()[-6:])
            return
        after = json.loads(proc.stdout.strip().splitlines()[-1])
    same_page = after["page_sha256"] == hashlib.sha256(before.data).hexdigest()
    passed = (file_saved and after["status"] == 200 and after["case"] == case and same_page
              and after["pid"] != os.getpid())
    report(verdict(passed), "1.2",
           f"case saved as <temp>/cases/{path.name} ({'yes' if file_saved else 'NO'}); a new process (pid {after['pid']}, fresh app and store) "
           f"answered GET /review/{case_id} with {after['status']}; same case "
           f"({'yes' if after['case'] == case else 'NO'}, {len(case)} fields); page identical byte for byte "
           f"({'yes' if same_page else 'NO'})")


@check("1.3")
def no_identifiers_in_case_file():
    with sandbox() as box:
        form_page = box.client.get("/intake").get_data(as_text=True)
        case_id = case_id_from(box.client.post("/intake", data=FORM_WITH_GAPS))
        data = json.loads((box.cases / f"{case_id}.json").read_text(encoding="utf-8"))
    found = identifier_findings(data)
    inputs = sorted(set(re.findall(r'name="([^"]+)"', form_page)))
    bad_inputs = [name for name in inputs if IDENTIFIER_KEY.search(name)]
    report(verdict(not found and not bad_inputs), "1.3",
           f"saved case file: {count_keys(data)} keys and their values scanned, {len(found)} identifier-like "
           f"(name, birth date, address, record/MRN, phone, email; English and Arabic labels); intake form: "
           f"{len(bad_inputs)} of {len(inputs)} input names identifier-like",
           [f"top-level keys: {', '.join(data)}", f"case fields: {', '.join(data['case'])}",
            f"form inputs: {', '.join(inputs)}"] + found + bad_inputs)


@check("1.4")
def cases_ignored_by_git():
    lines = (ROOT / ".gitignore").read_text(encoding="utf-8-sig").splitlines()
    number = next((n for n, line in enumerate(lines, 1) if line.strip() in ("data/cases/", "data/cases", "/data/cases/")),
                  None)
    proc = subprocess.run(["git", "check-ignore", "-v", "data/cases/verify-probe.json"], cwd=ROOT,
                          capture_output=True, text=True, encoding="utf-8")
    report(verdict(number is not None and proc.returncode == 0), "1.4",
           (f".gitignore line {number}: {lines[number - 1]}" if number else ".gitignore has no data/cases/ line")
           + f"; git check-ignore: {proc.stdout.strip() or 'not ignored'}")


@check("1.5")
def form_kept_after_an_error():
    details, passed = [], True
    with sandbox() as box:
        for field, bad in (("age_years", "abc"), ("body_weight_kg", "heavy")):
            response = box.client.post("/intake", data=FULL_FORM | {field: bad})
            page = response.get_data(as_text=True)
            others = {name: value for name, value in FULL_FORM.items() if name != field}
            lost = [name for name, value in others.items() if not value_kept(page, name, value)]
            bad_kept = value_kept(page, field, bad)
            ok = response.status_code == 400 and not lost and bad_kept
            passed &= ok
            details.append(f"{field}={bad!r}: {response.status_code}, {len(others) - len(lost)}/{len(others)} other "
                           f"values back in the form, the bad value too ({'yes' if bad_kept else 'NO'})"
                           + (f"; LOST: {', '.join(lost)}" if lost else ""))
        saved = list(box.cases.glob("*.json")) if box.cases.exists() else []
    passed &= not saved
    report(verdict(passed), "1.5", f"invalid age and invalid body weight: 400, every other value kept; "
                                   f"{len(saved)} cases saved" if passed else "form not kept after an error", details)


PYTHON_WORDING = ("invalid literal", "could not convert", "ValueError", "Traceback", "is not a valid",
                  "must be 0 or greater", "must be greater than 0")
ARABIC = re.compile(r"[؀-ۿ]")


@check("1.6")
def errors_translated():
    details, passed = [], True
    with sandbox() as box:
        for lang in ("ar", "en"):
            box.client.set_cookie("lang", lang)
            for field, bad in (("age_years", "abc"), ("body_weight_kg", "heavy")):
                response = box.client.post("/intake", data=FULL_FORM | {field: bad})
                page = response.get_data(as_text=True)
                match = re.search(r'(?s)<div class="error">(.*?)</div>', page)
                message = " ".join(visible_text(match.group(1)).split()) if match else ""
                python = [w for w in PYTHON_WORDING if w in page]
                if lang == "ar":
                    ok = bool(ARABIC.search(message)) and not re.search(r"[A-Za-z]", message)
                else:
                    ok = bool(message) and not ARABIC.search(message)
                ok &= response.status_code == 400 and not python
                passed &= ok
                details.append(f"[{lang}] {field}={bad!r}: {response.status_code}  {message}"
                               + (f"; PYTHON WORDING: {python}" if python else "")
                               + ("" if ok else "  <- FAIL"))
    report(verdict(passed), "1.6", "the same invalid values with the Arabic cookie: an Arabic message, no Latin "
                                   f"letters in it; no Python wording ({', '.join(PYTHON_WORDING[:4])}, ...) on "
                                   "any page (English checked too)", details)


@check("1.7")
def language_switch_keeps_input():
    typed = {"amputation_level": "transfemoral", "pain": "ألم شبحي", "comorbidities": "Diabetes",
             "device_1_description": "socket", "age_years": "abc"}  # an invalid age: a switch checks nothing
    with sandbox() as box:
        form = box.client.get("/intake").get_data(as_text=True)
        button = re.search(r'<button[^>]*name="switch_language"[^>]*>', form)
        to_arabic = box.client.post("/intake", data={"switch_language": "ar", **typed})
        page = to_arabic.get_data(as_text=True)
        kept = [name for name, value in typed.items() if value_kept(page, name, value)]
        cookie = to_arabic.headers.get("Set-Cookie", "")
        back = box.client.post("/intake", data={"switch_language": "en", "pain": typed["pain"]})
        back_page = back.get_data(as_text=True)
        saved = len(list(box.cases.glob("*.json"))) if box.cases.exists() else 0
        in_memory = len(store.all())
    passed = (to_arabic.status_code == 200 and '<html lang="ar" dir="rtl">' in page and len(kept) == len(typed)
              and "lang=ar" in cookie and 'class="error"' not in page and saved == 0 and in_memory == 0
              and '<html lang="en" dir="ltr">' in back_page and value_kept(back_page, "pain", typed["pain"])
              and button is not None and "formnovalidate" in button.group(0))
    report(verdict(passed), "1.7",
           f"server-side: POST /intake with switch_language=ar -> {to_arabic.status_code}, Arabic right-to-left "
           f"form, {len(kept)}/{len(typed)} typed values kept (an invalid age too), cookie lang=ar, no error, "
           f"{saved} cases saved; switching back to English kept them",
           ["How: the language control on the intake page is a submit button of the intake form",
            f"  ({button.group(0) if button else 'NOT FOUND'}),",
            "  so clicking it posts whatever has been typed. intake/routes.py submit_form() sees switch_language,",
            "  sets g.lang, draws the same form from request.form in the other language, sets the cookie and",
            "  neither checks nor saves anything. A hidden default submit button placed first keeps Enter",
            "  submitting the case. No JavaScript; the browser's part is checked by hand (1.7b)."])
    report("MANUAL", "1.7b", "clicking the language button in a real browser keeps unsent input: "
                             "docs/manual_checks_prompts_0_2.md, check 3")


@check("1.8")
def log_split():
    if not REAL_TEST_LOG.is_file():
        report("FAIL", "1.8", f"{rel(REAL_TEST_LOG)} is missing")
        return
    real_before = {p: sha256(p) if p.is_file() else "absent" for p in (REAL_TEST_LOG, REAL_TRIAL_LOG)}
    with tempfile.TemporaryDirectory(prefix="verify_logs_") as tmp:
        tmp = Path(tmp)
        test_copy, trial_copy = tmp / REAL_TEST_LOG.name, tmp / REAL_TRIAL_LOG.name
        shutil.copy(REAL_TEST_LOG, test_copy)
        if REAL_TRIAL_LOG.is_file():
            shutil.copy(REAL_TRIAL_LOG, trial_copy)
        else:
            trial_copy.touch()
        lines = non_empty_lines(test_copy)
        parsed, versions = 0, Counter()
        for line in lines:
            try:
                versions[json.loads(line).get("log_version", 1)] += 1
                parsed += 1
            except json.JSONDecodeError:
                pass
        trial_before, test_sha = len(non_empty_lines(trial_copy)), sha256(test_copy)
        with sandbox(log=trial_copy) as box:
            case_id = case_id_from(box.client.post("/intake", data=FORM_WITH_GAPS))
            decision = box.client.post(f"/review/{case_id}/decision", follow_redirects=True,
                                       data={"decision": "approve", f"gap:{VOLUME}": "needed"})
        trial_after, test_after = len(non_empty_lines(trial_copy)), len(non_empty_lines(test_copy))
        test_unchanged = sha256(test_copy) == test_sha
    real_unchanged = real_before == {p: sha256(p) if p.is_file() else "absent" for p in real_before}
    passed = (len(lines) == 26 and parsed == 26 and trial_before == 0 and decision.status_code == 200
              and trial_after == 1 and test_after == 26 and test_unchanged and real_unchanged)
    report(verdict(passed), "1.8",
           f"copy of {REAL_TEST_LOG.name}: {len(lines)} lines, {parsed} parse as JSON "
           f"({', '.join(f'v{v}: {n}' for v, n in sorted(versions.items()))}); copy of {REAL_TRIAL_LOG.name}: "
           f"{trial_before} lines ({REAL_TRIAL_LOG.stat().st_size if REAL_TRIAL_LOG.is_file() else 'no'} bytes). "
           f"After 1 decision: review log {trial_after} line, test log {test_after} lines "
           f"({'unchanged' if test_unchanged else 'CHANGED'}); real files {'unchanged' if real_unchanged else 'CHANGED'}")


# ---- Prompt 2: trial tooling ------------------------------------------------

@check("2.1")
def term_sheet():
    if not TERM_SHEET.is_file():
        report("FAIL", "2.1", f"{rel(TERM_SHEET)} is missing")
        return
    bom = TERM_SHEET.read_bytes().startswith(b"\xef\xbb\xbf")
    with TERM_SHEET.open(encoding="utf-8-sig", newline="") as f:
        header, *rows = list(csv.reader(f))
    expected = {key: (texts["en"], texts["ar"]) for key, texts in i18n.TEXT.items()}
    parts = {"TEXT": len(expected)}
    fields = {f"field_label:{path}": (FIELDS_BY_PATH[path].label, arabic)
              for path, arabic in i18n.FIELD_LABELS["ar"].items()}
    choices = {f"choice:{enum}.{value}": (value.replace("_", " "), arabic)
               for enum, values in i18n.VALUE_LABELS["ar"].items() for value, arabic in values.items()}
    parts["field labels"], parts["choices"] = len(fields), len(choices)
    expected |= fields | choices
    keys = [row[0] for row in rows]
    duplicates = [key for key, n in Counter(keys).items() if n > 1]
    columns_ok = tuple(header) == arabic_terms.COLUMNS
    filled = [row[0] for row in rows if len(row) != 6 or row[4] or row[5]]
    stale = [row[0] for row in rows if row[0] in expected and tuple(row[1:3]) != expected[row[0]]]
    missing, extra = sorted(set(expected) - set(keys)), sorted(set(keys) - set(expected))
    not_found = [row[0] for row in rows if len(row) > 3 and row[3] == "(not found)"]
    passed = columns_ok and bom and not (duplicates or filled or stale or missing or extra)
    report(verdict(passed), "2.1",
           f"{rel(TERM_SHEET)}: {len(rows)} rows, shared/i18n.py has {len(expected)} text keys "
           f"({' + '.join(f'{n} {p}' for p, n in parts.items())}); same keys ({len(missing)} missing, "
           f"{len(extra)} extra, {len(duplicates)} duplicated); columns "
           f"{'as expected' if columns_ok else 'WRONG: ' + ' | '.join(header)}; last two empty in "
           f"{len(rows) - len(filled)}/{len(rows)}; English and Arabic as in i18n.py in "
           f"{len(rows) - len(stale)}/{len(rows)}; UTF-8 BOM: {'yes' if bom else 'NO (Excel shows Arabic wrongly)'}",
           [f"columns: {' | '.join(header)}"]
           + [f"MISSING {k}" for k in missing[:10]] + [f"EXTRA {k}" for k in extra[:10]]
           + [f"FILLED {k}" for k in filled[:10]] + [f"STALE {k}" for k in stale[:10]]
           + ([f"'where it appears' not found for {len(not_found)} keys: {not_found[:5]}"] if not_found else []))


def write_sheet(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=arabic_terms.COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


@check("2.2")
def term_sheet_round_trip():
    key, corrected = "review.approve", "موافقة"
    with tempfile.TemporaryDirectory(prefix="verify_terms_") as tmp:
        tmp = Path(tmp)
        original, edited, untouched = tmp / "i18n_original.py", tmp / "i18n_edited.py", tmp / "i18n_untouched.py"
        for copy in (original, edited, untouched):
            shutil.copy(I18N_FILE, copy)
        sheet, filled_sheet = tmp / "arabic_terms.csv", tmp / "arabic_terms_filled.csv"
        shutil.copy(TERM_SHEET, sheet)
        rows = arabic_terms.read_sheet(sheet)
        for row in rows:
            if row["key"] == key:
                old_arabic = row["Arabic"]
                row["corrected Arabic"] = corrected
        write_sheet(filled_sheet, rows)

        out = io.StringIO()
        changed = arabic_terms.apply(filled_sheet, edited, confirm=lambda question: True, out=out)
        before = i18n_texts(load_module(original, "i18n_verify_original"))
        after = i18n_texts(load_module(edited, "i18n_verify_edited"))
        differing = sorted(k for k in before.keys() | after.keys() if before.get(k) != after.get(k))
        diff = [line for line in difflib.unified_diff(original.read_text(encoding="utf-8").splitlines(),
                                                      edited.read_text(encoding="utf-8").splitlines(), lineterm="")
                if line.startswith(("+", "-")) and not line.startswith(("+++", "---"))]

        untouched_out = io.StringIO()
        untouched_changed = arabic_terms.apply(sheet, untouched, confirm=lambda question: True, out=untouched_out)
        untouched_same = untouched.read_bytes() == original.read_bytes()
    one_key = differing == [f"TEXT[{key}][ar]"] and after.get(differing[0] if differing else "") == corrected
    passed = changed == 1 and one_key and untouched_changed is None and untouched_same
    report(verdict(passed), "2.2",
           f"one 'corrected Arabic' cell ({key}: {old_arabic} -> {corrected}) applied to a copy of i18n.py: "
           f"apply returned {changed}, {len(differing)} of {len(before)} texts changed "
           f"({', '.join(differing) or 'none'}), file diff -{sum(l[0] == '-' for l in diff)} "
           f"+{sum(l[0] == '+' for l in diff)} lines. Untouched sheet: apply returned {untouched_changed}, "
           f"\"{untouched_out.getvalue().strip()}\", file byte-identical: {'yes' if untouched_same else 'NO'}",
           diff)


@check("2.3")
def trial_cases():
    paths = sorted(TRIAL_CASES.glob("*.json"))
    cases, problems, findings = [], [], []
    case_fields = set(Case.__dataclass_fields__)
    for path in paths:
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            case = Case.from_dict(data)
        except Exception as e:
            problems.append(f"{path.name}: does not load: {e}")
            continue
        if case.case_id != path.stem:
            problems.append(f"{path.name}: case_id {case.case_id!r} is not the file name")
        unknown = set(data) - case_fields
        if unknown:
            problems.append(f"{path.name}: keys that are not Case fields: {sorted(unknown)}")
        findings += [f"{path.name}: {f}" for f in identifier_findings(data)]
        cases.append(case)
    lower = [c for c in cases if c.is_lower_limb]
    upper = [c for c in cases if not c.is_lower_limb]
    sides = {limb: Counter(c.side.value for c in group) for limb, group in (("lower", lower), ("upper", upper))}
    k_levels = Counter(c.activity.k_level.value if c.activity.k_level else "not recorded" for c in lower)
    unrecorded = {c.case_id: len(c.unrecorded_fields()) for c in cases}
    partly = [i for i, n in unrecorded.items() if n > 0]
    gaps, statements = {}, {}
    with patch("intake.routes.retrieve_relevant_chunks", side_effect=no_passages):
        for case in cases:
            try:
                record = analyse_case(case)
                gaps[case.case_id], statements[case.case_id] = len(record.gaps), len(record.shown_statements())
            except Exception as e:
                problems.append(f"{case.case_id}: analysis raised {type(e).__name__}: {e}")
    levels = {c.amputation_level for c in cases}
    spread_ok = (len(levels) == 12 and all(set(s) >= {"left", "right", "bilateral"} for s in sides.values())
                 and set(k_levels) >= {"K0", "K1", "K2", "K3", "K4", "unknown"})
    passed = 10 <= len(paths) <= 15 and not problems and not findings and len(gaps) == len(paths) and spread_ok
    report(verdict(passed), "2.3",
           f"{len(paths)} trial cases, all load with Case.from_dict and run through the analysis "
           f"({len(gaps)}/{len(paths)}; search replaced by no passages), {len(findings)} identifier-like keys or "
           f"values; {len(levels)}/12 amputation levels",
           [f"lower limb {len(lower)}: " + ", ".join(f"{s} {n}" for s, n in sorted(sides['lower'].items()))
            + "; K-levels " + ", ".join(f"{k} {n}" for k, n in sorted(k_levels.items())),
            f"upper limb {len(upper)}: " + ", ".join(f"{s} {n}" for s, n in sorted(sides['upper'].items())),
            f"partly filled (at least one field not recorded): {len(partly)}/{len(cases)}; fields not recorded "
            f"per case: {min(unrecorded.values())}-{max(unrecorded.values())} "
            f"({', '.join(f'{i[-2:]}:{n}' for i, n in unrecorded.items())})",
            f"gaps per case {min(gaps.values(), default=0)}-{max(gaps.values(), default=0)}, statements per case "
            f"{min(statements.values(), default=0)}-{max(statements.values(), default=0)}"]
           + problems + findings)


@check("2.3m")
def trial_cases_real_search():
    if not state.get("with_model"):
        report("SKIP", "2.3m", "the real search over the trial cases was not run: it loads the bge-m3 model "
                               "(rerun with --with-model)")
        return
    needed = [config.VECTOR_STORE_DIR / name for name in ("vectors.npy", "chunks.json", "info.json")]
    if not all(p.is_file() for p in needed):
        report("SKIP", "2.3m", f"no search index in {rel(config.VECTOR_STORE_DIR)} (python -m knowledge.ingest)")
        return
    started, rows, warnings = time.perf_counter(), [], set()
    for path in sorted(TRIAL_CASES.glob("*.json")):
        record = analyse_case(load_trial_cases.read_case(path))
        cited = sum(1 for gap in record.gaps if gap.evidence is not None)
        rows.append((path.stem, len(record.gaps), cited))
        if record.knowledge_warning:
            warnings.add(record.knowledge_warning)
    report(verdict(not warnings), "2.3m",
           f"{len(rows)} trial cases analysed with the real search in {time.perf_counter() - started:.0f} s: "
           f"{sum(r[1] for r in rows)} gaps, {sum(r[2] for r in rows)} cite a source; {len(warnings)} warnings",
           [f"{case_id}: {n} gaps, {cited} with a source" for case_id, n, cited in rows] + sorted(warnings))


@check("2.4")
def load_command():
    paths = sorted(TRIAL_CASES.glob("*.json"))
    with sandbox(no_passages) as box:
        _, output = run_capturing_stdout(load_trial_cases.main, [])
        saved = sorted(p.stem for p in box.cases.glob("*.json"))
        store._records.clear()  # the app starts after the load
        app = create_app()
        app.testing = True
        client = app.test_client()
        pages = {stem: client.get(f"/review/{stem}") for stem in saved}
        temp_folder = str(box.cases) in output
    opened = [stem for stem, page in pages.items() if page.status_code == 200 and stem in page.get_data(as_text=True)]
    passed = saved == [p.stem for p in paths] and len(opened) == len(paths) and temp_folder
    report(verdict(passed), "2.4",
           f"the load command (intake.load_trial_cases.main) saved {len(saved)}/{len(paths)} cases to a temporary "
           f"folder ({'it says so' if temp_folder else 'NOT the temporary folder'}); after a simulated app start, "
           f"{len(opened)}/{len(paths)} review pages return 200 with their case id",
           [line for line in output.splitlines() if line.startswith("trial-")])


FAKE_LOG_CASES = [  # case id, level, side, a source passage shown for the volume gap?
    ("verify-a", "transtibial", "left", True),
    ("verify-b", "transfemoral", "left", False),
    ("verify-c", "transradial", "right", False),
]
EDIT_NOTE = "يرجى تسجيل طول الطرف المتبقي قبل التركيب"  # a fake note, in Arabic
FAKE_DECISIONS = [  # case id, decision, note, page language, gap marks, statement marks
    ("verify-a", "approve", None, "en", {VOLUME: "not_needed", PAIN: "not_needed"},
     {"cms_elevated_vacuum": "not_relevant"}),
    ("verify-b", "edit", EDIT_NOTE, "ar", {WOUND: "needed"}, {}),
    ("verify-c", "reject", None, "en", {}, {}),
]
# What the report must say about the fake log above, written out by hand.
EXPECTED_GAPS_PER_CASE = {"verify-a": 17, "verify-b": 17, "verify-c": 15}  # every gap field left empty
EXPECTED_STATEMENTS_PER_CASE = {"verify-a": 22 + 11, "verify-b": 23 + 12, "verify-c": 7 + 2}  # fitting + component
EXPECTED = {
    "decisions logged": 3, "cases": 3, "cases with more than one decision": 0,
    "approve": 1, "edit": 1, "reject": 1,
    "gaps needed": 1, "gaps not needed": 2, "gaps not marked": 17 + 17 + 15 - 3,
    "statements relevant": 0, "statements not relevant": 1, "statements not marked": 33 + 35 + 9 - 1,
}
EXPECTED_GAP_ROWS = {  # (field, source passage shown) -> (needed, not needed, not marked)
    (VOLUME, "yes"): (0, 1, 0), (VOLUME, "no"): (0, 0, 2), (WOUND, "no"): (1, 0, 2), (PAIN, "no"): (0, 1, 2),
}
EXPECTED_STATEMENT_ROWS = {"cms_elevated_vacuum": (0, 1, 1)}  # shown for verify-a and verify-b
EXPECTED_UNSOURCED = [(WOUND, "Residual limb wound status", 1, "verify-b")]
EXPECTED_NOTES = [("verify-b", "ar", EDIT_NOTE)]


def write_fake_log(path: Path) -> dict[str, CaseRecord]:
    """The fake decisions above, written by the app's own logger."""
    records = {}
    for case_id, level, side, sourced in FAKE_LOG_CASES:
        case = Case(amputation_level=level, side=side, case_id=case_id)
        chunks = {VOLUME: [FAKE_PASSAGE]} if sourced else {}
        records[case_id] = CaseRecord(case=case, retrieved_chunks=chunks, gaps=analyze_gaps(case, chunks),
                                      components=component_support(case), fitting=fitting_support(case))
    for case_id, decision, note, lang, gap_marks, statement_marks in FAKE_DECISIONS:
        decision_log.record_decision(records[case_id], decision, note=note, gap_judgements=gap_marks, path=path,
                                     ui_language=lang, statement_judgements=statement_marks)
    return records


def tally(records: dict[str, CaseRecord]) -> tuple[dict, dict]:
    """The rows the report should have, counted straight from the fake decisions (not by the report)."""
    gap_rows, statement_rows = defaultdict(lambda: [0, 0, 0]), defaultdict(lambda: [0, 0, 0])
    for case_id, _, _, _, gap_marks, statement_marks in FAKE_DECISIONS:
        record = records[case_id]
        for gap in record.gaps:
            column = {"needed": 0, "not_needed": 1, None: 2}[gap_marks.get(gap.field)]
            gap_rows[(gap.field, "yes" if gap.evidence else "no")][column] += 1
        for cited in record.shown_statements():
            column = {"relevant": 0, "not_relevant": 1, None: 2}[statement_marks.get(cited.statement.id)]
            statement_rows[cited.statement.id][column] += 1
    return {k: tuple(v) for k, v in gap_rows.items()}, {k: tuple(v) for k, v in statement_rows.items()}


def run_report_command(log: Path, out: Path) -> subprocess.CompletedProcess:
    """python -m review.trial_report on a given log, writing its CSV to `out`."""
    return subprocess.run([sys.executable, "-m", "review.trial_report", "--log", str(log), "--out", str(out)],
                          cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=CHILD_ENV)


def numbers_in(value) -> int:
    if isinstance(value, bool):
        return 0
    if isinstance(value, int):
        return 1
    if isinstance(value, str):
        return 1 if value.isdigit() else 0
    if isinstance(value, dict):
        return sum(numbers_in(v) for v in value.values())
    if isinstance(value, (list, tuple)):
        return sum(numbers_in(v) for v in value)
    return 0


@check("2.5")
def report_on_known_log():
    compared, differences = 0, []

    def same(what, got, want):
        nonlocal compared
        compared += numbers_in(want)
        if got != want:
            differences.append(f"{what}: report {got!r}, expected {want!r}")

    with tempfile.TemporaryDirectory(prefix="verify_report_") as tmp:
        tmp = Path(tmp)
        log, out = tmp / "review_log.jsonl", tmp / "report.csv"
        records = write_fake_log(log)
        same("gaps per case (input)", {i: len(r.gaps) for i, r in records.items()}, EXPECTED_GAPS_PER_CASE)
        same("statements per case (input)", {i: len(r.shown_statements()) for i, r in records.items()},
             EXPECTED_STATEMENTS_PER_CASE)
        want_gaps, want_statements = tally(records)

        # The report object.
        r = trial_report.build_report(trial_report.read_log(log), log)
        gap_rows = {(f, src): (n, nn, u) for f, _, src, n, nn, u in r.gap_rows()}
        statement_rows = {s: (rv, nr, u) for s, _, _, _, rv, nr, u in r.statement_rows()}
        same("decisions", r.decisions, EXPECTED["decisions logged"])
        same("cases", len(r.cases), EXPECTED["cases"])
        same("cases decided more than once", sum(1 for n in r.cases.values() if n > 1),
             EXPECTED["cases with more than one decision"])
        for d in ("approve", "edit", "reject"):
            same(f"decision {d}", r.decision_counts[d], EXPECTED[d])
        for column, name in enumerate(("gaps needed", "gaps not needed", "gaps not marked")):
            same(name, sum(row[column] for row in gap_rows.values()), EXPECTED[name])
        for column, name in enumerate(("statements relevant", "statements not relevant", "statements not marked")):
            same(name, sum(row[column] for row in statement_rows.values()), EXPECTED[name])
        for key, want in EXPECTED_GAP_ROWS.items():
            same(f"gap row {key}", gap_rows.get(key), want)
        for key, want in EXPECTED_STATEMENT_ROWS.items():
            same(f"statement row {key}", statement_rows.get(key), want)
        same("every gap row", gap_rows, want_gaps)
        same("every statement row", statement_rows, want_statements)
        same("no-source list", r.unsourced_rows(), EXPECTED_UNSOURCED)
        same("edit notes", [(c, lang, note) for _, c, lang, note in r.edit_notes], EXPECTED_NOTES)

        # The command: its CSV and its printed summary.
        printed = run_report_command(log, out).stdout
        sections = csv_sections(out)
        summary = {row[0]: row[1] for row in sections["Trial report (counts only)"][1:]}
        for name in ("decisions logged", "cases", "cases with more than one decision"):
            same(f"CSV {name}", summary.get(name), str(EXPECTED[name]))
        same("CSV decisions", sections["Decisions"][1:], [[d, str(EXPECTED[d])] for d in ("approve", "edit", "reject")])
        same("CSV gap rows", {(row[0], row[2]): tuple(map(int, row[3:6])) for row in sections["Gap fields"][1:]},
             want_gaps)
        same("CSV statement rows", {row[0]: tuple(map(int, row[4:7])) for row in sections["Statements"][1:]},
             want_statements)
        same("CSV no-source list", sections["Gaps shown without a source and marked Needed"][1:],
             [[f, label, str(n), ids] for f, label, n, ids in EXPECTED_UNSOURCED])
        same("CSV edit notes", [row[1:] for row in sections["Edit notes"][1:]], [list(n) for n in EXPECTED_NOTES])
        for text in ("3 decisions on 3 cases (0 cases decided more than once)",
                     "Decisions: approve 1, edit 1, reject 1",
                     f"Statements: {len(want_statements)} shown, 1 marked at least once", f"[ar]  {EDIT_NOTE}"):
            if text not in printed:
                differences.append(f"printed summary lacks {text!r}")
        if not re.search(rf"{re.escape(WOUND)}\s+1\s+verify-b", printed):
            differences.append("printed summary lacks the no-source line for residual_limb.wound_status")
    report(verdict(not differences), "2.5",
           f"fake log of {EXPECTED['decisions logged']} decisions on 3 cases (written by the app's logger); "
           f"{compared} expected numbers compared with the report object, its CSV and its printed summary: "
           f"{len(differences)} differ; no-source list {EXPECTED_UNSOURCED[0][0]} x1 (verify-b); Arabic edit "
           f"note kept word for word", differences[:10])


@check("2.6")
def report_on_empty_or_missing_log():
    details, passed = [], True
    with tempfile.TemporaryDirectory(prefix="verify_report_") as tmp:
        tmp = Path(tmp)
        empty = tmp / "empty.jsonl"
        empty.write_text("", encoding="utf-8")
        for label, log in (("empty log", empty), ("missing log", tmp / "missing.jsonl")):
            out = tmp / f"{log.stem}.csv"
            proc = run_report_command(log, out)
            sections = csv_sections(out) if out.is_file() else {}
            decisions = sections.get("Decisions", [])[1:]
            logged = {row[0]: row[1] for row in sections.get("Trial report (counts only)", [])[1:]}
            traceback_shown = "Traceback" in proc.stdout + proc.stderr
            ok = (proc.returncode == 0 and not traceback_shown and "No decisions logged yet." in proc.stdout
                  and decisions == [["approve", "0"], ["edit", "0"], ["reject", "0"]]
                  and logged.get("decisions logged") == "0")
            passed &= ok
            details.append(f"{label}: exit {proc.returncode}, prints "
                           f"{'No decisions logged yet.' if 'No decisions logged yet.' in proc.stdout else 'NO message'}"
                           f", CSV decisions {decisions}, traceback: {'YES' if traceback_shown else 'no'}")
    report(verdict(passed), "2.6", "python -m review.trial_report on an empty and on a missing log: a clear "
                                   "message, zero counts, no traceback", details)


# The report command in a new process that records every file it opens (an audit hook).
REPORT_OPEN_PROBE = """
import json, os, sys
opened = []
def record(event, args):
    if event == "open" and args[0] is not None and not isinstance(args[0], int):
        opened.append(os.path.normcase(os.path.abspath(os.fsdecode(args[0]))))
sys.addaudithook(record)
from review import trial_report
trial_report.main(sys.argv[1:])
print("OPENED " + json.dumps(opened))
"""


@check("2.7")
def report_reads_only_its_log():
    source = Path(trial_report.__file__).read_text(encoding="utf-8")
    with tempfile.TemporaryDirectory(prefix="verify_report_") as tmp:
        tmp = Path(tmp)
        log, out = tmp / "review_log.jsonl", tmp / "report.csv"
        write_fake_log(log)
        proc = subprocess.run([sys.executable, "-c", REPORT_OPEN_PROBE, "--log", str(log), "--out", str(out)],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8", env=CHILD_ENV)
        if proc.returncode:
            report("FAIL", "2.7", "the report command failed", proc.stderr.strip().splitlines()[-6:])
            return
        opened = json.loads(proc.stdout.strip().splitlines()[-1].removeprefix("OPENED "))
        logs_opened = sorted({p for p in opened if os.path.basename(p).startswith("review_log")})
        only_given = logs_opened == [_norm(log)]
    test_log_opened = _norm(REAL_TEST_LOG) in opened
    names_test_log = "review_log.test" in source or "test.jsonl" in source
    default_ok = REPORT_DEFAULT_LOG == config.REVIEW_LOG_PATH and REPORT_DEFAULT_LOG.name == "review_log.jsonl"
    report(verdict(only_given and not test_log_opened and not names_test_log and default_ok), "2.7",
           f"the report command on a temporary log opened {len(opened)} files, {len(logs_opened)} named review_log* "
           f"({'only the log given' if only_given else logs_opened}); {REAL_TEST_LOG.name} opened: "
           f"{'YES' if test_log_opened else 'no'}; review/trial_report.py names a test log: "
           f"{'YES' if names_test_log else 'no'}; default --log: {rel(REPORT_DEFAULT_LOG)}")


def safety(before: dict[str, str]) -> None:
    after = fingerprint()
    changed = [p for p in sorted(before.keys() | after.keys()) if before.get(p) != after.get(p)]
    absent = [p for p, v in before.items() if v == "absent"]
    report(verdict(not changed and not write_attempts), "S.1",
           f"protected paths: {len(before)} fingerprinted, {len(changed)} changed "
           f"({', '.join(absent)} absent before and after); {len(write_attempts)} write attempts refused",
           [f"CHANGED {p}" for p in changed] + write_attempts)


# ---- The practice server for the manual checks -------------------------------

def practice_server(folder: str | None, port: int) -> int:
    """The app on temporary data, with the trial cases loaded: nothing in data/ is touched."""
    folder = Path(folder) if folder else Path(tempfile.mkdtemp(prefix="prosthetic_lab_practice_"))
    store.folder = folder / "cases"
    decision_log.REVIEW_LOG_PATH = folder / "review_log.jsonl"
    if not store.folder.exists():
        print(f"Loading the {len(list(TRIAL_CASES.glob('*.json')))} trial cases with the real search "
              "(the model takes 10-30 s to load) ...")
        load_trial_cases.load(sorted(TRIAL_CASES.glob("*.json")))
    print(f"Practice data (cases and review log): {folder}")
    print(f"Open http://127.0.0.1:{port}/intake or http://127.0.0.1:{port}/review/trial-01")
    print(f"Report afterwards: python -m review.trial_report --log \"{decision_log.REVIEW_LOG_PATH}\" "
          f"--out \"{folder / 'report.csv'}\"")
    print("Stop with Ctrl+C. The folder stays until you delete it; nothing in data/ is changed.")
    create_app().run(port=port)
    return 0


def main(argv=None) -> int:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python scripts/verify_prompts_0_2.py",
                                     description=__doc__.splitlines()[0])
    parser.add_argument("--with-model", action="store_true", help="also run the real search over the trial cases")
    parser.add_argument("--practice-server", action="store_true", help="run the app on temporary data")
    parser.add_argument("--practice-dir", help="practice data folder to use (default: a new temporary one)")
    parser.add_argument("--port", type=int, default=5001)
    parser.add_argument("--restart-probe", nargs=3, help=argparse.SUPPRESS)  # used by check 1.2
    args = parser.parse_args(argv)
    try:
        if args.restart_probe:
            return restart_probe(*args.restart_probe)
        if args.practice_server:
            return practice_server(args.practice_dir, args.port)
        state["with_model"] = args.with_model
        before = fingerprint()
        print(f"Verifying Prompts 0-2 in {ROOT}\n")
        for check_id, function in CHECKS:
            try:
                function()
            except Exception as e:
                report("FAIL", check_id, f"the check itself raised {type(e).__name__}: {e}",
                       traceback.format_exc().strip().splitlines()[-6:])
            finally:
                store._records.clear()
        safety(before)
    finally:
        shutil.rmtree(_SCRATCH, ignore_errors=True)
    counts = Counter(status for _, status, _ in results)
    print("\n" + ", ".join(f"{status} {counts[status]}" for status in ("PASS", "FAIL", "SKIP", "MANUAL")))
    failed = [check_id for check_id, status, _ in results if status == "FAIL"]
    if failed:
        print("Failed: " + ", ".join(failed))
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())

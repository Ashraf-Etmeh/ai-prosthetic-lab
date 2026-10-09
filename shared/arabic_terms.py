"""The Arabic term sheet: every interface text, for an Arabic-reading prosthetist to check.

  python -m shared.arabic_terms export          writes data/trial/arabic_terms.csv
  python -m shared.arabic_terms apply SHEET     puts the sheet's corrections into shared/i18n.py

The sheet has one row per text in shared/i18n.py: the page texts (TEXT), the
gap field names (FIELD_LABELS) and the drop-down choices (VALUE_LABELS).
Columns: key, English, Arabic, where it appears (the templates and modules
that use it), corrected Arabic, comment. The reviewer fills in only the last
two, and only where needed.

`apply` changes only the rows with a corrected Arabic text. It edits just
those strings in shared/i18n.py (the rest of the file, comments included,
stays as it is), shows the difference, and writes only after a yes. It
refuses the whole sheet if any corrected row is unsafe: an unknown key,
an Arabic text that changed since the sheet was exported, or a {placeholder}
the English text doesn't have. Comments are listed for the team; they
change nothing.

The CSV is UTF-8 with a byte-order mark, so Excel shows the Arabic.
"""

import argparse
import ast
import csv
import difflib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional

from shared import i18n
from shared.config import PROJECT_ROOT, TRIAL_DIR
from shared.field_guide import FIELDS_BY_PATH

TERMS_PATH = TRIAL_DIR / "arabic_terms.csv"
I18N_PATH = Path(i18n.__file__)
COLUMNS = ("key", "English", "Arabic", "where it appears", "corrected Arabic", "comment")
# Keys of the field names and drop-down choices, so every row has one key.
FIELD_PREFIX = "field_label:"  # e.g. field_label:residual_limb.pain
CHOICE_PREFIX = "choice:"  # e.g. choice:AmputationLevel.transtibial


@dataclass
class Term:
    key: str
    english: str
    arabic: str
    where: str


# ---- Export -------------------------------------------------------------


def _source_files(root: Path) -> list[Path]:
    """The templates and modules that show interface text (not tests, not i18n itself)."""
    files = [root / "app.py", *root.glob("*/templates/*.html"), *root.glob("*/*.py")]
    return sorted(p for p in files if p.parent.name != "tests" and p.name not in ("i18n.py", "arabic_terms.py"))


def where_used(key: str, sources: dict[Path, str], root: Path) -> str:
    """The files that use a TEXT key: by name, or by building it from a prefix ('component.' ~ key)."""
    exact = re.compile(rf"""(['"]){re.escape(key)}\1""")
    found = [path for path, text in sources.items() if exact.search(text)]
    parts = key.split(".")
    for cut in range(len(parts) - 1, 0, -1):
        if found:
            break
        prefix = re.escape(".".join(parts[:cut]) + ".")
        built = re.compile(rf"""(['"]){prefix}\1\s*~|f(['"]){prefix}\{{""")
        found = [path for path, text in sources.items() if built.search(text)]
    return "; ".join(path.relative_to(root).as_posix() for path in found) or "(not found)"


def _helper_users(helper: str, sources: dict[Path, str], root: Path) -> str:
    # app.py only hands the helper to the templates.
    return "; ".join(path.relative_to(root).as_posix() for path, text in sources.items()
                     if f"{helper}(" in text and path.name != "app.py")


def collect_terms(root: Path = PROJECT_ROOT) -> list[Term]:
    sources = {path: path.read_text(encoding="utf-8") for path in _source_files(root)}
    terms = [Term(key, texts["en"], texts["ar"], where_used(key, sources, root))
             for key, texts in i18n.TEXT.items()]
    field_where = _helper_users("field_label", sources, root)
    terms += [Term(FIELD_PREFIX + path, FIELDS_BY_PATH[path].label, arabic, field_where)
              for path, arabic in i18n.FIELD_LABELS["ar"].items()]
    choice_where = _helper_users("value_label", sources, root)
    terms += [Term(f"{CHOICE_PREFIX}{enum}.{value}", value.replace("_", " "), arabic, choice_where)
              for enum, choices in i18n.VALUE_LABELS["ar"].items() for value, arabic in choices.items()]
    return terms


def read_sheet(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    if rows and set(COLUMNS) - set(rows[0]):
        raise ValueError(f"{path}: expected the columns {', '.join(COLUMNS)}")
    return rows


def _filled(row: dict[str, str]) -> bool:
    return bool((row.get("corrected Arabic") or "").strip() or (row.get("comment") or "").strip())


def export(path: Path = TERMS_PATH, root: Path = PROJECT_ROOT, force: bool = False) -> int:
    """Write the sheet; returns the number of rows. Never overwrites a sheet someone has filled in."""
    if path.is_file() and not force and any(_filled(row) for row in read_sheet(path)):
        raise FileExistsError(f"{path} already has corrections or comments; apply it first, "
                              "or export with --force to replace it")
    path.parent.mkdir(parents=True, exist_ok=True)
    terms = collect_terms(root)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(COLUMNS)
        writer.writerows([term.key, term.english, term.arabic, term.where, "", ""] for term in terms)
    return len(terms)


# ---- Apply --------------------------------------------------------------


def _arabic_literals(source: str) -> dict[str, ast.Constant]:
    """Sheet key -> the Arabic string literal in shared/i18n.py's source (its exact position)."""
    found: dict[str, ast.Constant] = {}
    for node in ast.parse(source).body:
        if isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            name, value = node.target.id, node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            name, value = node.targets[0].id, node.value
        else:
            continue
        if not isinstance(value, ast.Dict):
            continue
        entries = {k.value: v for k, v in zip(value.keys, value.values) if isinstance(k, ast.Constant)}
        if name == "TEXT":
            for key, texts in entries.items():
                languages = {k.value: v for k, v in zip(texts.keys, texts.values) if isinstance(k, ast.Constant)}
                found[key] = languages.get("ar")
        elif name == "FIELD_LABELS":
            for k, v in zip(entries["ar"].keys, entries["ar"].values):
                found[FIELD_PREFIX + k.value] = v
        elif name == "VALUE_LABELS":
            for enum_key, choices in zip(entries["ar"].keys, entries["ar"].values):
                for k, v in zip(choices.keys, choices.values):
                    found[f"{CHOICE_PREFIX}{enum_key.value}.{k.value}"] = v
    return found


def _python_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n") + '"'


@dataclass
class Correction:
    key: str
    old: str
    new: str


def plan(rows: list[dict[str, str]]) -> tuple[list[Correction], list[str], list[str]]:
    """(corrections to make, problems that stop the apply, comments for the team)."""
    current = {term.key: term for term in collect_terms()}
    corrections, problems, comments = [], [], []
    for number, row in enumerate(rows, start=2):  # row 1 is the header
        key = (row.get("key") or "").strip()
        new = (row.get("corrected Arabic") or "").strip()
        comment = (row.get("comment") or "").strip()
        if comment:
            comments.append(f"{key}: {comment}")
        if not new:
            continue
        term = current.get(key)
        if term is None:
            problems.append(f"row {number}: unknown key {key!r}")
            continue
        if row.get("Arabic", "") != term.arabic:
            problems.append(f"row {number} ({key}): the Arabic in shared/i18n.py changed after the sheet "
                            "was exported; export a new sheet and copy the correction over")
            continue
        if new == term.arabic:
            continue
        if key in i18n.TEXT:
            try:
                extra = i18n.placeholders(new) - i18n.placeholders(term.english)
            except ValueError:
                problems.append(f"row {number} ({key}): a {{ or }} doesn't form a placeholder; "
                                f"keep placeholders exactly as in the English, e.g. {{n}}")
                continue
            if extra:
                problems.append(f"row {number} ({key}): {', '.join('{' + p + '}' for p in sorted(extra))} "
                                f"is not in the English text; only these can be used: "
                                f"{', '.join('{' + p + '}' for p in sorted(i18n.placeholders(term.english))) or 'none'}")
                continue
        corrections.append(Correction(key, term.arabic, new))
    return corrections, problems, comments


def corrected_source(source: str, corrections: list[Correction]) -> str:
    """The i18n.py source with only the corrected Arabic strings replaced."""
    literals = _arabic_literals(source)
    data = source.encode("utf-8")  # ast positions are in UTF-8 bytes
    line_starts = [0]
    for line in data.splitlines(keepends=True):
        line_starts.append(line_starts[-1] + len(line))
    spans = []
    for correction in corrections:
        node = literals.get(correction.key)
        if not isinstance(node, ast.Constant) or node.value != correction.old:
            raise ValueError(f"{correction.key}: its Arabic string literal was not found in the source")
        start = line_starts[node.lineno - 1] + node.col_offset
        end = line_starts[node.end_lineno - 1] + node.end_col_offset
        spans.append((start, end, _python_string(correction.new).encode("utf-8")))
    for start, end, new in sorted(spans, reverse=True):  # from the end, so earlier positions stay valid
        data = data[:start] + new + data[end:]
    result = data.decode("utf-8")
    ast.parse(result)  # still valid Python
    return result


def apply(sheet: Path, i18n_path: Path = I18N_PATH, confirm: Callable[[str], bool] = None,
          out=sys.stdout) -> Optional[int]:
    """Apply a filled-in sheet. Returns the number of texts changed, or None if nothing was written."""
    corrections, problems, comments = plan(read_sheet(sheet))
    if comments:
        print("Comments (for the team; they change nothing):", file=out)
        for comment in comments:
            print(f"  {comment}", file=out)
    if problems:
        print("Nothing written. Fix these rows first:", file=out)
        for problem in problems:
            print(f"  {problem}", file=out)
        return None
    if not corrections:
        print("No corrected Arabic in the sheet; nothing to change.", file=out)
        return None
    old = i18n_path.read_text(encoding="utf-8")
    new = corrected_source(old, corrections)
    diff = difflib.unified_diff(old.splitlines(keepends=True), new.splitlines(keepends=True),
                                "shared/i18n.py (now)", "shared/i18n.py (corrected)")
    print("".join(diff), file=out)
    question = f"Write {len(corrections)} corrected text(s) to {i18n_path.name}? [y/N] "
    if not (confirm or (lambda q: input(q).strip().lower() in ("y", "yes")))(question):
        print("Nothing written.", file=out)
        return None
    i18n_path.write_text(new, encoding="utf-8")
    print(f"Written. Run python -m unittest to check the texts.", file=out)
    return len(corrections)


def main(argv=None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m shared.arabic_terms", description=__doc__.splitlines()[0])
    commands = parser.add_subparsers(dest="command", required=True)
    exporting = commands.add_parser("export", help="write the term sheet")
    exporting.add_argument("--out", type=Path, default=TERMS_PATH)
    exporting.add_argument("--force", action="store_true", help="replace a sheet that has corrections")
    applying = commands.add_parser("apply", help="put a filled-in sheet's corrections into shared/i18n.py")
    applying.add_argument("sheet", type=Path)
    applying.add_argument("--yes", action="store_true", help="write without asking (after showing the diff)")
    args = parser.parse_args(argv)
    if args.command == "export":
        try:
            rows = export(args.out, force=args.force)
        except FileExistsError as e:
            sys.exit(str(e))
        print(f"{rows} texts written to {args.out}")
    else:
        apply(args.sheet, confirm=(lambda question: True) if args.yes else None)


if __name__ == "__main__":
    main()

"""Knowledge items: the curated statements in the research brief's knowledge-item structure.

  python -m knowledge.items          writes data/knowledge/items.json and items_to_curate.csv
                                     (python -m knowledge.evidence_rules does the same)

Built in two steps:
1. build_items(): one item per statement in reasoning/component_guide.py (the
   component rules, the K-level descriptions and cautions) and
   reasoning/fitting_guide.py, in that order, holding only what the guides
   and the catalog record: the statement id, the quote (and the list it
   introduces), the domain, its component or fitting section, the source,
   the citation, the source's year and kind, and the grade exactly as
   stored. Evidence values "unassigned", "unreviewed".
2. knowledge/evidence_rules.py applies the owner's rule table
   (data/knowledge/evidence_rules.csv). Nothing else sets a clinical value
   (CLAUDE.md).

items.json is UTF-8 with Arabic kept readable; the same guides and table
always give the same file. Next to it, items_to_curate.csv lists the items no
rule classified, with empty columns for the owner (UTF-8 with a byte-order
mark, so Excel shows every character). Neither is ever replaced while it
holds something only the team can give (KnowledgeItem.kept_by_team, or a
filled-in cell of the sheet); then nothing is written.
"""

import argparse
import csv
import json
import re
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from typing import Optional

from knowledge.evidence_rules import CONDITIONS, EvidenceRule, apply_rules, load_rules
from knowledge.models import KnowledgeItem
from reasoning import component_guide, fitting_guide
from reasoning.component_support import cite
from reasoning.models import GuidelineStatement
from shared.config import EVIDENCE_RULES_PATH, KNOWLEDGE_ITEMS_PATH, PROJECT_ROOT

ITEMS_FILE_VERSION = 1  # raise when the shape of an item changes
DOMAIN = "prosthetics"  # both guides cover the brief's prosthetics domain

CURATE_FILE = "items_to_curate.csv"  # written next to items.json
CURATE_COLUMNS = ("knowledge_id", "source", "page", "grade", "quote",
                  "evidence_layer", "evidence_tag", "confidence", "population", "limitations", "note")
OWNER_COLUMNS = CURATE_COLUMNS[5:]  # left empty for the owner
_PAGE = re.compile(r", p\. (\d+(?:-\d+)?)$")  # the end of a citation


def item_from_statement(statement: GuidelineStatement) -> KnowledgeItem:
    cited = cite(statement)  # the title, year and source type from the catalog
    return KnowledgeItem(
        knowledge_id=statement.id,
        statement=statement.quote.text,
        list_items=statement.quote.items,
        domain=DOMAIN,
        topic=statement.component,
        source_id=statement.doc_id,
        citation=cited.citation(statement.quote),  # as the review page shows it
        date=str(cited.year) if cited.year else "",
        source_type=cited.source_type,
        grade_as_printed=statement.grade or "",
    )


def build_items() -> list[KnowledgeItem]:
    statements = (*component_guide.ALL_STATEMENTS, *fitting_guide.ALL_STATEMENTS)
    return [item_from_statement(statement) for statement in statements]


def classified_items(rules: Optional[list[EvidenceRule]] = None) -> list[KnowledgeItem]:
    """build_items() with the owner's rules applied (read from the table unless given)."""
    return apply_rules(build_items(), load_rules() if rules is None else rules)


def to_curate(items: list[KnowledgeItem]) -> list[KnowledgeItem]:
    """The items no rule classified (none matched, or a "per item" rule) and nobody has yet."""
    return [item for item in items if item.assigned_by == "none"]


def to_json(items: list[KnowledgeItem]) -> str:
    data = {"items_file_version": ITEMS_FILE_VERSION, "items": [asdict(item) for item in items]}
    return json.dumps(data, ensure_ascii=False, indent=2) + "\n"


def write_items(items: list[KnowledgeItem], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(to_json(items), encoding="utf-8", newline="\n")


def read_items(path: Path) -> list[KnowledgeItem]:
    """The items in an exported file, each checked again. ValueError if one is not valid."""
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("items_file_version") != ITEMS_FILE_VERSION:
        raise ValueError(f"{path}: items_file_version {data.get('items_file_version')!r}, "
                         f"expected {ITEMS_FILE_VERSION}")
    items = []
    for number, entry in enumerate(data["items"], start=1):
        try:
            items.append(KnowledgeItem(**{**entry, "list_items": tuple(entry.get("list_items", ()))}))
        except TypeError as error:  # a field is misspelled or missing
            raise ValueError(f"item {number} ({entry.get('knowledge_id')}): {error}") from None
    return items


def write_curate(items: list[KnowledgeItem], path: Path) -> None:
    """The curation sheet: each item's source, page, grade and quote; the owner's columns empty."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(CURATE_COLUMNS)
        for item in items:
            quote = "\n".join((item.statement, *item.list_items))  # a list item per line, as printed
            writer.writerow([item.knowledge_id, item.source_id, _PAGE.search(item.citation).group(1),
                             item.grade_as_printed, quote, *([""] * len(OWNER_COLUMNS))])


def read_curate(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        if tuple(reader.fieldnames or ()) != CURATE_COLUMNS:
            raise ValueError(f"expected the columns {', '.join(CURATE_COLUMNS)}")
        return list(reader)


def _refuse_to_replace(items_path: Path, curate_path: Path) -> None:
    """FileExistsError if either file holds something only the team can give, or can't be read."""
    if items_path.is_file():
        try:
            existing = read_items(items_path)
        except (ValueError, KeyError, AttributeError) as error:
            raise FileExistsError(f"{items_path} could not be read ({error}), so nothing was written; "
                                  "export with --force to replace it") from None
        kept = [f"{item.knowledge_id} ({', '.join(item.kept_by_team())})"
                for item in existing if item.kept_by_team()]
        if kept:
            raise FileExistsError(f"{items_path} holds values only the team can give, so nothing was written: "
                                  f"{'; '.join(kept)}. Export with --force to replace it")
    if curate_path.is_file():
        try:
            rows = read_curate(curate_path)
        except ValueError as error:
            raise FileExistsError(f"{curate_path} could not be read ({error}), so nothing was written; "
                                  "export with --force to replace it") from None
        filled = [row["knowledge_id"] for row in rows if any((row[c] or "").strip() for c in OWNER_COLUMNS)]
        if filled:
            raise FileExistsError(f"{curate_path} has been filled in ({', '.join(filled)}), so nothing was "
                                  "written. Export with --force to replace it")


def export(path: Path = KNOWLEDGE_ITEMS_PATH, force: bool = False,
           rules: Optional[list[EvidenceRule]] = None) -> list[KnowledgeItem]:
    """Write items.json to path and items_to_curate.csv next to it; returns the items.

    Writes nothing if a rule is not valid or two rules match one item
    (ValueError), or if a file holds the team's values (FileExistsError).
    """
    items = classified_items(rules)
    curate_path = path.parent / CURATE_FILE
    if not force:
        _refuse_to_replace(path, curate_path)
    write_items(items, path)
    write_curate(to_curate(items), curate_path)
    return items


def summary(items: list[KnowledgeItem], rules: list[EvidenceRule]) -> list[str]:
    assigned = Counter(item.assigned_by for item in items)
    lines = [f"{len(items)} knowledge items ({len(component_guide.ALL_STATEMENTS)} component, "
             f"{len(fitting_guide.ALL_STATEMENTS)} fitting); rules: {_shown(EVIDENCE_RULES_PATH)}"]
    for rule in rules:
        if rule.per_item:
            matched = sum(CONDITIONS[rule.rule_id].matches(item) for item in items)
            lines.append(f"  {rule.rule_id:<4} sets nothing ('per item'); matches {matched}")
        else:
            lines.append(f"  {rule.rule_id:<4} assigned {assigned[rule.rule_id]:>3}")
    rule_assigned = [item for item in items if item.validation_status == "rule-assigned"]
    layer_left = sum(item.evidence_layer == "unassigned" for item in rule_assigned)
    lines.append(f"  rule-assigned {len(rule_assigned)} (the rule left the layer unassigned: {layer_left})")
    lines.append(f"  left to classify {len(to_curate(items))}")
    return lines


def _shown(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return str(path)


def main(argv=None, prog: str = "python -m knowledge.items") -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog=prog, description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=KNOWLEDGE_ITEMS_PATH,
                        help=f"items.json to write; {CURATE_FILE} goes next to it")
    parser.add_argument("--force", action="store_true",
                        help="replace files holding values only the team can give")
    args = parser.parse_args(argv)
    try:
        rules = load_rules()
        items = export(args.out, force=args.force, rules=rules)
    except (OSError, ValueError) as e:  # OSError: incl. FileExistsError and a missing rule table
        sys.exit(str(e))
    print("\n".join(summary(items, rules)))
    print(f"Written: {_shown(args.out)}, {_shown(args.out.parent / CURATE_FILE)}")


if __name__ == "__main__":
    main()

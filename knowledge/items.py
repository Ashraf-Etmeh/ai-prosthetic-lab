"""Knowledge items: the curated statements in the research brief's knowledge-item structure.

  python -m knowledge.items          writes data/knowledge/items.json

One item per statement in reasoning/component_guide.py (the component rules,
the K-level descriptions and cautions) and reasoning/fitting_guide.py, in
that order. An item holds only what the guides and the catalog already
record: the statement id, the quote (and the list it introduces), the
domain, its component or fitting section, the source, the citation, the
source's year and kind, and the grade exactly as stored. The clinical
judgements stay "unassigned" or empty and the item "unreviewed": they come
only from the owner's rule table or the owner's own values (CLAUDE.md), and
nothing here sets them.

The file is UTF-8 with Arabic kept readable, and the same guides always give
the same file. The export never overwrites a file in which a clinical value
or a review state has been set (knowledge/models.py TEAM_FIELDS).
"""

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

from knowledge.models import KnowledgeItem
from reasoning import component_guide, fitting_guide
from reasoning.component_support import cite
from reasoning.models import GuidelineStatement
from shared.config import KNOWLEDGE_ITEMS_PATH

ITEMS_FILE_VERSION = 1  # raise when the shape of an item changes
DOMAIN = "prosthetics"  # both guides cover the brief's prosthetics domain


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


def export(path: Path = KNOWLEDGE_ITEMS_PATH, force: bool = False) -> list[KnowledgeItem]:
    """Write every item to path; returns them. Never replaces values the team has set, unless forced."""
    if path.is_file() and not force:
        try:
            existing = read_items(path)
        except (ValueError, KeyError, AttributeError) as error:
            raise FileExistsError(f"{path} could not be read ({error}), so it was not replaced; "
                                  "export with --force to replace it") from None
        set_by_team = [f"{item.knowledge_id} ({', '.join(item.set_fields())})"
                       for item in existing if item.set_fields()]
        if set_by_team:
            raise FileExistsError(f"{path} has values set by the team, so it was not replaced: "
                                  f"{'; '.join(set_by_team)}. Export with --force to replace it")
    items = build_items()
    write_items(items, path)
    return items


def main(argv=None) -> None:
    sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(prog="python -m knowledge.items", description=__doc__.splitlines()[0])
    parser.add_argument("--out", type=Path, default=KNOWLEDGE_ITEMS_PATH)
    parser.add_argument("--force", action="store_true",
                        help="replace a file in which clinical values or a review state are set")
    args = parser.parse_args(argv)
    try:
        items = export(args.out, force=args.force)
    except FileExistsError as e:
        sys.exit(str(e))
    print(f"{len(items)} knowledge items written to {args.out} "
          f"({len(component_guide.ALL_STATEMENTS)} component, {len(fitting_guide.ALL_STATEMENTS)} fitting)")


if __name__ == "__main__":
    main()

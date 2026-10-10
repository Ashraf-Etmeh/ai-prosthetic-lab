"""Tests for the KnowledgeItem model (knowledge/models.py) and the export (knowledge/items.py)."""

import dataclasses
import json
import tempfile
import unittest
from pathlib import Path

from knowledge.catalog import load_catalog
from knowledge.items import build_items, export, read_items, to_json, write_items
from knowledge.models import (
    CONFIDENCE_LEVELS,
    EVIDENCE_LAYERS,
    EVIDENCE_TAGS,
    TEAM_FIELDS,
    VALIDATION_STATUSES,
    KnowledgeItem,
)
from reasoning import component_guide, fitting_guide
from shared.config import KNOWLEDGE_ITEMS_PATH

STATEMENTS = (*component_guide.ALL_STATEMENTS, *fitting_guide.ALL_STATEMENTS)
RECORDED = ("knowledge_id", "statement", "list_items", "domain", "topic", "source_id", "citation", "date",
            "source_type", "grade_as_printed")


def make_item(**changes) -> KnowledgeItem:
    values = dict(knowledge_id="test_item", statement="A sentence.", domain="prosthetics", topic="knee",
                  source_id="test_doc", citation="Test Document (2020), p. 1", date="2020",
                  source_type="protocol")
    return KnowledgeItem(**{**values, **changes})


class ModelTests(unittest.TestCase):
    def test_new_item_is_unassigned_and_unreviewed(self):
        item = make_item()
        self.assertEqual((item.population, item.limitations), ("", ""))
        self.assertEqual((item.evidence_layer, item.evidence_tag, item.confidence),
                         ("unassigned", "unassigned", "unassigned"))
        self.assertEqual((item.validation_status, item.assigned_by), ("unreviewed", "none"))
        self.assertEqual(item.set_fields(), [])

    def test_every_field_is_recorded_or_the_teams(self):
        self.assertEqual(sorted(f.name for f in dataclasses.fields(KnowledgeItem)),
                         sorted((*RECORDED, *TEAM_FIELDS)))

    def test_allowed_values_accepted(self):
        for name, allowed in (("evidence_layer", EVIDENCE_LAYERS), ("evidence_tag", EVIDENCE_TAGS),
                              ("confidence", CONFIDENCE_LEVELS), ("validation_status", VALIDATION_STATUSES)):
            for value in allowed:
                with self.subTest(name, value=value):
                    self.assertEqual(getattr(make_item(**{name: value}, assigned_by="R1"), name), value)
        for value in ("R1", "R2", "R17", "manual", "none"):
            with self.subTest("assigned_by", value=value):
                self.assertEqual(make_item(assigned_by=value).assigned_by, value)

    def test_invalid_values_refused(self):
        invalid = {
            "evidence_layer": ("Established", "established ", "evidence based practice", "strong", "", None),
            "evidence_tag": ("direct", "Direct evidence", "indirect", "", None),
            "confidence": ("High", "moderate", "very low", "", None),
            "validation_status": ("reviewed", "Unreviewed", "unassigned", "", None),
            "assigned_by": ("R", "r1", "R1a", "R 1", "rule 1", "Manual", "None", "claude", "code", "", None),
        }
        for name, values in invalid.items():
            for value in values:
                with self.subTest(name, value=value):
                    # assigned_by "manual", so only the value itself can be refused
                    changes = {"assigned_by": "manual", name: value}
                    with self.assertRaises(ValueError):
                        make_item(**changes)

    def test_recorded_fields_required(self):
        for name in ("knowledge_id", "statement", "domain", "topic", "source_id", "citation"):
            for value in ("", "   ", None):
                with self.subTest(name, value=value), self.assertRaises(ValueError):
                    make_item(**{name: value})
        with self.assertRaises(TypeError):  # a field left out
            KnowledgeItem(knowledge_id="x", statement="A sentence.")

    def test_domain_and_source_type_are_catalog_values(self):
        for changes in ({"domain": "prosthetic"}, {"domain": "Prosthetics"}, {"source_type": "guideline"}):
            with self.subTest(changes), self.assertRaises(ValueError):
                make_item(**changes)

    def test_list_items_are_texts(self):
        self.assertEqual(make_item(list_items=("First;", "Second.")).list_items, ("First;", "Second."))
        for value in (["First;"], ("First;", ""), ("First;", None), "First;"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                make_item(list_items=value)

    def test_clinical_value_needs_its_origin(self):
        # Nothing clinical without the owner's rule or "manual" in assigned_by.
        for name, value in (("evidence_layer", "established"), ("evidence_tag", "inferred"),
                            ("confidence", "low"), ("population", "Adults"), ("limitations", "Small sample")):
            with self.subTest(name):
                with self.assertRaises(ValueError):
                    make_item(**{name: value})
                self.assertEqual(make_item(**{name: value}, assigned_by="R3").set_fields(), [name, "assigned_by"])
                make_item(**{name: value}, assigned_by="manual")

    def test_rule_assigned_names_the_rule(self):
        make_item(validation_status="rule-assigned", assigned_by="R1", confidence="medium")
        for assigned_by in ("manual", "none"):
            with self.subTest(assigned_by), self.assertRaises(ValueError):
                make_item(validation_status="rule-assigned", assigned_by=assigned_by)

    def test_values_cannot_be_changed_unchecked(self):
        item = make_item()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            item.confidence = "high"
        with self.assertRaises(ValueError):
            dataclasses.replace(item, confidence="certain", assigned_by="manual")
        self.assertEqual(dataclasses.replace(item, confidence="high", assigned_by="manual").confidence, "high")


class BuildTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.items = build_items()
        cls.catalog = {doc.id: doc for doc in load_catalog()}

    def test_one_item_per_statement(self):
        self.assertEqual(len(self.items), len(component_guide.ALL_STATEMENTS) + len(fitting_guide.ALL_STATEMENTS))
        self.assertEqual([item.knowledge_id for item in self.items], [s.id for s in STATEMENTS])

    def test_ids_unique_and_equal_to_statement_ids(self):
        ids = [item.knowledge_id for item in self.items]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertEqual(set(ids), {s.id for s in STATEMENTS})

    def test_every_item_has_a_source_and_citation(self):
        for item, statement in zip(self.items, STATEMENTS):
            with self.subTest(item.knowledge_id):
                self.assertEqual(item.source_id, statement.doc_id)
                self.assertIn(item.source_id, self.catalog)
                document = self.catalog[item.source_id]
                self.assertEqual(item.citation, f"{document.title} ({document.year}), {statement.quote.pages}")

    def test_recorded_fields_copied_exactly(self):
        for item, statement in zip(self.items, STATEMENTS):
            with self.subTest(item.knowledge_id):
                document = self.catalog[statement.doc_id]
                self.assertEqual(item.statement, statement.quote.text)  # the guide's quote, tested on its page
                self.assertEqual(item.list_items, statement.quote.items)
                self.assertEqual(item.domain, "prosthetics")
                self.assertEqual(item.topic, statement.component)
                self.assertEqual(item.date, str(document.year))
                self.assertEqual(item.source_type, document.source_type)
                self.assertEqual(item.grade_as_printed, statement.grade or "")

    def test_clinical_fields_left_for_the_team(self):
        for item in self.items:
            with self.subTest(item.knowledge_id):
                self.assertEqual(item.set_fields(), [])


class ExportTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.path = self.folder / "knowledge" / "items.json"

    def test_exporting_twice_gives_identical_files(self):
        export(self.path)
        first = self.path.read_bytes()
        export(self.path)
        self.assertEqual(self.path.read_bytes(), first)
        export(self.folder / "again.json")
        self.assertEqual((self.folder / "again.json").read_bytes(), first)

    def test_file_reads_back_as_the_same_items(self):
        items = export(self.path)
        self.assertEqual(read_items(self.path), items)
        data = json.loads(self.path.read_text(encoding="utf-8"))
        self.assertEqual(data["items_file_version"], 1)
        self.assertEqual(list(data["items"][0]), [f.name for f in dataclasses.fields(KnowledgeItem)])

    def test_utf8_with_arabic_readable(self):
        arabic = make_item(statement="لا يوجد دليل كافٍ.", population="البالغون", assigned_by="manual")
        write_items([arabic], self.path)
        text = self.path.read_bytes().decode("utf-8")  # fails if not UTF-8
        self.assertIn("لا يوجد دليل كافٍ.", text)
        self.assertIn("البالغون", text)
        self.assertNotIn("\\u06", text)  # not escaped
        self.assertEqual(read_items(self.path), [arabic])
        self.assertIn("“", to_json(build_items()))  # the sources' curly quotes kept as printed

    def test_values_set_by_the_team_are_never_overwritten(self):
        items = export(self.path)
        items[3] = dataclasses.replace(items[3], confidence="low", assigned_by="manual")
        write_items(items, self.path)
        filled = self.path.read_bytes()
        with self.assertRaises(FileExistsError) as refused:
            export(self.path)
        self.assertIn(f"{items[3].knowledge_id} (confidence, assigned_by)", str(refused.exception))
        self.assertEqual(self.path.read_bytes(), filled)
        export(self.path, force=True)
        self.assertNotEqual(self.path.read_bytes(), filled)

    def test_unreadable_file_is_not_overwritten(self):
        self.path.parent.mkdir(parents=True)
        for text in ("not json", "[]", '{"items_file_version": 99, "items": []}',
                     '{"items_file_version": 1, "items": [{"knowledge_id": "x"}]}'):
            with self.subTest(text):
                self.path.write_text(text, encoding="utf-8")
                with self.assertRaises(FileExistsError):
                    export(self.path)
                self.assertEqual(self.path.read_text(encoding="utf-8"), text)

    def test_exported_file_matches_the_guides(self):
        # data/knowledge/items.json is in git; it must follow the guides.
        if not KNOWLEDGE_ITEMS_PATH.is_file():
            self.skipTest(f"{KNOWLEDGE_ITEMS_PATH} not exported")
        stored = read_items(KNOWLEDGE_ITEMS_PATH)
        message = "data/knowledge/items.json is out of date: run python -m knowledge.items"
        self.assertEqual([item.knowledge_id for item in stored], [item.knowledge_id for item in build_items()],
                         message)
        for item, built in zip(stored, build_items()):
            with self.subTest(item.knowledge_id):
                self.assertEqual({name: getattr(item, name) for name in RECORDED},
                                 {name: getattr(built, name) for name in RECORDED}, message)


if __name__ == "__main__":
    unittest.main()

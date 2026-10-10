"""Tests for knowledge/evidence_rules.py: the owner's rule table applied to the knowledge items, and the curation sheet."""

import csv
import dataclasses
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest import mock

from knowledge import evidence_rules
from knowledge.catalog import load_catalog
from knowledge.evidence_rules import (
    COLUMNS,
    CONDITIONS,
    ICRC_MANUAL,
    WHO_STANDARDS,
    Condition,
    EvidenceRule,
    apply_rules,
    load_rules,
)
from knowledge.items import (
    CURATE_COLUMNS,
    CURATE_FILE,
    build_items,
    classified_items,
    export,
    read_curate,
    to_curate,
    write_curate,
)
from knowledge.models import EVIDENCE_FIELDS

# What a rule may change; everything else stays as built.
RULE_FIELDS = (*EVIDENCE_FIELDS, "validation_status", "assigned_by")
VALID_ROW = {"rule_id": "R1", "matches": "Some documents", "evidence_layer": "emerging",
             "evidence_tag": "proposed", "confidence": "low", "basis": "A reason"}


def write_table(path: Path, rows: list[dict], columns=COLUMNS) -> Path:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=columns)
        writer.writeheader()
        writer.writerows(rows)
    return path


def rule(rule_id: str, layer: str = "emerging", tag: str = "proposed", confidence: str = "low") -> EvidenceRule:
    return EvidenceRule(rule_id, "test", layer, tag, confidence, "test")


class OwnersTableTests(unittest.TestCase):
    def test_table_loads_and_every_rule_has_one_condition(self):
        rules = load_rules()
        self.assertEqual([r.rule_id for r in rules], list(CONDITIONS))

    def test_conditions_name_catalogued_documents_and_existing_items(self):
        catalog = {doc.id for doc in load_catalog()}
        ids = {item.knowledge_id for item in build_items()}
        for rule_id, condition in CONDITIONS.items():
            with self.subTest(rule_id):
                self.assertLessEqual(condition.source_ids, catalog)
                self.assertLessEqual(condition.knowledge_ids or frozenset(), ids)
                self.assertLessEqual(condition.except_knowledge_ids, ids)

    def test_approved_mapping(self):
        # As shown to and approved by the owner on 2026-10-10 (FUTURE_WORK.md).
        items = classified_items()
        self.assertEqual(Counter(item.assigned_by for item in items),
                         Counter({"R8": 28, "R6": 10, "R5": 5, "R2": 4, "R3": 4, "R4": 4, "R7": 4}))
        by_id = {item.knowledge_id: item for item in items}
        for knowledge_id, rule_id in (("va_dod_ll_17_microprocessor_knee", "R2"),
                                      ("va_dod_ul_8_no_specific_component", "R3"),
                                      ("va_dod_ll_algorithm_fitting", "R4"), ("cms_k2_description", "R5"),
                                      ("cms_k_level_intended_use", "R6"), ("cms_k2_microprocessor_knee", "R6"),
                                      ("who_delivery_check", "R7"), ("icrc_ready_for_fitting", "R8")):
            with self.subTest(knowledge_id):
                self.assertEqual(by_id[knowledge_id].assigned_by, rule_id)

    def test_values_copied_from_the_table(self):
        rules = {r.rule_id: r for r in load_rules()}
        for item in classified_items():
            with self.subTest(item.knowledge_id):
                source = rules[item.assigned_by]
                self.assertEqual(item.validation_status, "rule-assigned")
                self.assertEqual((item.evidence_layer, item.evidence_tag, item.confidence),
                                 (source.evidence_layer, source.evidence_tag, source.confidence))


class ApplyTests(unittest.TestCase):
    def test_applying_twice_gives_identical_results(self):
        rules = load_rules()
        once = apply_rules(build_items(), rules)
        self.assertEqual(apply_rules(once, rules), once)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "items.json"
            export(path)
            first = (path.read_bytes(), (path.parent / CURATE_FILE).read_bytes())
            export(path)
            self.assertEqual((path.read_bytes(), (path.parent / CURATE_FILE).read_bytes()), first)

    def test_rules_change_nothing_else(self):
        built = build_items()
        for before, after in zip(built, classified_items()):
            with self.subTest(before.knowledge_id):
                for f in dataclasses.fields(before):
                    if f.name not in RULE_FIELDS:
                        self.assertEqual(getattr(after, f.name), getattr(before, f.name), f.name)

    def test_rules_never_touch_population_or_limitations(self):
        filled = [dataclasses.replace(item, population=f"Population {n}", limitations=f"Limitation {n}")
                  for n, item in enumerate(build_items())]
        result = apply_rules(filled, load_rules())
        self.assertTrue(all(item.assigned_by != "none" for item in result))
        self.assertEqual([(i.population, i.limitations) for i in result],
                         [(i.population, i.limitations) for i in filled])
        self.assertEqual([(i.population, i.limitations) for i in classified_items()], [("", "")] * len(result))

    def test_overlapping_rules_refused(self):
        rules = load_rules()
        overlapping = {**CONDITIONS, "R8": Condition(ICRC_MANUAL | WHO_STANDARDS)}
        with self.assertRaises(ValueError) as refused:
            apply_rules(build_items(), rules, overlapping)
        message = str(refused.exception)
        for item in build_items():
            if item.source_id in WHO_STANDARDS:
                self.assertIn(f"{item.knowledge_id} matches R7, R8", message)
        self.assertNotIn("icrc_", message)

    def test_overlapping_rules_change_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "items.json"
            export(path)
            before = (path.read_bytes(), (path.parent / CURATE_FILE).read_bytes())
            with mock.patch.dict(evidence_rules.CONDITIONS, {"R6": Condition(evidence_rules.CMS)}):
                with self.assertRaises(ValueError) as refused:
                    export(path, force=True)  # not even with --force
            self.assertIn("cms_k0_description matches R5, R6", str(refused.exception))
            self.assertEqual((path.read_bytes(), (path.parent / CURATE_FILE).read_bytes()), before)

    def test_per_item_or_no_rule_leaves_items_unassigned(self):
        items = build_items()
        icrc = [item for item in items if item.source_id in ICRC_MANUAL]
        per_item = [r if r.rule_id != "R8" else dataclasses.replace(r, evidence_layer="per item",
                                                                       evidence_tag="", confidence="")
                    for r in load_rules()]
        without_r8 = [r for r in load_rules() if r.rule_id != "R8"]
        for rules in (per_item, without_r8):
            with self.subTest([r.rule_id for r in rules]):
                result = {item.knowledge_id: item for item in apply_rules(classified_items(), rules)}
                for item in icrc:
                    self.assertEqual(result[item.knowledge_id], item)  # the old R8 values undone
                self.assertEqual({i.knowledge_id for i in to_curate(list(result.values()))},
                                 {i.knowledge_id for i in icrc})

    def test_values_set_by_hand_or_reviewed_are_not_replaced(self):
        items = build_items()
        self.assertEqual((items[0].knowledge_id, items[1].knowledge_id),
                         ("va_dod_ll_17_microprocessor_knee", "cms_k2_microprocessor_knee"))
        manual = dataclasses.replace(items[0], confidence="high", assigned_by="manual")
        reviewed = dataclasses.replace(items[1], validation_status="owner-reviewed", assigned_by="R6")
        with self.assertRaises(ValueError) as refused:
            apply_rules([manual, reviewed, *items[2:]], load_rules())
        self.assertIn(f"{manual.knowledge_id} matches R2", str(refused.exception))
        self.assertIn(f"{reviewed.knowledge_id} matches R6", str(refused.exception))
        # Kept when no rule matches.
        self.assertEqual(apply_rules([manual], [r for r in load_rules() if r.rule_id != "R2"]), [manual])


class RuleTableRefusalTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "evidence_rules.csv"
        self.conditions = {"R1": Condition(ICRC_MANUAL)}

    def load(self, rows, columns=COLUMNS, conditions=None):
        return load_rules(write_table(self.path, rows, columns), conditions or self.conditions)

    def test_a_valid_table_loads(self):
        self.assertEqual(self.load([VALID_ROW]), [EvidenceRule(**VALID_ROW)])
        self.assertTrue(self.load([{**VALID_ROW, "evidence_layer": "per item", "evidence_tag": "",
                                    "confidence": "per item"}])[0].per_item)
        self.assertEqual(len(self.load([VALID_ROW, dict.fromkeys(COLUMNS, "")])), 1)  # an empty line

    def test_a_rule_with_an_invalid_value_is_refused(self):
        invalid = {
            "rule_id": ("1", "r1", "R1a", "Rule 1", "R 1", ""),
            "evidence_layer": ("Established", "established ", "strong", "per-item", ""),
            "evidence_tag": ("direct", "Direct evidence", "per item", ""),
            "confidence": ("very high", "Medium", "moderate", "per item", ""),
        }
        for name, values in invalid.items():
            for value in values:
                with self.subTest(name, value=value), self.assertRaises(ValueError) as refused:
                    self.load([{**VALID_ROW, name: value}])
                self.assertIn("row 2", str(refused.exception))
        # A "per item" rule sets nothing, so it can't name a tag or confidence.
        for name in ("evidence_tag", "confidence"):
            with self.subTest("per item", name=name), self.assertRaises(ValueError):
                self.load([{**VALID_ROW, "evidence_layer": "per item", name: "low" if name == "confidence"
                            else "inferred"}])

    def test_a_table_of_another_shape_is_refused(self):
        with self.assertRaises(ValueError):  # a rule can't set population or limitations
            self.load([{**VALID_ROW, "population": "Adults"}], (*COLUMNS, "population"))
        with self.assertRaises(ValueError):
            self.load([{k: v for k, v in VALID_ROW.items() if k != "basis"}], COLUMNS[:-1])
        with self.assertRaises(ValueError):
            self.load([VALID_ROW, VALID_ROW])  # the same id twice
        with self.assertRaises(ValueError):  # a rule without a condition, or a condition without a rule
            self.load([VALID_ROW, {**VALID_ROW, "rule_id": "R2"}])
        with self.assertRaises(ValueError):
            self.load([VALID_ROW], conditions={**self.conditions, "R2": Condition(WHO_STANDARDS)})
        self.path.write_text(",".join(COLUMNS) + "\nR1,x,emerging,proposed,low,y,extra\n", encoding="utf-8")
        with self.assertRaises(ValueError):  # more cells than columns
            load_rules(self.path, self.conditions)


class CurationSheetTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.items_path = Path(tmp.name) / "items.json"
        self.sheet = Path(tmp.name) / CURATE_FILE

    def test_only_items_no_rule_classified_are_listed(self):
        items = export(self.items_path)
        self.assertEqual(read_curate(self.sheet), [])  # every item has a rule today
        self.assertTrue(any(i.evidence_layer == "unassigned" for i in items))  # not listed: the rule's choice
        with self.sheet.open(encoding="utf-8-sig", newline="") as f:
            self.assertEqual(tuple(next(csv.reader(f))), CURATE_COLUMNS)

    def test_rows_quote_word_for_word_with_empty_owner_columns(self):
        items = {item.knowledge_id: item for item in build_items()}
        chosen = [items["icrc_ready_for_fitting"], items["va_dod_ll_algorithm_fitting"]]
        write_curate(chosen, self.sheet)
        rows = read_curate(self.sheet)
        self.assertEqual(rows[0]["quote"], "\n".join((chosen[0].statement, *chosen[0].list_items)))
        self.assertEqual((rows[0]["source"], rows[0]["page"], rows[0]["grade"]),
                         ("prosthetic_gait_analysis_icrc_manual_2014", "49", ""))
        self.assertEqual((rows[1]["quote"], rows[1]["page"]), (chosen[1].statement, "144"))
        for row in rows:
            self.assertEqual([row[c] for c in CURATE_COLUMNS[5:]], [""] * 6)

    def test_a_filled_in_sheet_is_never_overwritten(self):
        export(self.items_path)
        write_curate([build_items()[0]], self.sheet)
        rows = read_curate(self.sheet)
        rows[0]["note"] = "checked with the team"
        with self.sheet.open("w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=CURATE_COLUMNS)
            writer.writeheader()
            writer.writerows(rows)
        filled, items_before = self.sheet.read_bytes(), self.items_path.read_bytes()
        with self.assertRaises(FileExistsError) as refused:
            export(self.items_path)
        self.assertIn(rows[0]["knowledge_id"], str(refused.exception))
        self.assertEqual((self.sheet.read_bytes(), self.items_path.read_bytes()), (filled, items_before))
        self.sheet.write_text("not the sheet\n", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            export(self.items_path)
        export(self.items_path, force=True)
        self.assertEqual(read_curate(self.sheet), [])


if __name__ == "__main__":
    unittest.main()

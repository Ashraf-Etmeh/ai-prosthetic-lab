"""Tests for knowledge/clinic_rules.py: the owner's file of clinic rules (data/knowledge/clinic_rules.csv),
each with its status, version, owner and approval date (SYSTEM_DESIGN.md §7.1)."""

import tempfile
import unittest
from pathlib import Path

from knowledge.clinic_rules import APPROVED, COLUMNS, DRAFT, ClinicRule, load_rules, rules_for
from orthotics import hard_stops

HEADER = ",".join(COLUMNS)


class ProjectFileTests(unittest.TestCase):
    def test_the_file_reads_and_names_every_hard_stop_the_code_applies(self):
        rules = load_rules()
        self.assertTrue(rules)
        self.assertEqual(set(rules_for("orthotics", "hard_stop")), set(hard_stops.RULES))
        for rule in rules:
            with self.subTest(rule.rule_id):
                self.assertIn(rule.status, (DRAFT, APPROVED))
                self.assertTrue(rule.source)


class LoadTests(unittest.TestCase):
    def load(self, *rows):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clinic_rules.csv"
            path.write_text("\n".join((HEADER, *rows)) + "\n", encoding="utf-8")
            return load_rules(path)

    def test_a_draft_and_an_approved_rule(self):
        draft, approved = self.load("ulcer,orthotics,hard_stop,draft,1,,,design map",
                                    "",  # an empty line, e.g. left by a spreadsheet
                                    "contracture,orthotics,hard_stop,approved,2,Dr Owner,2026-10-24,the owner")
        self.assertEqual((draft.approved, draft.version), (False, 1))
        self.assertEqual(approved, ClinicRule("contracture", "orthotics", "hard_stop", APPROVED, 2, "Dr Owner",
                                              "2026-10-24", "the owner"))

    def test_refused_rows(self):
        for row, says in (
                ("ulcer,orthotics,hard_stop,maybe,1,,,x", "status"),
                ("ulcer,orthotics,hard_stop,approved,1,,2026-10-24,x", "owner"),
                ("ulcer,orthotics,hard_stop,approved,1,Dr Owner,,x", "owner"),
                ("ulcer,orthotics,hard_stop,approved,1,Dr Owner,24 Oct,x", "date"),
                ("ulcer,orthotics,hard_stop,draft,1,,2026-10-24,x", "draft"),
                ("ulcer,orthotics,hard_stop,draft,0,,,x", "version"),
                ("ulcer,orthotics,hard_stop,draft,one,,,x", "version"),
                ("ulcer,gait,hard_stop,draft,1,,,x", "domain"),
                ("ulcer,orthotics,threshold,draft,1,,,x", "kind"),
                ("Ulcer Rule,orthotics,hard_stop,draft,1,,,x", "rule_id"),
                ("ulcer,orthotics,hard_stop,draft,1,,,x,extra", "more cells")):
            with self.subTest(row), self.assertRaisesRegex(ValueError, says):
                self.load(row)

    def test_a_rule_listed_twice_or_wrong_columns(self):
        with self.assertRaisesRegex(ValueError, "more than once"):
            self.load("ulcer,orthotics,hard_stop,draft,1,,,x", "ulcer,orthotics,hard_stop,draft,1,,,y")
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clinic_rules.csv"
            path.write_text("rule_id,status\nulcer,draft\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "columns"):
                load_rules(path)


if __name__ == "__main__":
    unittest.main()

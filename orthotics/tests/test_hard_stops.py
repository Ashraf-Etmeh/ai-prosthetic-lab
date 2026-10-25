"""Tests for orthotics/hard_stops.py: the design's four DRAFT hard-stop rules, applied to what was recorded.

The owner answered on 2026-10-24 "not yet, keep as drafts". Each rule's status
(draft or the clinic's, with its version) comes from the owner's file
data/knowledge/clinic_rules.csv and is shown beside it; every line quotes the
rule instead of saying in the tool's own voice what to do.
"""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from knowledge.clinic_rules import COLUMNS
from orthotics import hard_stops
from orthotics.hard_stops import (
    CLEAR,
    CONTRACTURE,
    FES_IMPLANT,
    INSENSATE,
    JUDGE,
    NOT_CHECKED,
    RULES,
    STOP,
    ULCER,
    WARN,
    case_checks,
    lacks_lining,
    stops,
)
from orthotics.plan import FES_REFERRAL, DesignOption, OptionPart, OrthoticPlan, Part
from orthotics.tests.helpers import OrthoticPageTestCase
from orthotics.tests.test_orthotics import full_case
from shared.i18n import TEXT


def check(case, rule, plan=None):
    return next(c for c in case_checks(case, plan) if c.rule == rule)


def with_exam(**values):
    case = full_case()
    for name, value in values.items():
        setattr(case.exam, name, value)
    case.exam.__post_init__()
    return case


class RuleTests(unittest.TestCase):
    def test_four_rules_in_the_maps_order(self):
        self.assertEqual([c.rule for c in case_checks(full_case())], list(RULES))
        self.assertEqual(RULES, (ULCER, INSENSATE, CONTRACTURE, FES_IMPLANT))

    def test_ulcer(self):
        for value, status, detail in (("yes", STOP, "ulcer_yes"), ("no", CLEAR, "ulcer_no"),
                                      ("unknown", NOT_CHECKED, "unknown"), (None, NOT_CHECKED, "not_recorded")):
            with self.subTest(value):
                found = check(with_exam(ulcer_infection_or_poor_blood_supply=value), ULCER)
                self.assertEqual((found.status, found.detail), (status, detail))

    def test_insensate_skin(self):
        for value, status, detail in (("reduced", WARN, "insensate"), ("absent", WARN, "insensate"),
                                      ("intact", CLEAR, "sensation_intact"), ("unknown", NOT_CHECKED, "unknown"),
                                      (None, NOT_CHECKED, "not_recorded")):
            with self.subTest(value):
                found = check(with_exam(protective_sensation=value), INSENSATE)
                self.assertEqual((found.status, found.detail), (status, detail))

    def test_insensate_skin_names_the_options_without_a_lining(self):
        case = with_exam(protective_sensation="reduced")
        plan = OrthoticPlan(options=[
            DesignOption("A", "solid_afo"),
            DesignOption("B", "hinged_afo", parts=[OptionPart(Part.EVA_LINING)]),
            DesignOption("C", "posterior_leaf_spring", parts=[OptionPart(Part.STRAPS)]),
        ])
        found = check(case, INSENSATE, plan)
        self.assertEqual((found.status, found.detail, found.params), (WARN, "insensate_options", {"ids": "A, C"}))
        self.assertEqual([lacks_lining(case, o) for o in plan.options], [True, False, True])
        # Whether a device is rigid is the orthotist's to say: the check never decides it.
        self.assertFalse(lacks_lining(with_exam(protective_sensation="intact"), plan.options[0]))
        self.assertFalse(lacks_lining(case, DesignOption("A", "fes")))

    def test_contracture_is_the_orthotists_judgement(self):
        self.assertEqual(check(with_exam(dorsiflexion_knee_extended_deg=None), CONTRACTURE).status, NOT_CHECKED)
        for angle, shown in ((-5, "-5"), (10, "+10")):
            found = check(with_exam(dorsiflexion_knee_extended_deg=angle), CONTRACTURE)
            self.assertEqual((found.status, found.detail, found.params), (JUDGE, "contracture", {"n": shown}))

    def test_fes_with_an_implant(self):
        fes_chosen = OrthoticPlan(chosen=FES_REFERRAL)
        for implanted, plan, status, detail in (
                ("yes", fes_chosen, STOP, "implant_fes_chosen"), ("yes", None, WARN, "implant_yes"),
                ("no", fes_chosen, CLEAR, "implant_no"), ("unknown", None, NOT_CHECKED, "unknown"),
                (None, None, NOT_CHECKED, "not_asked")):
            with self.subTest(implanted=implanted, fes=plan is not None):
                found = check(full_case(implanted_electronic_device=implanted), FES_IMPLANT, plan)
                self.assertEqual((found.status, found.detail), (status, detail))

    def test_stops_lists_only_the_matched_rules(self):
        case = with_exam(ulcer_infection_or_poor_blood_supply="yes")
        self.assertEqual([c.rule for c in stops(case_checks(case))], [ULCER])
        self.assertEqual(stops(case_checks(full_case())), [])

    def test_every_status_and_detail_has_its_text(self):
        for key in ([f"hard_status.{s}" for s in hard_stops.STATUSES] + [f"hard_detail.{d}" for d in hard_stops.DETAILS]
                    + [f"{p}.{r}" for p in ("hard", "hard_rule") for r in RULES]):
            with self.subTest(key):
                self.assertTrue(TEXT[key]["en"] and TEXT[key]["ar"])


class WordingTests(unittest.TestCase):
    """The owner's answer of 2026-10-24: the rules are drafts, not the owner's or the clinic's rules yet. Since then
    each rule's status comes from the owner's file (data/knowledge/clinic_rules.csv), not from its wording."""

    def test_no_text_calls_them_the_owners_rules(self):
        for key, texts in TEXT.items():
            if key.startswith(("hard", "know_here.expertise")):
                with self.subTest(key):
                    self.assertNotRegex(texts["en"], r"(?i)the owner's (hard|rules)")
                    # (The evidence rule table is the owner's: "جدول قواعد المالك للأدلة" is right.)
                    for claim in ("قواعد المالك من خريطة", "التي وضعها المالك"):
                        self.assertNotIn(claim, texts["ar"])

    def test_no_line_advises_in_the_tools_own_voice(self):
        for key in [k for k in TEXT if k.startswith("hard_detail.")]:
            with self.subTest(key):
                self.assertNotRegex(TEXT[key]["en"], r"(?i)\bneeds?\b|\bmust\b|\bshould\b")

    def test_each_check_carries_its_rules_row_in_the_owners_file(self):
        rows = hard_stops.clinic_rules()
        self.assertEqual(set(rows), set(RULES))
        for found in case_checks(full_case()):
            self.assertEqual(found.clinic_rule, rows[found.rule])

    def test_the_code_and_the_owners_file_must_name_the_same_rules(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "clinic_rules.csv"
            path.write_text(",".join(COLUMNS) + "\nulcer,orthotics,hard_stop,draft,1,,,design map\n", encoding="utf-8")
            with patch("knowledge.clinic_rules.config.CLINIC_RULES_PATH", path), self.assertRaises(ValueError):
                hard_stops.clinic_rules()


def rule_file(folder: Path, approved: dict) -> Path:
    """A copy of the four rules with some approved: {rule_id: (version, owner, date)}."""
    rows = [",".join(COLUMNS)]
    for rule in RULES:
        if rule in approved:
            version, owner, day = approved[rule]
            rows.append(f"{rule},orthotics,hard_stop,approved,{version},{owner},{day},design map")
        else:
            rows.append(f"{rule},orthotics,hard_stop,draft,1,,,design map")
    path = folder / "clinic_rules.csv"
    path.write_text("\n".join(rows) + "\n", encoding="utf-8")
    return path


class StatusOnThePagesTests(OrthoticPageTestCase):
    def test_while_drafts_each_rule_says_so_on_the_analysis_page_and_the_map(self):
        for url in (self.url("analysis"), "/orthotics"):
            with self.subTest(url):
                page = self.page(url)
                self.assertEqual(page.count("Draft rule, awaiting the owner's approval"), len(RULES))
                self.assertIn("Draft rules from the design's system map, awaiting the owner's approval", page)
                self.assertNotIn("The owner's rules", page)
                arabic = self.page(url, "ar")
                self.assertEqual(arabic.count("قاعدة مسوّدة بانتظار موافقة المالك"), len(RULES))
                self.assertIn("قواعد مسوّدة من خريطة النظام في التصميم", arabic)
        page = self.page(self.url("analysis"))
        self.assertIn("Hard-stop checks", page)
        self.assertIn("Recorded: -5°. The orthotist judges whether the design can accommodate it.", page)

    def test_a_matched_rule_shows_its_status_in_the_banner(self):
        resp = self.client.post("/intake/orthotics", data={**self.intake, "ulcer": "yes"})
        page = self.page(resp.headers["Location"])
        self.assertIn("A hard-stop rule matches what was recorded; the rule routes the case to a doctor: "
                      "Ulcer, infection or poor blood supply Draft rule, awaiting the owner's approval", page)
        self.assertIn("Recorded: yes. The rule routes the case to a doctor.", page)

    def test_an_approved_rule_is_shown_as_the_clinics_with_its_version(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = rule_file(Path(tmp), {"ulcer": (2, "Dr Owner", "2026-10-24")})
            with patch("knowledge.clinic_rules.config.CLINIC_RULES_PATH", path):
                page = self.page(self.url("analysis"))
                self.assertIn("Clinic rule, version 2, approved by Dr Owner on 2026-10-24", page)
                self.assertEqual(page.count("Draft rule, awaiting the owner's approval"), len(RULES) - 1)
                self.assertIn("awaiting the owner's approval: they are not the clinic's rules yet", page)  # 3 drafts
                self.assertIn("قاعدة العيادة، الإصدار", self.page(self.url("analysis"), "ar"))
            path = rule_file(Path(tmp), {rule: (1, "Dr Owner", "2026-10-24") for rule in RULES})
            with patch("knowledge.clinic_rules.config.CLINIC_RULES_PATH", path):
                page = self.page("/orthotics")
                self.assertNotIn("Draft rule", page)
                self.assertIn("Rules set and versioned by the clinic.", page)


if __name__ == "__main__":
    unittest.main()

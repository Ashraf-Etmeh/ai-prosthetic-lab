"""Tests for review/decision_log.py: saving review decisions to a JSON-lines file."""

import json
import tempfile
import unittest
from pathlib import Path

from knowledge.models import ProtocolChunk
from reasoning.component_support import component_support
from reasoning.fitting_support import fitting_support
from reasoning.gap_analysis import analyze_gaps
from review.decision_log import InvalidDecision, read_decisions, record_decision
from review.routes import judgement_summary
from shared.case_schema import ActivityProfile, Case, ResidualLimb
from shared.config import RETRIEVAL_LANGUAGES
from shared.store import CaseRecord

VOLUME = "residual_limb.volume_stability"
WOUND = "residual_limb.wound_status"

VOLUME_PASSAGE = ProtocolChunk(
    chunk_id="test_guideline_2024-0007",
    text="Residual limb volume should be stable before the definitive socket is cast.",
    source="01_guidelines/test.pdf",
    title="Test Guideline",
    year=2024,
    page=14,
    end_page=14,
    language="en",
    score=0.71,
)


def make_record(case_id: str = "case-a") -> CaseRecord:
    case = Case(amputation_level="transtibial", side="left", age_years=58, case_id=case_id)
    retrieved = {VOLUME: [VOLUME_PASSAGE]}
    return CaseRecord(case=case, retrieved_chunks=retrieved, gaps=analyze_gaps(case, retrieved))


class DecisionLogTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "logs" / "review_log.jsonl"  # folder made on first write
        self.record = make_record()

    def log(self, decision="approve", note=None, judgements=None, record=None, ui_language="en"):
        return record_decision(record or self.record, decision, note, judgements, path=self.path,
                               ui_language=ui_language)

    def gap_entry(self, entry: dict, field: str) -> dict:
        return next(gap for gap in entry["gaps"] if gap["field"] == field)

    def test_each_decision_adds_one_line(self):
        self.log("reject", note="wrong case")
        self.log("approve")
        lines = self.path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 2)
        self.assertEqual([json.loads(line)["decision"] for line in lines], ["reject", "approve"])
        self.assertEqual([e["decision"] for e in read_decisions(path=self.path)], ["reject", "approve"])

    def test_entry_keeps_a_copy_of_the_case(self):
        entry = self.log()
        self.assertEqual(entry["case_id"], "case-a")
        self.assertEqual(Case.from_dict(entry["case"]).to_dict(), self.record.case.to_dict())
        self.assertTrue(entry["logged_at"].endswith("+00:00"))  # UTC

    def test_cited_gap_keeps_quote_citation_and_passage(self):
        source = self.gap_entry(self.log(), VOLUME)["source"]
        self.assertEqual(source["chunk_id"], "test_guideline_2024-0007")
        self.assertEqual(source["citation"], "Test Guideline (2024), p. 14")
        self.assertEqual(source["quote"], VOLUME_PASSAGE.text)
        self.assertEqual(source["passage"], VOLUME_PASSAGE.text)
        self.assertEqual((source["file"], source["page"], source["score"]), ("01_guidelines/test.pdf", 14, 0.71))

    def test_every_gap_shown_is_logged(self):
        entry = self.log()
        self.assertEqual([g["field"] for g in entry["gaps"]], [g.field for g in self.record.gaps])
        self.assertIsNone(self.gap_entry(entry, WOUND)["source"])  # no passage for it here

    def test_gap_judgements(self):
        entry = self.log(judgements={VOLUME: "needed", WOUND: "not_needed"})
        self.assertEqual(self.gap_entry(entry, VOLUME)["reviewer_judgement"], "needed")
        self.assertEqual(self.gap_entry(entry, WOUND)["reviewer_judgement"], "not_needed")
        others = [g["reviewer_judgement"] for g in entry["gaps"] if g["field"] not in (VOLUME, WOUND)]
        self.assertTrue(others and all(j is None for j in others))

    def test_page_language_recorded_but_log_stays_english(self):
        self.assertEqual(self.log()["ui_language"], "en")
        entry = self.log(ui_language="ar")
        self.assertEqual((entry["log_version"], entry["ui_language"]), (4, "ar"))
        volume = self.gap_entry(entry, VOLUME)
        self.assertEqual(volume["label"], "Residual limb volume stability")
        self.assertTrue(volume["why_needed"].startswith("Residual limb volume stability was not recorded"))

    def test_settings_recorded(self):
        settings = self.log()["settings"]
        self.assertEqual(settings["embedding_model"], "BAAI/bge-m3")
        self.assertEqual(settings["retrieval_languages"], list(RETRIEVAL_LANGUAGES))

    def test_invalid_decisions_refused_and_nothing_written(self):
        for kwargs in [
            {"decision": "maybe"},
            {"decision": ""},
            {"decision": "edit"},  # an edit needs a note
            {"decision": "edit", "note": "   "},
            {"decision": "approve", "judgements": {VOLUME: "yes"}},
            {"decision": "approve", "judgements": {"age_years": "needed"}},  # not a gap of this case
        ]:
            with self.subTest(**kwargs):
                with self.assertRaises(InvalidDecision):
                    self.log(**kwargs)
        self.assertFalse(self.path.exists())

    def test_blank_note_is_none_and_arabic_stays_readable(self):
        self.assertIsNone(self.log(note="  ")["note"])
        self.log("edit", note="يجب قياس حجم الطرف المتبقي")
        self.assertIn("يجب قياس حجم الطرف المتبقي", self.path.read_text(encoding="utf-8"))

    def test_record_without_components(self):
        entry = self.log()
        self.assertIsNone(entry["components"])
        self.assertIsNone(entry["fitting"])
        with self.assertRaises(InvalidDecision):
            record_decision(self.record, "approve", path=self.path,
                            statement_judgements={"cms_elevated_vacuum": "relevant"})

    def test_read_decisions_by_case(self):
        self.assertEqual(read_decisions(path=self.path), [])  # no file yet
        self.log()
        self.log(record=make_record("case-b"))
        self.assertEqual([e["case_id"] for e in read_decisions("case-b", path=self.path)], ["case-b"])
        self.assertEqual(len(read_decisions(path=self.path)), 2)


class ComponentLogTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "review_log.jsonl"
        case = Case(amputation_level="transfemoral", side="left", activity=ActivityProfile(k_level="K2"))
        self.record = CaseRecord(case=case, gaps=analyze_gaps(case, {}), components=component_support(case))

    def log(self, **judgements):
        return record_decision(self.record, "approve", path=self.path, statement_judgements=judgements)

    def statements(self, entry) -> dict[str, dict]:
        return {s["id"]: s for section in entry["components"]["sections"] for s in section["statements"]}

    def test_functional_level_logged(self):
        functional = self.log()["components"]["functional_level"]
        self.assertEqual((functional["lower_limb"], functional["k_level"]), (True, "K2"))
        self.assertEqual(functional["description"]["id"], "cms_k2_description")
        self.assertEqual(functional["description"]["citation"],
                         "Lower Limb Prosthetic Workgroup Consensus Document (2017), p. 5")
        self.assertEqual(len(functional["cautions"]), 2)

    def test_every_statement_shown_is_logged_with_its_words(self):
        entry = self.log(va_dod_ll_17_microprocessor_knee="relevant", cms_elevated_vacuum="not_relevant")
        logged = self.statements(entry)
        self.assertEqual(list(logged), [c.statement.id for c in self.record.components.statements])
        knee = logged["va_dod_ll_17_microprocessor_knee"]
        self.assertEqual((knee["component"], knee["grade"], knee["reviewer_judgement"]),
                         ("knee", "Weak for", "relevant"))
        self.assertTrue(knee["quote"].startswith("For prosthetic ambulators, we suggest prescribing"))
        self.assertTrue(knee["citation"].endswith("(2024), p. 56"))
        self.assertEqual(len(knee["context"]), 2)
        self.assertEqual(logged["cms_elevated_vacuum"]["reviewer_judgement"], "not_relevant")
        self.assertIsNone(logged["cms_k2_microprocessor_knee"]["grade"])
        self.assertIsNone(logged["cms_k2_microprocessor_knee"]["reviewer_judgement"])

    def test_statement_judgements_checked(self):
        for judgements in [{"made_up": "relevant"},
                           {"va_dod_ul_7_body_or_externally_powered": "relevant"},  # not shown here
                           {"cms_elevated_vacuum": "needed"}]:  # a gap's value, not a statement's
            with self.subTest(**judgements):
                with self.assertRaises(InvalidDecision):
                    self.log(**judgements)
        self.assertFalse(self.path.exists())

    def test_summary(self):
        entry = self.log(cms_elevated_vacuum="relevant")
        # 16 gaps: K-level is recorded here
        self.assertEqual(judgement_summary(entry),
                         f"16 not marked; components: 1 relevant, {len(self.statements(entry)) - 1} not marked")
        del entry["components"]  # as in entries logged before version 3
        self.assertEqual(judgement_summary(entry), "16 not marked")


class FittingLogTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "review_log.jsonl"
        case = Case(amputation_level="transtibial", side="left", comorbidities=[],
                    residual_limb=ResidualLimb(wound_status="open", skin_condition="graft"))
        self.record = CaseRecord(case=case, gaps=analyze_gaps(case, {}), components=component_support(case),
                                 fitting=fitting_support(case))

    def log(self, **judgements):
        return record_decision(self.record, "approve", path=self.path, statement_judgements=judgements)

    def statements(self, entry) -> dict[str, dict]:
        return {s["id"]: s for section in entry["fitting"]["sections"] for s in section["statements"]}

    def test_every_fitting_statement_logged_with_its_list(self):
        entry = self.log(icrc_ready_for_fitting="not_relevant", icrc_tt_foot_angle="relevant")
        logged = self.statements(entry)
        self.assertEqual(list(logged), [c.statement.id for c in self.record.fitting.statements])
        self.assertEqual([s["component"] for s in entry["fitting"]["sections"]],
                         ["readiness", "prosthesis_stage", "fitting", "alignment"])
        ready = logged["icrc_ready_for_fitting"]
        self.assertEqual((ready["quote"], ready["items"][:2]),
                         ("Those who are ready for fitting", ["Free of pain and infection;", "No oedema;"]))
        self.assertEqual(ready["source_type"], "professional_knowledge")
        self.assertTrue(ready["citation"].endswith("Reference Manual (2014), p. 49"))
        self.assertEqual(ready["reviewer_judgement"], "not_relevant")
        self.assertEqual(logged["icrc_tt_foot_angle"]["reviewer_judgement"], "relevant")
        self.assertNotIn("items", logged["icrc_tt_foot_angle"])  # a plain quote
        self.assertEqual(logged["va_dod_ll_5_rigid_dressing"]["grade"], "Weak for")

    def test_recorded_values_logged_as_stored(self):
        recorded = self.log()["fitting"]["recorded"]
        self.assertEqual(recorded["residual_limb.wound_status"], "open")
        self.assertEqual(recorded["residual_limb.skin_condition"], "graft")
        self.assertEqual(recorded["comorbidities"], [])  # asked, none reported
        self.assertIsNone(recorded["cognitive_status"])  # not recorded

    def test_component_and_fitting_marks_in_one_decision(self):
        entry = self.log(cms_elevated_vacuum="relevant", who_delivery_check="relevant")
        components = {s["id"]: s for section in entry["components"]["sections"] for s in section["statements"]}
        self.assertEqual(components["cms_elevated_vacuum"]["reviewer_judgement"], "relevant")
        self.assertEqual(self.statements(entry)["who_delivery_check"]["reviewer_judgement"], "relevant")
        self.assertIn("; design and fitting: 1 relevant, ", judgement_summary(entry))

    def test_statement_for_another_level_refused(self):
        with self.assertRaises(InvalidDecision):
            self.log(icrc_tf_knee_axis="relevant")  # transfemoral only
        self.assertFalse(self.path.exists())


if __name__ == "__main__":
    unittest.main()

"""Tests for shared/store.py: cases saved to disk and read back after a restart."""

import json
import tempfile
import unittest
from dataclasses import asdict
from pathlib import Path

from knowledge.models import ProtocolChunk
from reasoning.component_support import component_support
from reasoning.fitting_support import fitting_support
from reasoning.gap_analysis import analyze_gaps
from shared.case_schema import ActivityProfile, Case, PriorDevice, ResidualLimb
from shared.store import CASE_FILE_VERSION, CaseRecord, CaseStore

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


def make_record(**case_fields) -> CaseRecord:
    """A record as intake builds it."""
    case = Case(amputation_level="transfemoral", side="left", **case_fields)
    chunks = {"residual_limb.volume_stability": [VOLUME_PASSAGE]}
    return CaseRecord(case=case, retrieved_chunks=chunks, gaps=analyze_gaps(case, chunks),
                      components=component_support(case), fitting=fitting_support(case))


def statement_ids(record: CaseRecord) -> list[str]:
    return [cited.statement.id for cited in record.shown_statements()]


class PersistenceTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name) / "cases"  # made on the first save

    def test_case_survives_a_restart(self):
        record = make_record(
            age_years=61, etiology="vascular", comorbidities=["Diabetes"],
            residual_limb=ResidualLimb(wound_status="healing", pain="phantom pain at night"),
            activity=ActivityProfile(k_level="K2", functional_goals="walk to the mosque"),
            prior_devices=[PriorDevice("quadrilateral socket", years_used=3.5, currently_using=False)],
        )
        CaseStore(self.folder).save(record)

        loaded = CaseStore(self.folder).get(record.case.case_id)  # a new store: nothing in memory

        self.assertEqual(loaded.case.to_dict(), record.case.to_dict())
        self.assertEqual([asdict(g) for g in loaded.gaps], [asdict(g) for g in record.gaps])
        cited = next(g for g in loaded.gaps if g.evidence is not None)
        self.assertEqual(cited.evidence.citation, "Test Guideline (2024), p. 14")
        self.assertEqual({path: [asdict(c) for c in chunks] for path, chunks in loaded.retrieved_chunks.items()},
                         {path: [asdict(c) for c in chunks] for path, chunks in record.retrieved_chunks.items()})
        self.assertIsNone(loaded.knowledge_warning)
        # Component and fitting statements are worked out again from the case.
        self.assertEqual(statement_ids(loaded), statement_ids(record))
        self.assertEqual(loaded.components.functional.k_level, "K2")
        self.assertEqual(dict(loaded.fitting.recorded), dict(record.fitting.recorded))

    def test_warning_kept_when_the_library_was_not_searched(self):
        case = Case(amputation_level="transradial", side="right")
        record = CaseRecord(case=case, gaps=analyze_gaps(case, {}), knowledge_warning="not searched",
                            components=component_support(case), fitting=fitting_support(case))
        CaseStore(self.folder).save(record)
        loaded = CaseStore(self.folder).get(case.case_id)
        self.assertEqual(loaded.knowledge_warning, "not searched")
        self.assertEqual(loaded.retrieved_chunks, {})
        self.assertTrue(all(g.evidence is None for g in loaded.gaps))

    def test_one_json_file_per_case_named_by_its_id(self):
        record = make_record()
        CaseStore(self.folder).save(record)
        self.assertEqual([p.name for p in self.folder.iterdir()], [f"{record.case.case_id}.json"])
        data = json.loads((self.folder / f"{record.case.case_id}.json").read_text(encoding="utf-8"))
        self.assertEqual(data["case_file_version"], CASE_FILE_VERSION)
        self.assertEqual(set(data), {"case_file_version", "case", "knowledge_warning", "retrieved_chunks", "gaps"})
        self.assertEqual(set(data["case"]), set(record.case.to_dict()))  # only the case's own fields

    def test_saving_again_replaces_the_file(self):
        store = CaseStore(self.folder)
        record = make_record()
        store.save(record)
        record.knowledge_warning = "changed"
        store.save(record)
        self.assertEqual(len(list(self.folder.iterdir())), 1)  # no temporary file left
        self.assertEqual(CaseStore(self.folder).get(record.case.case_id).knowledge_warning, "changed")

    def test_unknown_and_unsafe_ids_not_found(self):
        CaseStore(self.folder).save(make_record())
        store = CaseStore(self.folder)
        for case_id in ("0123456789ab", "../cases", "a/b", "a.b", "", "x" * 65):
            with self.subTest(case_id=case_id):
                self.assertIsNone(store.get(case_id))

    def test_id_that_is_not_a_file_name_refused(self):
        record = make_record()
        record.case.case_id = "../outside"
        with self.assertRaises(ValueError):
            CaseStore(self.folder).save(record)
        self.assertFalse(self.folder.exists())

    def test_memory_only_store_writes_nothing(self):
        store = CaseStore(None)
        record = make_record()
        store.save(record)
        self.assertIs(store.get(record.case.case_id), record)
        self.assertFalse(self.folder.exists())


if __name__ == "__main__":
    unittest.main()

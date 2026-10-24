"""Tests for knowledge/catalog.py: loading and checking data/knowledge/sources/catalog.json."""

import csv
import json
import tempfile
import unittest
from pathlib import Path

from knowledge.catalog import DOMAINS, attributions, find_unlisted_files, load_catalog
from shared.config import CATALOG_PATH, RETRIEVAL_DOMAINS

MANIFEST_PATH = CATALOG_PATH.parent / "00_registry" / "sources_manifest.csv"


def make_entry(**changes) -> dict:
    entry = {
        "id": "test_doc_2024",
        "file": "01_guidelines/test_doc_2024.pdf",
        "title": "A test document",
        "authors": "Tester T",
        "year": 2024,
        "publisher": "Nobody",
        "doi": None,
        "url": None,
        "source_type": "protocol",
        "domains": ["prosthetics"],
        "language": "en",
    }
    entry.update(changes)
    return entry


class ProjectCatalogTests(unittest.TestCase):
    def test_project_catalog_is_valid(self):
        # data/knowledge/sources/catalog.json is in git, so this runs even without the PDFs.
        self.assertGreater(len(load_catalog(CATALOG_PATH)), 0)

    def test_licences_are_copied_from_the_manifest(self):
        # Copied as written, both ways: every catalog licence is the manifest's, and every Creative
        # Commons licence the manifest records for a catalogued file is in the catalog.
        with open(MANIFEST_PATH, encoding="utf-8-sig") as file:
            manifest = {row["filename"]: row["licence"].strip() for row in csv.DictReader(file)}
        for doc in load_catalog():
            recorded = manifest.get(Path(doc.file).name, "")
            with self.subTest(doc.id):
                if doc.licence:
                    self.assertEqual(doc.licence, recorded)
                self.assertEqual(bool(doc.licence), recorded.startswith("CC "))

    def test_attributions(self):
        credits = attributions()
        self.assertEqual(credits["scoliosis_sosort_guidelines_2016"], ("Negrini S, et al.", "CC BY 4.0"))
        self.assertEqual(credits["who_po_standards_part1_2017"][1], "CC BY-NC-SA 3.0 IGO")
        self.assertNotIn("lower_limb_amputation_va_dod_cpg_2024", credits)  # a US federal work: none recorded
        self.assertNotIn("prosthetic_gait_analysis_icrc_manual_2014", credits)  # "© ICRC", no licence

    def test_retrieval_domains_are_known(self):
        self.assertTrue(set(RETRIEVAL_DOMAINS) <= DOMAINS)


class LoadCatalogTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.sources = Path(tmp.name)

    def write_catalog(self, *entries) -> Path:
        path = self.sources / "catalog.json"
        path.write_text(json.dumps({"version": 1, "documents": list(entries)}), encoding="utf-8")
        return path

    def test_valid_entry_loads(self):
        [doc] = load_catalog(self.write_catalog(make_entry()))
        self.assertEqual(doc.id, "test_doc_2024")
        self.assertEqual(doc.domains, ["prosthetics"])

    def test_missing_catalog_gives_no_documents(self):
        self.assertEqual(load_catalog(self.sources / "no_catalog.json"), [])

    def test_bad_entries_rejected(self):
        bad = {
            "unknown domain": make_entry(domains=["cardiology"]),
            "no domains": make_entry(domains=[]),
            "unknown source type": make_entry(source_type="blog"),
            "unknown language": make_entry(language="fr"),
            "wrong file type": make_entry(file="01_guidelines/test_doc.docx"),
            "unknown limb": make_entry(limbs=["arm"]),
            "empty limbs": make_entry(limbs=[]),
            "misspelled field": {**make_entry(), "domian": ["prosthetics"]},
            "missing field": {k: v for k, v in make_entry().items() if k != "title"},
        }
        for name, entry in bad.items():
            with self.subTest(name), self.assertRaises(ValueError):
                load_catalog(self.write_catalog(entry))

    def test_repeated_id_rejected(self):
        path = self.write_catalog(make_entry(), make_entry(file="01_guidelines/other.pdf"))
        with self.assertRaises(ValueError):
            load_catalog(path)

    def test_unlisted_files_found(self):
        folder = self.sources / "01_guidelines"
        folder.mkdir()
        (folder / "test_doc_2024.pdf").write_bytes(b"")  # listed
        (folder / "forgotten.txt").write_text("x", encoding="utf-8")  # not listed
        (folder / "notes.docx").write_bytes(b"")  # not a source file type
        documents = load_catalog(self.write_catalog(make_entry()))
        self.assertEqual(find_unlisted_files(documents, self.sources), [folder / "forgotten.txt"])

    def test_skipped_folders_not_reported(self):
        datasets = self.sources / "05_datasets" / "gait"
        datasets.mkdir(parents=True)
        (datasets / "paper.pdf").write_bytes(b"")
        (datasets / "README.txt").write_text("x", encoding="utf-8")
        documents = load_catalog(self.write_catalog(make_entry()))
        self.assertEqual(len(find_unlisted_files(documents, self.sources)), 2)
        self.assertEqual(find_unlisted_files(documents, self.sources, ("05_datasets",)), [])

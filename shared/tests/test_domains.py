"""Tests for the folder layout's rule (CLAUDE.md, "Everything lives in its part's folder"): every clinical domain
is a package of the same shape, and shared code reaches a domain through shared/domains.py, never by naming it."""

import re
import unittest

from shared import domains
from shared.case_schema import DOMAIN_CASES
from shared.config import PROJECT_ROOT
from shared.dates import DateError, check_date
from shared.requirements import Priority, Requirement, next_requirement_id

# What each domain's modules must provide (shared/domains.py).
PARTS = {
    "case": (),
    "fields": ("FIELDS", "FIELDS_BY_PATH", "query_for"),
    "topics": ("topics_for_case", "PARTS", "SEARCH_DOMAINS", "PASSAGES_PER_DOCUMENT"),
    "rag": ("PROFILE", "components_from", "fitting_from"),
    "intake": ("bp",),
    "nav": ("MAP", "INTAKE", "MODULES", "LABELS", "DECIDES", "APPROVES", "CASE_BAR"),
}


class SameShapeTests(unittest.TestCase):
    def test_every_domain_has_every_part(self):
        for domain in domains.DOMAINS:
            for part, names in PARTS.items():
                with self.subTest(domain=domain, part=part):
                    module = domains.part(domain, part)
                    for name in names:
                        self.assertTrue(hasattr(module, name), f"{domain}/{part}.py has no {name}")

    def test_every_domain_registers_its_case(self):
        domains.load_cases()
        self.assertEqual(set(DOMAIN_CASES), set(domains.DOMAINS))

    def test_each_domains_pages_and_tests_live_in_its_folder(self):
        for domain in domains.DOMAINS:
            with self.subTest(domain):
                self.assertTrue((PROJECT_ROOT / domain / "templates" / domain).is_dir())
                self.assertTrue((PROJECT_ROOT / domain / "tests" / "__init__.py").is_file())
                case_bar = domains.part(domain, "nav").CASE_BAR
                self.assertTrue((PROJECT_ROOT / domain / "templates" / case_bar).is_file())

    def test_a_plan_is_optional_and_has_its_class(self):
        for domain in domains.DOMAINS:
            if domains.has_part(domain, "plan"):
                self.assertTrue(hasattr(domains.part(domain, "plan"), "PLAN"))
        self.assertFalse(domains.has_part("prosthetics", "plan"))  # not yet: plan Part 3

    def test_an_unknown_domain_is_refused(self):
        with self.assertRaisesRegex(ValueError, "domain must be one of"):
            domains.part("gait", "case")
        self.assertFalse(domains.has_part("gait", "case"))


class SharedCodeNamesNoDomainTests(unittest.TestCase):
    """Shared code asks shared/domains.py; it never checks a case's domain by name."""

    SHARED = ("shared", "knowledge", "reasoning")
    BY_NAME = re.compile(r"""domain\s*==\s*['"](%s)['"]""" % "|".join(domains.DOMAINS))

    def test_no_domain_checked_by_name_in_shared_code_or_the_shared_pages(self):
        files = [p for package in self.SHARED for p in (PROJECT_ROOT / package).rglob("*.py")
                 if "tests" not in p.parts and "__pycache__" not in p.parts]
        files += list((PROJECT_ROOT / "shared" / "templates").glob("*.html"))
        for path in files:
            with self.subTest(str(path.relative_to(PROJECT_ROOT))):
                self.assertIsNone(self.BY_NAME.search(path.read_text(encoding="utf-8")))


class SharedPiecesTests(unittest.TestCase):
    def test_requirements(self):
        self.assertIs(Requirement("R1", "clear the toes", priority="must").priority, Priority.MUST)
        self.assertIsNone(Requirement("R2", "x").priority)
        self.assertEqual(next_requirement_id([]), "R1")
        self.assertEqual(next_requirement_id([Requirement("R1", "a"), Requirement("R7", "b"), Requirement("X", "c")]),
                         "R8")

    def test_dates(self):
        self.assertEqual(check_date("2026-10-24"), "2026-10-24")
        self.assertIsNone(check_date(None))
        with self.assertRaises(DateError):
            check_date("24/10/2026")


if __name__ == "__main__":
    unittest.main()

"""Tests for reasoning/sentence_checks.py: flags on the AI's sentences (measurement only)."""

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from reasoning import sentence_checks as sc
from reasoning.rag import OK, Generation, Item, Part
from reasoning.rag_topics import COMPONENTS_PART

KNEE_QUOTE = ("For prosthetic ambulators, we suggest prescribing microprocessor knee units over "
              "non-microprocessor knee units.")
ARABIC_KNEE = "يقترح دليل VA/DoD للمرضى الذين يمشون بالطرف الاصطناعي ركبة بمعالج دقيق."


def kinds(quote: str, en: str, ar: str = ARABIC_KNEE) -> list[str]:
    return [flag.kind for flag in sc.flags(quote, en, ar)]


class FaithfulTests(unittest.TestCase):
    def test_a_faithful_attributed_sentence_is_not_flagged(self):
        en = "The VA/DoD guideline suggests microprocessor knee units over non-microprocessor knees for prosthetic ambulators."
        self.assertEqual(sc.flags(KNEE_QUOTE, en, ARABIC_KNEE), [])

    def test_years_and_synonyms_are_not_flagged(self):
        quote = "TT sockets should be checked for fit at each visit with a minimum of 5 cm clearance."
        en = "The ICRC manual (2014) says transtibial sockets should be checked at each visit, with 5 cm clearance."
        ar = "يذكر دليل ICRC أن التجويف يُفحص في كل زيارة مع خلوص ٥ سم."
        self.assertNotIn(sc.LEVEL_NOT_IN_QUOTE, kinds(quote, en, ar))
        self.assertNotIn(sc.NUMBER_NOT_IN_QUOTE, kinds(quote, en, ar))  # 2014 is a year
        self.assertNotIn(sc.NUMBERS_DIFFER_AR, kinds(quote, en, ar))  # ٥ is 5


class SlipTests(unittest.TestCase):
    def test_a_number_the_quote_does_not_have(self):
        found = sc.flags(KNEE_QUOTE, "The VA/DoD guideline says microprocessor knees cut falls by 80%.", "خفض ٨٠٪")
        self.assertIn(sc.Flag(sc.NUMBER_NOT_IN_QUOTE, "80"), found)

    def test_arabic_numbers_must_match_the_english(self):
        quote = "Limit wear time if redness does not resolve in 15-20 min."
        en = "The VA/DoD tool says to limit wear time if redness does not resolve in 15-20 minutes."
        self.assertIn(sc.NUMBERS_DIFFER_AR, kinds(quote, en, "قلّل مدة الارتداء إذا لم يزل الاحمرار خلال ١٥-٣٠ دقيقة."))
        self.assertNotIn(sc.NUMBERS_DIFFER_AR, kinds(quote, en, "قلّل مدة الارتداء إذا لم يزل الاحمرار خلال ١٥-٢٠ دقيقة."))

    def test_codes(self):
        en = "The CMS document describes K3 users as community ambulators."
        found = sc.flags("Level 3: Has the ability or potential for ambulation with variable cadence.", en,
                         "تصف وثيقة CMS مستخدمي K2 بأنهم يمشون في المجتمع.")
        self.assertIn(sc.Flag(sc.CODE_NOT_IN_QUOTE, "K3"), found)
        self.assertIn(sc.CODES_DIFFER_AR, [flag.kind for flag in found])
        self.assertNotIn(sc.CODE_NOT_IN_QUOTE, kinds("K3 users ambulate with variable cadence.", en, "K3"))

    def test_a_level_the_quote_does_not_name(self):
        found = sc.flags(KNEE_QUOTE, "For transfemoral amputees the guideline suggests microprocessor knees.",
                         ARABIC_KNEE)
        self.assertIn(sc.Flag(sc.LEVEL_NOT_IN_QUOTE, "transfemoral"), found)

    def test_negation_dropped_or_added(self):
        quote = "There is insufficient evidence to recommend for or against any specific socket; it is not established."
        self.assertIn(sc.NEGATION_DIFFERS, kinds(quote, "The guideline recommends a specific socket design."))
        self.assertNotIn(sc.NEGATION_DIFFERS, kinds(quote, "The guideline says no socket design is established."))
        self.assertIn(sc.NEGATION_DIFFERS, kinds(KNEE_QUOTE, "The guideline does not suggest microprocessor knees."))


class AdviceTests(unittest.TestCase):
    def test_advice_in_the_sentences_own_voice(self):
        for en, name in [("The patient should use a microprocessor knee.", "directive"),
                         ("A microprocessor knee is the best choice here.", "choice or ranking"),
                         ("This patient is ready for fitting.", "readiness verdict"),
                         ("We recommend a microprocessor knee.", "own recommendation")]:
            with self.subTest(en):
                details = [flag.detail for flag in sc.flags(KNEE_QUOTE, en, ARABIC_KNEE) if flag.kind == sc.ADVICE]
                self.assertTrue(any(d.startswith(name) for d in details), details)

    def test_a_sources_own_should_is_marked_as_in_the_quote(self):
        quote = "the K level classification should not be considered a functional classification"
        [flag] = [f for f in sc.flags(quote, "The CMS document says the K level classification should not be "
                                      "considered a functional classification.", "تقول وثيقة CMS ...") if f.kind == sc.ADVICE]
        self.assertEqual(flag.detail, "directive: 'should' (also in the quote)")

    def test_arabic_advice(self):
        self.assertIn(sc.ADVICE_AR, kinds(KNEE_QUOTE, "x", "يجب أن يستخدم المريض ركبة بمعالج دقيق."))
        self.assertIn(sc.ADVICE_AR, kinds(KNEE_QUOTE, "x", "المريض جاهز للتركيب."))
        self.assertNotIn(sc.ADVICE_AR, kinds(KNEE_QUOTE, "x", "يذكر الدليل معايير الجاهزية للتركيب."))


class StoredCaseTests(unittest.TestCase):
    def test_flags_over_a_stored_case_file(self):
        item = Item("rag-knee-0000000000", "knee", "doc-0001", "doc", KNEE_QUOTE, 56, 56,
                    "The patient should use a microprocessor knee.", ARABIC_KNEE)
        generation = Generation("rag-v2", "fake-model", "medium",
                                {COMPONENTS_PART: Part(COMPONENTS_PART, OK, items=[item])})
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "case-1.json"
            path.write_text(json.dumps({"case": {"case_id": "case-1"}, "generation": generation.to_dict()}),
                            encoding="utf-8")
            (Path(folder) / "old.json").write_text(json.dumps({"case": {"case_id": "old"}, "generation": None}),
                                                   encoding="utf-8")
            self.assertEqual([(case, i.id) for case, i in sc.stored_items(path)], [("case-1", item.id)])
            out = io.StringIO()
            with redirect_stdout(out):
                sc.main([str(path), str(Path(folder) / "old.json")])
        self.assertIn("case-1  rag-knee-0000000000  advice wording: directive: 'should'", out.getvalue())
        self.assertIn("2 case file(s), 1 kept AI item(s), 1 flagged (measurement only", out.getvalue())


if __name__ == "__main__":
    unittest.main()

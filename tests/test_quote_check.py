"""Tests for reasoning/quote_check.py: a quote is shown only if it is word for word in its passage."""

import tempfile
import unittest
from pathlib import Path

from reasoning.quote_check import QuoteRefused, find_quote, grade_after, locate_pages

PASSAGE = ("Recommendation 17. For prosthetic ambulators, we suggest prescribing microprocessor knee\n"
           "units over non-microprocessor knee units. Weak for Reviewed, New-added\n"
           "The patient’s “goals” matter – see Table 5.")


class FindQuoteTests(unittest.TestCase):
    def test_exact_quote_found(self):
        quote = "For prosthetic ambulators, we suggest prescribing microprocessor knee units"
        self.assertEqual(find_quote(quote, PASSAGE), quote)

    def test_line_breaks_and_spaces_count_as_one_space(self):
        self.assertEqual(find_quote("we suggest   prescribing microprocessor knee \n units over", PASSAGE),
                         "we suggest prescribing microprocessor knee units over")

    def test_quotation_marks_and_dashes_compared_as_they_print_shown_as_the_passage_has_them(self):
        shown = find_quote('The patient\'s "goals" matter - see Table 5.', PASSAGE)
        self.assertEqual(shown, "The patient’s “goals” matter – see Table 5.")  # the passage's own characters

    def test_quotation_marks_around_the_quote_are_not_part_of_it(self):
        self.assertEqual(find_quote('"we suggest prescribing microprocessor knee units"', PASSAGE),
                         "we suggest prescribing microprocessor knee units")

    def test_one_changed_word_is_refused(self):
        for quote in ("we recommend prescribing microprocessor knee units",  # suggest -> recommend
                      "we suggest prescribing microprocessor knees units",
                      "For prosthetic ambulators we suggest prescribing",  # a comma left out
                      "we suggest prescribing ... knee units over"):  # text left out
            with self.subTest(quote), self.assertRaisesRegex(QuoteRefused, "not found word for word"):
                find_quote(quote, PASSAGE)

    def test_too_short_is_refused(self):
        with self.assertRaisesRegex(QuoteRefused, "shorter than 5 words"):
            find_quote("microprocessor knee units", PASSAGE)
        self.assertEqual(find_quote("microprocessor knee units", PASSAGE, min_words=3), "microprocessor knee units")

    def test_arabic_and_compatibility_characters(self):
        arabic = "يجب أن يكون الطرف المتبقي خالياً من الألم والالتهاب قبل التركيب."
        self.assertEqual(find_quote("الطرف المتبقي خالياً من الألم والالتهاب", arabic),
                         "الطرف المتبقي خالياً من الألم والالتهاب")
        # The extracted text is NFKC-normalised: a ligature in the model's copy still matches.
        self.assertEqual(find_quote("ﬁt the socket to the residual limb", "First fit the socket to the residual limb."),
                         "fit the socket to the residual limb")


class GradeTests(unittest.TestCase):
    QUOTE = "For prosthetic ambulators, we suggest prescribing microprocessor knee units over non-microprocessor knee units."

    def test_grade_printed_after_the_quote(self):
        self.assertTrue(grade_after("Weak for", self.QUOTE, PASSAGE))

    def test_grade_not_after_the_quote(self):
        self.assertFalse(grade_after("Strong for", self.QUOTE, PASSAGE))  # not printed at all
        self.assertFalse(grade_after("Weak for", "Weak for Reviewed, New-added", PASSAGE))  # only before
        far = self.QUOTE + " " + "x " * 200 + "Weak for"
        self.assertFalse(grade_after("Weak for", self.QUOTE, far))  # too far after to belong to it


class LocatePagesTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        (self.folder / "doc_2024.txt").write_text(
            "# header\n\n--- page 4 ---\nIntroduction text.\n\n--- page 5 ---\nThe socket must fit\nwell. "
            "Alignment follows the\n\n--- page 6 ---\nfitting of the socket.\n", encoding="utf-8")

    def test_the_page_the_quote_is_on(self):
        self.assertEqual(locate_pages("The socket must fit well.", "doc_2024", 4, 6, self.folder), (5, None))

    def test_a_quote_across_a_page_break(self):
        self.assertEqual(locate_pages("Alignment follows the fitting of the socket.", "doc_2024", 4, 6, self.folder),
                         (5, 6))

    def test_not_found_or_no_text_the_passage_pages(self):
        self.assertEqual(locate_pages("Words that are nowhere.", "doc_2024", 4, 6, self.folder), (4, 6))
        self.assertEqual(locate_pages("The socket must fit well.", "missing_doc", 7, 7, self.folder), (7, None))


if __name__ == "__main__":
    unittest.main()

"""Tests for shared/arabic_terms.py: the term sheet export and applying corrections back."""

import csv
import importlib.util
import io
import re
import shutil
import tempfile
import unittest
from pathlib import Path

from shared import arabic_terms, i18n
from shared.arabic_terms import CHOICE_PREFIX, COLUMNS, FIELD_PREFIX, apply, export, read_sheet
from shared.field_guide import FIELDS_BY_PATH

# Corrections used in the round trip: a one-line text, the disclaimer (several
# string pieces in the source), a text with a {placeholder}, a field name, a choice.
CORRECTIONS = {
    "review.approve": "موافقة",
    "disclaimer": "نص تجريبي بديل لإخلاء المسؤولية.",
    "intake.device": "الطرف السابق {n}",
    FIELD_PREFIX + "residual_limb.pain": "ألم الجذع والألم الشبحي",
    CHOICE_PREFIX + "AmputationLevel.transtibial": "بتر أسفل الركبة",
}


def load_module(path: Path):
    """shared/i18n.py as written to `path`, imported on its own."""
    spec = importlib.util.spec_from_file_location("i18n_corrected", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ExportTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.sheet = Path(tmp.name) / "trial" / "arabic_terms.csv"

    def test_every_interface_text_exported(self):
        self.assertEqual(export(self.sheet), len(read_sheet(self.sheet)))
        rows = {row["key"]: row for row in read_sheet(self.sheet)}
        expected = set(i18n.TEXT)
        expected |= {FIELD_PREFIX + path for path in i18n.FIELD_LABELS["ar"]}
        expected |= {f"{CHOICE_PREFIX}{enum}.{value}"
                     for enum, choices in i18n.VALUE_LABELS["ar"].items() for value in choices}
        self.assertEqual(set(rows), expected)
        self.assertEqual(rows["review.approve"]["English"], "Approve")
        self.assertEqual(rows["review.approve"]["Arabic"], "اعتماد")
        self.assertEqual(rows[FIELD_PREFIX + "residual_limb.pain"]["English"],
                         FIELDS_BY_PATH["residual_limb.pain"].label)
        self.assertEqual(rows[CHOICE_PREFIX + "Side.bilateral"]["English"], "bilateral")
        for row in rows.values():
            with self.subTest(row["key"]):
                self.assertEqual((row["corrected Arabic"], row["comment"]), ("", ""))  # for the reviewer
                self.assertNotEqual(row["where it appears"], "(not found)")

    def test_where_it_appears(self):
        export(self.sheet)
        rows = {row["key"]: row["where it appears"] for row in read_sheet(self.sheet)}
        self.assertEqual(rows["component.knee"], "review/templates/review.html")  # built: 'component.' ~ key
        self.assertEqual(rows["error.required.side"], "intake/routes.py")  # built: f"error.required.{name}"
        self.assertEqual(rows["intake.age"], "intake/routes.py; intake/templates/intake_form.html")
        self.assertIn("reasoning/gap_analysis.py", rows[FIELD_PREFIX + "residual_limb.pain"])
        self.assertIn("intake/templates/intake_form.html", rows[CHOICE_PREFIX + "Side.left"])

    def test_columns_and_bom_for_excel(self):
        export(self.sheet)
        self.assertTrue(self.sheet.read_bytes().startswith(b"\xef\xbb\xbf"))
        with self.sheet.open(encoding="utf-8-sig", newline="") as f:
            self.assertEqual(next(csv.reader(f)), list(COLUMNS))

    def test_filled_sheet_never_overwritten(self):
        export(self.sheet)
        rows = read_sheet(self.sheet)
        rows[0]["comment"] = "check this term"
        write_sheet(self.sheet, rows)
        with self.assertRaises(FileExistsError):
            export(self.sheet)
        self.assertEqual(read_sheet(self.sheet)[0]["comment"], "check this term")
        export(self.sheet, force=True)
        self.assertEqual(read_sheet(self.sheet)[0]["comment"], "")


def write_sheet(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8-sig", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


class ApplyTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.i18n_copy = self.folder / "i18n.py"
        shutil.copy(arabic_terms.I18N_PATH, self.i18n_copy)
        self.original = self.i18n_copy.read_text(encoding="utf-8")
        self.sheet = self.folder / "arabic_terms.csv"
        export(self.sheet)

    def fill(self, corrections=None, comments=None, arabic=None):
        rows = read_sheet(self.sheet)
        for row in rows:
            row["corrected Arabic"] = (corrections or {}).get(row["key"], "")
            row["comment"] = (comments or {}).get(row["key"], "")
            row["Arabic"] = (arabic or {}).get(row["key"], row["Arabic"])
        write_sheet(self.sheet, rows)

    def apply(self, answer=True):
        out = io.StringIO()
        changed = apply(self.sheet, self.i18n_copy, confirm=lambda question: answer, out=out)
        return changed, out.getvalue()

    def test_round_trip_changes_only_the_corrected_texts(self):
        self.fill(CORRECTIONS)
        changed, output = self.apply()
        self.assertEqual(changed, len(CORRECTIONS))
        corrected = load_module(self.i18n_copy)
        for key, texts in i18n.TEXT.items():
            with self.subTest(key):
                self.assertEqual(corrected.TEXT[key]["en"], texts["en"])
                self.assertEqual(corrected.TEXT[key]["ar"], CORRECTIONS.get(key, texts["ar"]))
        for path, label in i18n.FIELD_LABELS["ar"].items():
            self.assertEqual(corrected.FIELD_LABELS["ar"][path], CORRECTIONS.get(FIELD_PREFIX + path, label))
        for enum, choices in i18n.VALUE_LABELS["ar"].items():
            for value, label in choices.items():
                self.assertEqual(corrected.VALUE_LABELS["ar"][enum][value],
                                 CORRECTIONS.get(f"{CHOICE_PREFIX}{enum}.{value}", label))
        self.assertEqual(corrected.t("intake.device", "ar", n=2), "الطرف السابق \u20682\u2069")
        # The rest of the file, comments and layout included, is unchanged.
        new = self.i18n_copy.read_text(encoding="utf-8")
        removed = set(self.original.splitlines()) - set(new.splitlines())
        self.assertTrue(all(re.search("[؀-ۿ]", line) for line in removed), removed)  # Arabic lines only
        self.assertLessEqual(len(removed), 12)  # the disclaimer spans 7 lines, the others 1 each
        self.assertIn("# The Arabic names of the intake fields that can be gaps", new)
        self.assertIn('+    "review.approve": {"en": "Approve", "ar": "موافقة"},', output)  # the diff

    def test_nothing_written_without_a_yes(self):
        self.fill({"review.approve": "موافقة"})
        changed, output = self.apply(answer=False)
        self.assertIsNone(changed)
        self.assertIn('-    "review.approve": {"en": "Approve", "ar": "اعتماد"},', output)
        self.assertIn("Nothing written.", output)
        self.assertEqual(self.i18n_copy.read_text(encoding="utf-8"), self.original)

    def test_unsafe_rows_stop_the_whole_sheet(self):
        self.fill({"review.approve": "موافقة",  # fine on its own
                   "review.edit": "تحرير {x}",  # a placeholder the English doesn't have
                   "review.reject": "رفض {",  # a broken brace
                   "review.not_marked": "دون تحديد"},
                  arabic={"review.not_marked": "نص قديم"})  # Arabic changed since the export
        rows = read_sheet(self.sheet)
        rows.append({"key": "review.made_up", "corrected Arabic": "نص", "English": "", "Arabic": "",
                     "where it appears": "", "comment": ""})
        write_sheet(self.sheet, rows)
        changed, output = self.apply()
        self.assertIsNone(changed)
        self.assertIn("Nothing written. Fix these rows first:", output)
        self.assertIn("(review.edit): {x} is not in the English text", output)
        self.assertIn("(review.reject): a { or } doesn't form a placeholder", output)
        self.assertIn("(review.not_marked): the Arabic in shared/i18n.py changed", output)
        self.assertIn("unknown key 'review.made_up'", output)
        self.assertEqual(self.i18n_copy.read_text(encoding="utf-8"), self.original)

    def test_a_placeholder_may_be_left_out(self):
        self.fill({"intake.device": "جهاز سابق"})  # leaves out {n}: allowed, like the existing tests
        changed, _ = self.apply()
        self.assertEqual(changed, 1)
        self.assertEqual(load_module(self.i18n_copy).TEXT["intake.device"]["ar"], "جهاز سابق")

    def test_comments_are_listed_and_change_nothing(self):
        self.fill(comments={"fitting_section.alignment": "المحاذاة مقبولة، أو: ضبط الاصطفاف"})
        changed, output = self.apply()
        self.assertIsNone(changed)
        self.assertIn("fitting_section.alignment: المحاذاة مقبولة، أو: ضبط الاصطفاف", output)
        self.assertIn("No corrected Arabic in the sheet; nothing to change.", output)
        self.assertEqual(self.i18n_copy.read_text(encoding="utf-8"), self.original)

    def test_correction_equal_to_the_current_text_is_no_change(self):
        self.fill({"review.approve": "اعتماد"})
        changed, output = self.apply()
        self.assertIsNone(changed)
        self.assertIn("nothing to change", output)


if __name__ == "__main__":
    unittest.main()

"""Tests for the intake forms' shared parsers (shared/forms.py)."""

import unittest

from shared.forms import optional_list


class OptionalListTests(unittest.TestCase):
    def test_blank_is_not_recorded(self):
        for raw in (None, "", "  \r\n  \n"):
            self.assertIsNone(optional_list(raw))

    def test_none_means_asked_none_reported(self):
        self.assertEqual(optional_list("none"), [])
        self.assertEqual(optional_list("\n None \n"), [])
        self.assertEqual(optional_list("لا يوجد"), [])  # what the Arabic form says to type
        self.assertEqual(optional_list(" لا شيء "), [])

    def test_one_item_per_line(self):
        self.assertEqual(
            optional_list("Diabetes\r\n\r\n  Hypertension  \r\n"),
            ["Diabetes", "Hypertension"],
        )

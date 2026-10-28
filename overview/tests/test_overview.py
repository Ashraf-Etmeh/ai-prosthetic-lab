"""Tests for the system map (overview/; plan Part 11, docs/design/01-system-map/)."""

from flask import url_for

from gait import rules as gait_rules
from knowledge.clinic_rules import load_rules
from overview import nav as overview_nav
from overview.routes import waiting_for_owner
from prosthetics.tests.helpers import ProstheticRouteTestCase
from quality.releases import load_releases
from record import governance
from shared import domains
from shared.testing import visible_text


class SystemMapTests(ProstheticRouteTestCase):
    def test_home_is_the_system_map(self):
        resp = self.client.get("/")
        self.assertEqual(resp.status_code, 200)
        page = resp.get_data(as_text=True)
        text = visible_text(page)
        self.assertIn("The whole system, part by part", text)
        with self.app.test_request_context():
            for name in (*domains.DOMAINS, *domains.SHARED_PARTS):  # every part, opened from its card
                with self.subTest(name):
                    self.assertIn(f'href="{url_for(domains.nav(name).MAP)}"', page)
        for label in ("1 Capture", "4 Team record", "2 Case-based learning", "1 Record and follow-up"):
            self.assertIn(label, text)  # each part's own tabs, from its nav.py
        self.assertIn('lang="ar" dir="rtl">الأطراف الاصطناعية', page)  # each part's Arabic name under its English one

    def test_use_cases_each_link_to_their_part(self):
        page = self.client.get("/").get_data(as_text=True)
        self.assertEqual(len(overview_nav.USE_CASES), 7)
        with self.app.test_request_context():
            for number, name in overview_nav.USE_CASES:
                with self.subTest(number):
                    self.assertIn(f'<b>{number}</b>', page)
                    self.assertIn(f'href="{url_for(domains.nav(name).MAP)}"', page)

    def test_waiting_for_the_owner_is_counted_from_the_files(self):
        counts = {w.key: (w.drafts, w.total) for w in waiting_for_owner()}
        rules = load_rules()
        self.assertEqual(counts["clinic_rules"], (sum(1 for r in rules if not r.approved), len(rules)))
        thresholds = gait_rules.load_thresholds()
        self.assertEqual(counts["gait_thresholds"], (sum(1 for t in thresholds if not t.approved), len(thresholds)))
        self.assertEqual(counts["roles"][1], len(governance.load_roles()))
        self.assertEqual(counts["releases"], (0 if load_releases() else 1, 1))
        text = visible_text(self.client.get("/").get_data(as_text=True))
        self.assertIn(f"{counts['gait_thresholds'][0]} of {counts['gait_thresholds'][1]} drafts", text)
        self.assertIn("Cloud model for Orthotics", text)

    def test_header_brand_goes_home_and_the_map_is_not_a_part_to_switch_to(self):
        page = self.client.get("/intake").get_data(as_text=True)
        self.assertIn('<a class="ui-brand" href="/"', page)
        self.assertNotIn(">System map<", page)  # not in the switch between the parts
        home = self.client.get("/").get_data(as_text=True)
        self.assertIn('href="/architecture"', home)  # its own tabs
        self.assertIn('aria-current="page">1 System map', home)

    def test_architecture_reads_the_settings(self):
        page = visible_text(self.client.get("/architecture").get_data(as_text=True))
        self.assertIn("Architecture and data flow", page)
        self.assertIn(governance.provider(), page)
        for use in governance.cloud_uses():
            self.assertIn(("on" if use.on else "off"), page)
        self.assertIn("The shaded step is the only one outside this machine", page)

    def test_both_pages_in_arabic(self):
        self.client.set_cookie("lang", "ar")
        self.assertIn("النظام كاملاً، جزءاً جزءاً", self.client.get("/").get_data(as_text=True))
        self.assertIn("البنية وتدفق البيانات", self.client.get("/architecture").get_data(as_text=True))
        self.client.delete_cookie("lang")

"""Tests for every page's shared header and look (shared/templates/ui_*.html, 2026-10-23), on the prosthetic pages.

The prosthetic pages got the orthotic pages' design: the domain switch, the
domain's modules, the case bar. The prosthetic modules are the review page's
sections, so the header links to them; the prosthetics map names the brief's
capabilities.
"""

from prosthetics.tests.helpers import ProstheticRouteTestCase
from shared.testing import visible_text


class ProstheticHeaderTests(ProstheticRouteTestCase):
    def test_the_map_names_the_briefs_capabilities(self):
        page = visible_text(self.client.get("/prosthetics").get_data(as_text=True))
        for name in ("تقييم حالات البتر", "تحليل المتطلبات الوظيفية", "دعم اختيار المكونات",
                     "دعم قرارات التصميم والتركيب", "المتابعة والتقييم"):
            self.assertIn(name, page)
        self.assertIn("Prosthetics: the modules", page)
        self.assertIn("Not built yet", page)
        self.client.set_cookie("lang", "ar")
        self.assertIn("الأطراف الاصطناعية: الوحدات", visible_text(self.client.get("/prosthetics").get_data(as_text=True)))

    def test_the_header_names_the_part_and_switches_language_en_or_arabic(self):
        # SYSTEM_DESIGN.md §5: the brand and the part's name, the modules as numbered tabs, an EN | العربية switch.
        page = self.client.get("/prosthetics").get_data(as_text=True)
        self.assertIn('<span class="ui-part">/ Prosthetics</span>', page)
        self.assertIn('<span aria-current="true" lang="en">EN</span>', page)  # the current language
        self.assertIn('<a href="/language/ar?next=/prosthetics" lang="ar">العربية</a>', page)
        self.client.set_cookie("lang", "ar")
        page = self.client.get("/orthotics").get_data(as_text=True)
        self.assertIn('<span class="ui-part">/ تقويم العظام</span>', page)
        self.assertIn('<span aria-current="true" lang="ar">العربية</span>', page)
        self.assertIn('<a href="/language/en?next=/orthotics" lang="en">EN</a>', page)

    def test_on_the_intake_form_the_language_button_posts_the_form(self):
        page = self.client.get("/intake").get_data(as_text=True)
        self.assertIn('class="ui-page"', page)
        self.assertIn('href="/intake" aria-current="page">1 Evaluate', page)
        # The header's switch posts the form, so it comes back filled in (a link would lose what was typed).
        self.assertIn('<button type="submit" form="intake-form" name="switch_language" value="ar" formnovalidate '
                      'lang="ar">العربية</button>', page)
        self.assertNotIn('href="/language/', page)

    def test_the_review_page_links_its_sections(self):
        location = self.post_intake(**{"k_level": "K3"}).headers["Location"]
        page = self.client.get(location).get_data(as_text=True)
        for anchor in ("gaps", "functional", "components", "fitting"):
            with self.subTest(anchor):
                self.assertIn(f'id="{anchor}"', page)
                self.assertIn(f'href="{location}#{anchor}"', page)
        text = visible_text(page)
        self.assertIn("transtibial · left side · recorded K3", text)  # the case bar
        self.assertIn("Decision support: the specialist decides", text)
        self.client.set_cookie("lang", "ar")
        text = visible_text(self.client.get(location).get_data(as_text=True))
        self.assertIn("الجانب: أيسر", text)
        self.assertIn("دعم القرار: المختص هو من يقرر", text)

    def test_the_domain_switch_on_both_maps(self):
        for path, current in (("/prosthetics", "Prosthetics"), ("/orthotics", "Orthotics")):
            with self.subTest(path):
                page = self.client.get(path).get_data(as_text=True)
                self.assertIn(f'aria-current="true">{current}', page)
                self.assertIn('href="/prosthetics"', page)
                self.assertIn('href="/orthotics"', page)

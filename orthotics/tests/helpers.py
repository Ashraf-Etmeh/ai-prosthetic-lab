"""The orthotic page tests' set-up: a fake stroke case entered through the form, the search replaced by fixed
passages (no embedding model), the AI writer the tests' fake, and a page helper."""

from unittest.mock import patch

from orthotics.tests.test_orthotics import orthotic_retrieval, passage
from shared.store import store
from shared.testing import RouteTestCase, visible_text

STRAPS_PASSAGE = passage("afo_manufacturing_icrc_2010-0009", "Preparation of the straps: for the proximal strap, ...",
                         page=9)


def fake_passages(items):
    """Stands in for orthotics.sources.find_passages: one passage for straps, none for anything else."""
    return {key: ([STRAPS_PASSAGE] if key == "part.straps" else []) for key in items}


class OrthoticPageTestCase(RouteTestCase):
    """A fake stroke case (left side, toe drag, -5° with the knee extended, one requirement written at intake)."""

    fake_retrieval = staticmethod(orthotic_retrieval)
    intake = {"condition": "stroke", "side": "left", "months_since_onset": "7", "deviation": ["toe_drag"],
              "df_knee_ext": "-5", "requirements": "clear the toes in swing", "footwear": "trainers"}

    def setUp(self):
        super().setUp()
        replaced = patch("orthotics.modules.find_passages", side_effect=fake_passages)
        replaced.start()
        self.addCleanup(replaced.stop)
        resp = self.client.post("/intake/orthotics", data=self.intake)
        self.assertEqual(resp.status_code, 302)
        self.case_id = store.all()[-1].case.case_id
        self.writer_calls = len(self.writer.calls)

    def url(self, page):
        return f"/orthotics/{self.case_id}/{page}"

    def page(self, url, lang="en"):
        """What a reader sees on the page (status 200 checked)."""
        self.client.set_cookie("lang", lang)
        resp = self.client.get(url)
        self.assertEqual(resp.status_code, 200)
        return visible_text(resp.get_data(as_text=True))

    def post(self, page, lang="en", **data):
        self.client.set_cookie("lang", lang)
        return self.client.post(self.url(page), data=data)

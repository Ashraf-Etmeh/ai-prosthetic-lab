"""Tests for gait analysis (gait/; plan Part 10, SYSTEM_DESIGN.md §6.3).

Cases, logs and people go to temporary folders (shared/testing.py RouteTestCase); no model is loaded.
"""

import io
import json
import tempfile
import unittest
from pathlib import Path

from gait import rules
from gait.session import (
    CURVES,
    MEASURES,
    Comparison,
    GaitError,
    GaitRecord,
    Quality,
    Review,
    Session,
    read_table,
    table_template,
)
from prosthetics.case import Case
from prosthetics.plan import AlignmentVersion, ProstheticPlan
from prosthetics.tests.helpers import ProstheticRouteTestCase
from record import people
from record.timeline import record_view
from shared.config import EXTRACTED_DIR
from shared.store import CaseRecord, store
from shared.testing import visible_text

TABLE = """measure,left,right,both
walking_speed,,,"0,92"
step_length,0.58,0.49,
stance,58,66,
stride_time_cv,,,6
knee_flexion,"2 6 12 15 12 8 10 25 45 60 35 3","3 8 15 18 14 9 12 30 50 62 30 2",
"""


def session(**changes) -> Session:
    values = {"on": "2026-10-15", "source": "wearable", "walkway": "10 m", "pace": "comfortable",
              "values": {"stance": {"left": 58, "right": 66}, "step_length": {"left": 0.58, "right": 0.49},
                         "walking_speed": {"both": 0.92}}}
    values.update(changes)
    return Session(changes.pop("id", "G1"), **{k: v for k, v in values.items() if k != "id"})


class SessionTests(unittest.TestCase):
    def test_round_trip(self):
        record = GaitRecord(sessions=[session(), session(id="G2", source="phone_video", filming_consent=True,
                                                         quality=Quality(60, 6, 6, 14, 2, "left", "found"),
                                                         curves={"knee_flexion": {"left": [0, 10, 60, 2]}},
                                                         reviews=[Review("stance_sides", "reviewed", None, "x")])],
                            comparisons=[Comparison("G1", "G2", "device_setting", "2026-10-27T10:00:00+00:00")])
        again = GaitRecord.from_dict(json.loads(json.dumps(record.to_dict())))
        self.assertEqual(again.to_dict(), record.to_dict())
        self.assertEqual(again.next_id(), "G3")
        self.assertEqual(GaitRecord.from_dict({}).to_dict(), GaitRecord().to_dict())

    def test_what_a_session_refuses(self):
        for changes in ({"source": "phone_video"},  # filmed, no consent
                        {"source": "lab_3d", "filming_consent": False},
                        {"values": {"stance": {"both": 60}}},  # per side
                        {"values": {"walking_speed": {"left": 1.0}}},
                        {"values": {"shoe_size": {"both": 42}}},
                        {"quality": {"trials": 3, "trials_whole_body": 4}},
                        {"curves": {"hip_flexion": {"left": [1, 2]}}}):
            with self.subTest(changes):
                with self.assertRaises(GaitError):
                    session(**changes)
        with self.assertRaises(GaitError):
            Review("stance_sides", "dismissed", None, "x")  # dismissing needs a reason
        with self.assertRaises(GaitError):
            GaitRecord(sessions=[session()], comparisons=[Comparison("G1", "G9", "with_without", "x")])
        self.assertIsNone(session(source="wearable").filming_consent)  # not filmed: not asked

    def test_reading_the_capture_systems_table(self):
        values, curves = read_table("﻿" + TABLE)
        self.assertEqual(values["walking_speed"], {"both": 0.92})  # a comma decimal read as a point
        self.assertEqual(values["stance"], {"left": 58, "right": 66})
        self.assertEqual(len(curves["knee_flexion"]["left"]), 12)
        for bad in ("measure,value\nwalking_speed,1\n",  # columns
                    "measure,left,right,both\nshoe_size,,,42\n",
                    "measure,left,right,both\nstance,,,60\n",  # per side
                    "measure,left,right,both\nwalking_speed,,,fast\n",
                    "measure,left,right,both\nknee_flexion,5,,\n"):  # one point is no curve
            with self.subTest(bad):
                with self.assertRaises(GaitError):
                    read_table(bad)
        template = table_template().splitlines()
        self.assertEqual(template[0], "measure,left,right,both")
        self.assertEqual([line.split(",")[0] for line in template[1:]], [*MEASURES, *CURVES])


class RulesTests(unittest.TestCase):
    def write(self, text: str) -> Path:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
        tmp.write(text)
        tmp.close()
        self.addCleanup(Path(tmp.name).unlink)
        return Path(tmp.name)

    def test_the_owners_files_as_they_are(self):
        thresholds = rules.load_thresholds()
        self.assertEqual({t.status for t in thresholds}, {"draft"})  # Claude's drafts, awaiting the owner
        self.assertIsNotNone(rules.min_steps(thresholds))
        self.assertEqual(rules.load_references(), [])  # none set yet

    def test_invalid_thresholds_refused(self):
        header = ",".join(rules.THRESHOLD_COLUMNS)
        for row in ("t1,stance,guess,5,points,draft,1,,,", "t1,walking_speed,side_difference,5,m/s,draft,1,,,",
                    "t1,stance,below,5,points,draft,1,,,", "t1,stance,side_difference,,points,draft,1,,,",
                    "t1,stance,side_difference,5,points,approved,1,,,", "t1,cadence,above,5,x,draft,1,,2026-10-27,"):
            with self.subTest(row):
                with self.assertRaises(ValueError):
                    rules.load_thresholds(self.write(f"{header}\n{row}\n"))
        header = ",".join(rules.REFERENCE_COLUMNS)
        with self.assertRaises(ValueError):  # a reference names its source, page and words
            rules.load_references(self.write(f"{header}\nwalking_speed,both,1,1.4,0.1,m/s,,,,draft,,\n"))

    def thresholds(self):
        return rules.load_thresholds()

    def test_indicators_say_which_value_is_past_which_threshold(self):
        found = {i.id: i for i in rules.indicators(session(), self.thresholds(), [])}
        self.assertEqual(found["stance_sides"].difference, 8)
        self.assertAlmostEqual(found["step_length_sides"].difference, 16.82, places=2)
        self.assertNotIn("walking_speed_low", found)  # 0.92 is not below 0.8
        slow = rules.indicators(session(values={"walking_speed": {"both": 0.5}}), self.thresholds(), [])
        self.assertEqual([i.id for i in slow], ["walking_speed_low"])
        band = rules.Reference("walking_speed", "both", 1.0, 1.4, 0.1, "m/s", "doc", 3, "words", "approved", "O",
                               "2026-10-27")
        found = {i.id for i in rules.indicators(session(), [], [band])}
        self.assertEqual(found, {"band:walking_speed:both"})

    def test_comparison(self):
        first = session(values={"walking_speed": {"both": 0.84}, "stance": {"left": 57, "right": 68}})
        second = session(id="G2", pace="fast", values={"walking_speed": {"both": 0.92}})
        self.assertEqual(rules.differing_conditions(first, second), ["pace"])
        src = rules.Reference("walking_speed", "any", None, None, 0.1, "m/s", "doc", 3, "words", "approved", "O",
                              "2026-10-27")
        [row] = rules.compared_values(first, second, [src])  # only what is in both
        self.assertEqual((row.change, row.at_least_smallest_real_change), (0.08, False))
        [row] = rules.compared_values(first, second, [])
        self.assertIsNone(row.at_least_smallest_real_change)  # not set: nothing said


class ReferenceQuoteTests(unittest.TestCase):
    """Every reference's words are on its page (CLAUDE.md: every quote checked word for word)."""

    def test_each_quote_is_on_its_page(self):
        references = rules.load_references()
        if references and not EXTRACTED_DIR.is_dir():
            self.skipTest("data/knowledge/extracted/ is missing: run python -m knowledge.ingest")
        from prosthetics.tests.test_component_guide import flat, pages
        for ref in references:
            with self.subTest(ref.measure):
                self.assertIn(flat(ref.quote), pages(ref.doc_id).get(ref.page, ""))


class GaitRouteTests(ProstheticRouteTestCase):
    def setUp(self):
        super().setUp()
        self.case_id = self.post_intake().headers["Location"].split("/review/")[1]
        self.base = f"/gait/{self.case_id}"

    def capture(self, **data):
        return self.client.post(f"{self.base}/capture", data=data, content_type="multipart/form-data")

    def two_sessions(self):
        self.assertEqual(self.capture(on="2026-10-01", source="wearable", walkway="10 m", pace="comfortable",
                                      m_walking_speed_both="0.84", m_stance_left="57", m_stance_right="68",
                                      steps="12").status_code, 302)
        self.assertEqual(self.capture(on="2026-10-15", source="phone_video", filming_consent="1", walkway="10 m",
                                      pace="fast", steps="8",
                                      table=(io.BytesIO(TABLE.encode()), "measures.csv")).status_code, 302)

    def test_first_page_and_tabs(self):
        page = self.client.get("/gait").get_data(as_text=True)
        self.assertIn(f'href="{self.base}/capture"', page)
        self.assertIn('title="Open a case first (Gait analysis)"', page)
        self.assertIn("draft, not the clinic&#39;s rule", page)
        self.assertIn(f'href="{self.base}/interpret"', self.client.get(f"{self.base}/capture").get_data(as_text=True))
        self.assertEqual(self.client.get("/gait/nope/capture").status_code, 404)

    def test_capture_refusals(self):
        for data, words in (({"source": "wearable", "m_cadence_both": "96"}, "Give the session's date."),
                            ({"on": "2026-10-01", "m_cadence_both": "96"}, "Choose where the measures came from."),
                            ({"on": "2026-10-01", "source": "phone_video", "m_cadence_both": "96"},
                             "needs the person's consent to filming"),
                            ({"on": "2026-10-01", "source": "wearable"}, "at least one measure"),
                            ({"on": "2026-10-01", "source": "wearable", "trials": "3", "trials_whole_body": "4",
                              "m_cadence_both": "96"}, "The trials don't add up")):
            with self.subTest(data):
                resp = self.capture(**data)
                self.assertEqual(resp.status_code, 400)
                self.assertIn(words, visible_text(resp.get_data(as_text=True)))
        resp = self.capture(on="2026-10-01", source="wearable",
                            table=(io.BytesIO(b"measure,left,right,both\nshoe_size,,,42\n"), "m.csv"))
        self.assertEqual(resp.status_code, 400)
        self.assertIn("The table could not be read: unknown measure", visible_text(resp.get_data(as_text=True)))
        self.assertIsNone(store.get(self.case_id).gait)

    def test_sessions_interpreted_with_references_not_set(self):
        self.two_sessions()
        gait = store.get(self.case_id).gait
        self.assertEqual([s.id for s in gait.sessions], ["G1", "G2"])
        self.assertEqual(gait.sessions[1].value("walking_speed"), 0.92)  # from the imported table
        page = visible_text(self.client.get(f"{self.base}/interpret?session=G2").get_data(as_text=True))
        self.assertIn("0.92", page)
        self.assertIn("not set", page)
        self.assertIn("Knee flexion over the gait cycle", page)
        csv_page = self.client.get(f"{self.base}/template.csv")
        self.assertEqual(csv_page.mimetype, "text/csv")

    def test_indicators_reviewed_or_dismissed_with_a_reason(self):
        self.two_sessions()
        page = visible_text(self.client.get(f"{self.base}/indicators?session=G2").get_data(as_text=True))
        self.assertIn("Stance differs between the sides", page)
        self.assertIn("8 points apart", page)
        self.assertIn("Only 8 steps were captured; the minimum is 10.", page)
        url = f"{self.base}/indicators?session=G2"
        resp = self.client.post(url, data={"indicator": "stance_sides", "mark": "dismissed", "session": "G2"})
        self.assertEqual(resp.status_code, 400)
        self.assertEqual(self.client.post(url, data={"indicator": "walking_speed_low", "mark": "reviewed",
                                                     "session": "G2"}).status_code, 400)  # not an indicator here
        self.client.post(url, data={"indicator": "stance_sides", "mark": "dismissed", "session": "G2",
                                    "words": "first session without the bars"})
        [review] = store.get(self.case_id).gait.session("G2").reviews
        self.assertEqual((review.mark.value, review.words), ("dismissed", "first session without the bars"))
        for words in ("you should", "recommend", "diagnosed"):
            self.assertNotIn(words, page.lower())

    def test_compare_two_sessions_and_send_it_to_the_case(self):
        record = CaseRecord(case=Case(amputation_level="transtibial", side="left"), plan=ProstheticPlan(
            alignment_versions=[AlignmentVersion(1, {"foot": "neutral"}, None, "2026-09-30T10:00:00+00:00"),
                                AlignmentVersion(2, {"foot": "5 mm posterior"}, "heel", "2026-10-14T10:00:00+00:00")]))
        store.save(record)
        base = f"/gait/{record.case.case_id}"
        for on, version, speed in (("2026-10-01", "alignment_versions:1", "0.84"),
                                   ("2026-10-15", "alignment_versions:2", "0.92")):
            resp = self.client.post(f"{base}/capture", data={"on": on, "source": "wearable", "walkway": "10 m",
                                                             "device_version": version, "m_walking_speed_both": speed})
            self.assertEqual(resp.status_code, 302)
        page = visible_text(self.client.get(f"{base}/compare?first=G1&second=G2").get_data(as_text=True))
        self.assertIn("Alignment version 1 → Alignment version 2", page)
        self.assertIn("+0.08", page)
        self.assertIn("An association in this person, never proof", page)
        self.assertIn(f'href="/prosthetics/{record.case.case_id}/fitting"',
                      self.client.get(f"{base}/compare?first=G1&second=G2").get_data(as_text=True))
        self.assertEqual(self.client.post(f"{base}/compare", data={"first": "G1", "second": "G1"}).status_code, 400)
        self.client.post(f"{base}/compare", data={"first": "G1", "second": "G2", "kind": "device_setting",
                                                  "note": "keep v2"})
        [saved] = store.get(record.case.case_id).gait.comparisons
        self.assertEqual((saved.first, saved.second, saved.note), ("G1", "G2", "keep v2"))

    def test_conditions_that_differ_are_shown(self):
        self.two_sessions()
        page = visible_text(self.client.get(f"{self.base}/compare?first=G1&second=G2").get_data(as_text=True))
        self.assertIn("Differs", page)
        self.assertIn("The conditions differ", page)

    def test_nothing_sent_to_the_ai_and_arabic_pages(self):
        calls = len(self.writer.calls)
        self.two_sessions()
        self.client.set_cookie("lang", "ar")
        for module in ("capture", "interpret", "indicators", "compare"):
            with self.subTest(module):
                self.assertEqual(self.client.get(f"{self.base}/{module}").status_code, 200)
        self.assertIn("الالتقاط", self.client.get(f"{self.base}/capture").get_data(as_text=True))
        self.client.delete_cookie("lang")
        self.assertEqual(len(self.writer.calls), calls)

    def test_the_patient_record_shows_the_sessions(self):
        resp = self.client.post("/record/new")
        code = resp.headers["Location"].split("/record/")[1].split("/")[0]
        self.client.post(f"/record/{code}/consent", data={"item": "care_record", "answer": "agreed",
                                                          "consent_lang": "en"})
        case_id = self.post_intake(person_code=code).headers["Location"].split("/review/")[1]
        self.client.post(f"/gait/{case_id}/capture", data={"on": "2026-10-15", "source": "insoles",
                                                           "m_cadence_both": "96"})
        page = visible_text(self.client.get(f"/record/{code}").get_data(as_text=True))
        self.assertIn("Gait session G1", page)
        self.assertIn("G1", [e.label for e in record_view(people.get_person(code)).events if e.kind == "gait_session"])


if __name__ == "__main__":
    unittest.main()

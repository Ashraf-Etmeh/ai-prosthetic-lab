"""Tests for the patient record and governance (record/; plan Part 8, use case 07).

People's records and the access trail go to temporary folders, never to the real data/records/people/ or
data/records/access_log.jsonl.
"""

import json
import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import patch

from prosthetics.case import Case
from prosthetics.plan import ProstheticPlan, SocketVersion
from prosthetics.tests.helpers import ProstheticRouteTestCase
from reasoning.rag import generate
from reasoning.writer import ClaudeWriter, GeminiWriter, WriterUnavailable
from record import access, governance, people
from record.timeline import record_view
from shared import config
from shared.followup import Alert, FollowUp, MeasureDef, Visit
from shared.store import CaseRecord, store
from shared.testing import visible_text


class TemporaryRecords(unittest.TestCase):
    def setUp(self):
        super().setUp()
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.tmp = Path(tmp.name)
        for name, value in (("PEOPLE_DIR", self.tmp / "people"), ("ACCESS_LOG_PATH", self.tmp / "access.jsonl")):
            patcher = patch.object(config, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def refused(self, key: str):
        """A context in which a change is refused with this interface text (its key, in any language)."""
        test = self

        class Refused:
            def __enter__(self):
                return self

            def __exit__(self, kind, error, _):
                test.assertIs(kind, people.PersonError, f"not refused: expected {key}")
                test.assertEqual(error.key, key)
                return True

        return Refused()

    def consenting(self, *items: str) -> people.Person:
        person = people.new_person()
        for item in items:
            people.record_consent(person, item, "agreed", "en")
        return people.get_person(person.code)


class PeopleTests(TemporaryRecords):
    def test_a_new_record_has_a_code_only(self):
        person = people.new_person()
        self.assertRegex(person.code, r"^P-[0-9A-F]{6}$")
        [line] = [json.loads(x) for x in (config.PEOPLE_DIR / f"{person.code}.jsonl").read_text().splitlines()]
        self.assertEqual(set(line), {"record_version", "kind", "at"})  # nothing else about the person
        self.assertEqual([p.code for p in people.all_people()], [person.code])
        for bad in ("p-000000", "../x", "", "P-00000G"):
            self.assertIsNone(people.get_person(bad))

    def test_consent_lines_are_only_added(self):
        person = people.new_person()
        people.record_consent(person, "cloud_model", "agreed", "ar")
        person = people.get_person(person.code)
        self.assertTrue(person.agrees("cloud_model"))
        with self.refused("error.consent_same"):
            people.record_consent(person, "cloud_model", "agreed", "en")
        people.record_consent(person, "cloud_model", "withdrawn", "en")
        person = people.get_person(person.code)
        self.assertFalse(person.agrees("cloud_model"))
        self.assertEqual([(c.answer, c.language) for c in person.consent], [("agreed", "ar"), ("withdrawn", "en")])
        with self.refused("error.consent_withdraw_unagreed"):
            people.record_consent(person, "quality_use", "withdrawn", "en")
        for item, answer, language in (("shoe_size", "agreed", "en"), ("cloud_model", "maybe", "en"),
                                       ("cloud_model", "agreed", "fr")):
            with self.assertRaises(people.PersonError):
                people.record_consent(person, item, answer, language)
        self.assertEqual(len((config.PEOPLE_DIR / f"{person.code}.jsonl").read_text().splitlines()), 3)

    def test_a_case_is_attached_only_with_a_care_record(self):
        person = people.new_person()
        case = Case(amputation_level="transtibial", side="left")
        with self.refused("error.person_no_care_record"):
            people.person_for_intake(person.code)
        with self.refused("error.person_no_care_record"):
            people.attach_case(person, case)
        people.record_consent(person, "care_record", "agreed", "en")
        person = people.person_for_intake(f"  {person.code.lower()} ")
        people.attach_case(person, case)
        people.attach_case(person, case)  # once only
        self.assertEqual(people.get_person(person.code).case_ids(), [case.case_id])
        self.assertEqual(people.person_of(case.case_id).code, person.code)
        self.assertIsNone(people.person_for_intake(""))
        with self.refused("error.person_unknown"):
            people.person_for_intake("P-000000")

    def test_a_deletion_request_stops_new_cases(self):
        person = self.consenting("care_record")
        with self.assertRaises(people.PersonError):
            people.record_request(person, "deletion")  # on whose request
        people.record_request(person, "deletion", "person")
        person = people.get_person(person.code)
        self.assertEqual(person.deletion_requested.by, "person")
        with self.refused("error.person_deletion_open"):
            people.person_for_intake(person.code)

    def test_a_deletion_carried_out_by_the_owner(self):
        person = self.consenting("care_record")
        people.record_request(person, "deletion", "person")
        people._append(person.code, "deleted")  # what the owner writes, by hand, after removing the content
        person = people.get_person(person.code)
        self.assertIsNotNone(person.deleted_at)
        self.assertEqual([r.kind for r in person.requests], ["deletion"])  # the request stays

    def test_notes(self):
        person = people.new_person()
        for text in ("", "   ", "x" * (people.MAX_NOTE + 1)):
            with self.assertRaises(people.PersonError):
                people.add_note(person, text)
        people.add_note(person, " ملاحظة للزميل ")
        self.assertEqual([n.text for n in people.get_person(person.code).notes], ["ملاحظة للزميل"])

    def test_what_the_consent_does(self):
        case = Case(amputation_level="transtibial", side="left")
        self.assertIsNone(people.cloud_consent(case.case_id))  # no person: as before
        self.assertTrue(people.counts_allowed(case.case_id))
        person = self.consenting("care_record")
        people.attach_case(person, case)
        self.assertIs(people.cloud_consent(case.case_id), False)  # not recorded: no
        self.assertFalse(people.counts_allowed(case.case_id))
        self.assertEqual(people.left_out_of_counts(), {case.case_id})
        people.record_consent(person, "cloud_model", "agreed", "en")
        people.record_consent(person, "quality_use", "agreed", "en")
        self.assertIs(people.cloud_consent(case.case_id), True)
        self.assertEqual(people.left_out_of_counts(), set())


class ConsentGateTests(TemporaryRecords):
    """Owner's answer, 2026-10-27: a case attached to a person goes to the cloud model only with their consent."""

    def setUp(self):
        super().setUp()
        self.calls = []
        for cls in (GeminiWriter, ClaudeWriter):
            patcher = patch.object(cls, "write", autospec=True,
                                   side_effect=lambda *args: self.calls.append(args) or _raise())
            patcher.start()
            self.addCleanup(patcher.stop)
        self.case = Case(amputation_level="transtibial", side="left")  # age not recorded: a gap topic

    def ask(self, writer=None):
        from prosthetics.tests.helpers import VOLUME_PASSAGE

        return generate(self.case, {"age_years": [VOLUME_PASSAGE]}, writer or GeminiWriter())

    def test_no_consent_no_cloud(self):
        person = self.consenting("care_record")
        people.attach_case(person, self.case)
        for writer in (GeminiWriter(), ClaudeWriter()):
            generation = self.ask(writer)
            self.assertEqual(self.calls, [])
            self.assertEqual(generation.writer, "offline")
            # A part with no passage asks nothing (no reason); every part that would ask says why it did not.
            self.assertEqual({part.reason for part in generation.parts.values()} - {None}, {people.CONSENT_OFF})
        people.record_consent(people.get_person(person.code), "cloud_model", "agreed", "en")
        self.ask()
        self.assertEqual(len(self.calls), 1)
        people.record_consent(people.get_person(person.code), "cloud_model", "withdrawn", "en")
        self.ask()
        self.assertEqual(len(self.calls), 1)  # withdrawn: no more calls

    def test_a_case_with_no_person_is_unchanged(self):
        self.ask()
        self.assertEqual(len(self.calls), 1)


class AccessTrailTests(TemporaryRecords):
    def test_trail(self):
        access.log_access("P-AAAAAA", "opened_record")
        access.log_access("P-BBBBBB", "added_note")
        access.log_access("P-AAAAAA", "consent", "cloud_model")
        trail = access.trail("P-AAAAAA")
        self.assertEqual([(line["action"], line["detail"], line["who"]) for line in trail],
                         [("consent", "cloud_model", None), ("opened_record", None, None)])
        with self.assertRaises(ValueError):
            access.log_access("P-AAAAAA", "edited")


class GovernanceTests(unittest.TestCase):
    def test_the_owners_files_as_they_are(self):
        roles = governance.load_roles()
        self.assertEqual([r.role for r in roles], list(governance.ROLES))
        self.assertEqual({r.status for r in roles}, {"draft"})  # awaiting the owner
        retention = governance.load_retention()
        self.assertEqual({name: s.value for name, s in retention.items()}, {"retention_period": None, "law": None})

    def write(self, text: str) -> Path:
        tmp = tempfile.NamedTemporaryFile("w", suffix=".csv", delete=False, encoding="utf-8")
        tmp.write(text)
        tmp.close()
        self.addCleanup(Path(tmp.name).unlink)
        return Path(tmp.name)

    def test_invalid_rows_are_refused(self):
        header = ",".join(governance.ROLE_COLUMNS)
        for row in ("nurse,yes,yes,no,no,draft,1,,,", "therapist,always,yes,no,no,draft,1,,,",
                    "therapist,yes,yes,no,no,approved,1,,,", "therapist,yes,yes,no,no,draft,0,,,",
                    "therapist,yes,yes,no,no,draft,1,,2026-10-27,"):
            with self.subTest(row):
                with self.assertRaises(ValueError):
                    governance.load_roles(self.write(f"{header}\n{row}\n"))
        with self.assertRaises(ValueError):
            governance.load_roles(self.write("role,record\ntherapist,yes\n"))
        approved = governance.load_roles(self.write(f"{header}\ntherapist,yes,,no,no,approved,2,Owner,2026-10-27,\n"))
        self.assertEqual((approved[0].access["notes"], approved[0].owner), (None, "Owner"))
        retention_header = ",".join(governance.RETENTION_COLUMNS)
        with self.assertRaises(ValueError):
            governance.load_retention(self.write(f"{retention_header}\nlaw,,approved,Owner,2026-10-27,\n"))

    def test_where_data_goes_follows_the_switches(self):
        uses = {use.what: use.on for use in governance.cloud_uses()}
        self.assertEqual(set(uses), {"prosthetics", "orthotics", "search"})
        self.assertEqual(uses["orthotics"], config.ORTHOTIC_CLOUD_AI)
        with patch.object(config, "SEARCH_CLOUD_AI", True):
            self.assertTrue({u.what: u.on for u in governance.cloud_uses()}["search"])


class TimelineTests(TemporaryRecords):
    def test_the_record_gathers_what_was_recorded(self):
        log = self.tmp / "review_log.jsonl"
        folder = patch.object(store, "folder", self.tmp / "cases")  # never the real data/records/cases/
        folder.start()
        self.addCleanup(folder.stop)
        case = Case(amputation_level="transtibial", side="left")
        past = (date.today() - timedelta(days=3)).isoformat()
        plan = ProstheticPlan(socket_versions=[SocketVersion(1, "fits", None, "2026-10-20T10:00:00+00:00")],
                              follow_up=FollowUp(measures=[MeasureDef("Two-minute walk", "m", "no aid")],
                                                 visits=[Visit("3-month review", "2026-10-21", "done",
                                                               {"Two-minute walk": "96"}),
                                                         Visit("6-month review", past, "due")],
                                                 alerts=[Alert("redness after long walks")]))
        store.save(CaseRecord(case=case, plan=plan))
        log.write_text(json.dumps({"case_id": case.case_id, "decision": "approve",
                                   "logged_at": "2026-10-19T09:00:00+00:00"}) + "\n", encoding="utf-8")
        person = self.consenting("care_record")
        people.attach_case(person, case)
        with patch("review.decision_log.REVIEW_LOG_PATH", log):
            view = record_view(people.get_person(person.code))
        events = [(e.kind, e.day) for e in view.events]
        self.assertEqual(sorted(events), sorted([("intake", case.created_at[:10]), ("visit", past),
                                                 ("visit", "2026-10-21"), ("version", "2026-10-20"),
                                                 ("review", "2026-10-19")]))
        self.assertEqual([e.at for e in view.events], sorted((e.at for e in view.events), reverse=True))  # newest first
        self.assertEqual(view.next_due.name, "6-month review")
        self.assertTrue(view.next_due.date_passed)
        [table] = view.measures
        self.assertEqual(table.rows, [("Two-minute walk", "m", "no aid", ["96"])])
        self.assertEqual(view.open_alerts, [("prosthetics", case.case_id, "redness after long walks")])


def _raise():
    raise WriterUnavailable("API called")  # counted in self.calls; the page goes on without the AI


class RecordRouteTests(ProstheticRouteTestCase):
    def new_record(self, *agreed: str) -> str:
        resp = self.client.post("/record/new")
        self.assertEqual(resp.status_code, 302)
        code = resp.headers["Location"].split("/record/")[1].split("/")[0]
        for item in agreed:
            resp = self.client.post(f"/record/{code}/consent", data={"item": item, "answer": "agreed",
                                                                     "consent_lang": "en"})
            self.assertEqual(resp.status_code, 302)
        return code

    def test_the_pages_in_both_languages(self):
        code = self.new_record("care_record")
        for lang, words in (("en", ("Patient record", "1 Record and follow-up", "Keep a care record",
                                    "draft, awaiting the owner", "Not enforced yet")),
                            ("ar", ("سجل المريض", "1 السجل والمتابعة", "من يحق له رؤية ماذا"))):
            self.client.set_cookie("lang", lang)
            for url in ("/record", f"/record/{code}", "/record/governance", f"/record/{code}/governance"):
                with self.subTest(lang=lang, url=url):
                    resp = self.client.get(url)
                    self.assertEqual(resp.status_code, 200)
            page = visible_text(self.client.get(f"/record/{code}/governance").get_data(as_text=True))
            for w in words:
                self.assertIn(w, page)
        self.client.delete_cookie("lang")
        page = self.client.get(f"/record/{code}").get_data(as_text=True)
        self.assertIn(f'href="/record/{code}/governance"', page)  # the tabs keep the person
        self.assertIn(f"Person {code}", visible_text(page))
        self.assertEqual(self.client.get("/record/P-000000").status_code, 404)
        self.assertEqual(self.client.get("/record/P-000000/governance").status_code, 404)

    def test_consent_text_in_the_persons_language(self):
        code = self.new_record()
        page = self.client.get(f"/record/{code}/governance?consent_lang=ar").get_data(as_text=True)
        self.assertIn("الاحتفاظ بسجل رعاية", page)  # on the English page
        resp = self.client.post(f"/record/{code}/consent", data={"item": "cloud_model", "answer": "withdrawn",
                                                                 "consent_lang": "ar"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("Only an agreed item can be withdrawn.", resp.get_data(as_text=True))
        self.client.post(f"/record/{code}/consent", data={"item": "cloud_model", "answer": "agreed",
                                                          "consent_lang": "ar"})
        self.assertEqual(people.get_person(code).consent_now("cloud_model").language, "ar")

    def test_a_case_joins_a_record_at_its_intake(self):
        resp = self.post_intake(person_code="P-000000")
        self.assertEqual(resp.status_code, 400)
        self.assertIn("No record has the code P-000000", resp.get_data(as_text=True))
        code = self.new_record()
        before = len(store.all())
        resp = self.post_intake(person_code=code)
        self.assertEqual(resp.status_code, 400)  # no care record yet
        self.assertEqual(len(store.all()), before)  # nothing saved
        self.assertEqual(people.get_person(code).cases, [])
        code = self.new_record("care_record")
        resp = self.post_intake(person_code=code)
        self.assertEqual(resp.status_code, 302)
        [case_id] = people.get_person(code).case_ids()
        page = visible_text(self.client.get(f"/record/{code}").get_data(as_text=True))
        self.assertIn("Case recorded at intake", page)
        self.assertIn(case_id, page)
        actions = [line["action"] for line in access.trail(code)]
        self.assertEqual(actions[:2], ["opened_record", "attached_case"])
        self.assertIsNone(access.trail(code)[0]["who"])

    def test_an_orthotic_case_joins_too(self):
        code = self.new_record("care_record")
        resp = self.client.post("/intake/orthotics", data={"condition": "stroke", "side": "right",
                                                           "person_code": code})
        self.assertEqual(resp.status_code, 302)
        [case_id] = people.get_person(code).case_ids()
        self.assertEqual(store.get(case_id).case.domain, "orthotics")

    def test_notes_copy_and_deletion(self):
        code = self.new_record("care_record")
        self.post_intake(person_code=code, intake_notes="typed at intake")
        self.assertEqual(self.client.post(f"/record/{code}/note", data={"text": " "}).status_code, 400)
        resp = self.client.post(f"/record/{code}/note", data={"text": "Check the socket at the next visit."})
        self.assertEqual(resp.status_code, 302)
        self.assertIn("Check the socket at the next visit.", self.client.get(f"/record/{code}").get_data(as_text=True))
        resp = self.client.post(f"/record/{code}/request", data={"kind": "copy"})
        self.assertEqual(resp.headers["Location"], f"/record/{code}/copy")
        copy = visible_text(self.client.get(resp.headers["Location"]).get_data(as_text=True))
        for words in ("Copy of record", "transtibial", "typed at intake", "Check the socket at the next visit.",
                      "Keep a care record", "Copy given", "who: not recorded"):
            self.assertIn(words, copy)
        self.assertEqual(self.client.post(f"/record/{code}/request", data={"kind": "deletion"}).status_code, 400)
        self.client.post(f"/record/{code}/request", data={"kind": "deletion", "by": "representative"})
        page = visible_text(self.client.get(f"/record/{code}").get_data(as_text=True))
        self.assertIn("A deletion was requested", page)
        self.assertEqual(self.post_intake(person_code=code).status_code, 400)  # no new case
        actions = {line["action"] for line in access.trail(code)}
        self.assertLessEqual({"created", "consent", "attached_case", "added_note", "copy_given", "opened_copy",
                              "deletion_requested"}, actions)

    def test_the_quality_page_leaves_out_people_who_did_not_agree(self):
        code = self.new_record("care_record")
        self.post_intake(person_code=code)
        [case_id] = people.get_person(code).case_ids()
        self.client.post(f"/review/{case_id}/decision", data={"decision": "approve"})
        page = visible_text(self.client.get("/quality").get_data(as_text=True))
        self.assertIn("1 review(s) left out: the person did not agree to quality use.", page)
        self.client.post(f"/record/{code}/consent", data={"item": "quality_use", "answer": "agreed",
                                                          "consent_lang": "en"})
        self.assertNotIn("left out", visible_text(self.client.get("/quality").get_data(as_text=True)))


if __name__ == "__main__":
    unittest.main()

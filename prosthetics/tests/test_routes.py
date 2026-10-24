"""Tests for the prosthetic intake and review pages, through Flask's test client."""

import re
import unittest
from unittest.mock import patch

from markupsafe import escape

from knowledge.catalog import attributions
from knowledge.retrieval import KnowledgeBaseMissing
from prosthetics.tests.helpers import (
    BASE_FORM,
    FULL_FORM,
    KNEE_PASSAGE,
    VOLUME_PASSAGE,
    ProstheticRouteTestCase,
    catalogued_passage,
    fake_retrieval,
)
from review.decision_log import read_decisions
from shared.config import PROMPT_VERSION
from shared.store import store
from shared.testing import FakeWriter, visible_text


class IntakeRouteTests(ProstheticRouteTestCase):
    def test_form_renders(self):
        resp = self.client.get("/intake")
        self.assertEqual(resp.status_code, 200)
        self.assertIn(b'name="comorbidities"', resp.data)
        self.assertIn(b'name="no_prior_devices"', resp.data)
        self.assertIn(b'name="device_3_issues"', resp.data)
        self.assertNotIn(b'class="error"', resp.data)

    def test_fully_filled_form_has_no_gaps(self):
        resp = self.client.post("/intake", data=FULL_FORM)
        self.assertEqual(store.all()[-1].gaps, [])
        page = self.client.get(resp.headers["Location"]).get_data(as_text=True)
        self.assertIn("No gaps identified", page)
        self.assertIn("PTB socket, SACH foot · 2.0 years · no longer used · issues: loose fit",
                      visible_text(page))

    def test_prior_devices_from_rows(self):
        self.post_intake(
            device_1_description="  PTB socket  ", device_1_years="2.5", device_1_current="no",
            device_3_description="pin-lock liner", device_3_current="yes",  # row 2 left empty
        )
        devices = store.all()[-1].case.prior_devices
        self.assertEqual([d.device_description for d in devices], ["PTB socket", "pin-lock liner"])
        self.assertEqual((devices[0].years_used, devices[0].currently_using, devices[0].issues),
                         (2.5, False, None))
        self.assertIs(devices[1].currently_using, True)

    def test_no_prior_prosthesis_is_not_a_gap(self):
        self.post_intake(no_prior_devices="1")
        record = store.all()[-1]
        self.assertEqual(record.case.prior_devices, [])
        self.assertNotIn("prior_devices", [g.field for g in record.gaps])

    def test_blank_prior_devices_not_recorded(self):
        self.post_intake()
        record = store.all()[-1]
        self.assertIsNone(record.case.prior_devices)
        self.assertIn("prior_devices", [g.field for g in record.gaps])

    def test_bad_prior_devices_rejected(self):
        for fields, message in [
            ({"device_2_years": "3"}, b"prior device 2: describe the device"),
            ({"no_prior_devices": "1", "device_1_description": "socket"}, b"is ticked, but a device"),
            ({"device_1_description": "socket", "device_1_years": "-1"},
             b"prior device 1: Years used: enter 0 or more."),
            ({"device_1_description": "socket", "device_1_current": "maybe"}, b"expected yes or no"),
        ]:
            with self.subTest(**fields):
                before = len(store.all())
                resp = self.post_intake(**fields)
                self.assertEqual(resp.status_code, 400)
                self.assertIn(message, resp.data)
                self.assertEqual(len(store.all()), before)

    def test_valid_submission_saves_and_redirects_to_review(self):
        resp = self.post_intake(
            age_years="58", wound_status="healed", comorbidities="Diabetes\nHypertension"
        )
        self.assertEqual(resp.status_code, 302)
        case = store.all()[-1].case
        self.assertEqual(case.age_years, 58)
        self.assertEqual(case.residual_limb.wound_status.value, "healed")
        self.assertEqual(case.comorbidities, ["Diabetes", "Hypertension"])
        self.assertEqual(self.client.get(resp.headers["Location"]).status_code, 200)

    def test_blank_comorbidities_not_recorded(self):
        self.post_intake(comorbidities="")
        self.assertIsNone(store.all()[-1].case.comorbidities)

    def test_bad_values_rejected_with_message(self):
        for fields in [
            {"age_years": "-5"},
            {"body_weight_kg": "0"},
            {"age_years": "abc"},
            {"amputation_level": "banana"},
            {"wound_status": "bleeding"},
        ]:
            with self.subTest(**fields):
                before = len(store.all())
                resp = self.post_intake(**fields)
                self.assertEqual(resp.status_code, 400)
                self.assertIn(b"Case not saved:", resp.data)
                self.assertEqual(len(store.all()), before)

    def test_missing_required_field(self):
        for data, name in [({"side": "left"}, b"amputation_level is required"),
                           ({"amputation_level": "transtibial"}, b"side is required"),
                           ({"amputation_level": "transtibial", "side": ""}, b"side is required")]:
            with self.subTest(**data):
                resp = self.client.post("/intake", data=data)
                self.assertEqual(resp.status_code, 400)
                self.assertIn(name, resp.data)  # the form with a message, not a crash page


class RestartTests(ProstheticRouteTestCase):
    """Cases are saved to disk: a review page still works after the server restarts."""

    def restart(self):
        store._records.clear()  # what a restart loses: everything in memory; the files stay

    def test_review_page_after_a_restart(self):
        case_id = self.client.post("/intake", data=FULL_FORM | {"age_years": "", "k_level": "K2"}) \
            .headers["Location"].rsplit("/", 1)[-1]
        before = self.client.get(f"/review/{case_id}").get_data(as_text=True)
        self.assertTrue((self.cases_dir / f"{case_id}.json").is_file())

        self.restart()
        after = self.client.get(f"/review/{case_id}")

        self.assertEqual(after.status_code, 200)
        self.assertEqual(after.get_data(as_text=True), before)  # the same page, word for word

    def test_decision_after_a_restart(self):
        case_id = self.post_intake().headers["Location"].rsplit("/", 1)[-1]
        readiness = store.get(case_id).fitting.sections[0].statements[0].statement.id
        calls = len(self.writer.calls)
        self.restart()
        resp = self.client.post(f"/review/{case_id}/decision", follow_redirects=True, data={
            "decision": "approve", "gap:residual_limb.volume_stability": "needed",
            f"opt:{readiness}": "relevant"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(len(self.writer.calls), calls)  # the AI's answer came from the case file, not a new call
        [entry] = read_decisions(case_id, path=self.log_path)
        self.assertEqual(entry["case"]["case_id"], case_id)
        volume = next(g for g in entry["gaps"] if g["field"] == "residual_limb.volume_stability")
        self.assertEqual(volume["source"]["citation"], "Test Guideline (2024), p. 14")
        self.assertEqual(volume["summary_en"], "AI sentence about residual_limb.volume_stability.")
        marks = {s["id"]: s["reviewer_judgement"] for section in entry["fitting"]["sections"] for s in section["statements"]}
        self.assertEqual(marks[readiness], "relevant")

    def test_case_never_saved_is_still_404(self):
        self.restart()
        self.assertEqual(self.client.get("/review/0123456789ab").status_code, 404)


class FormKeptTests(ProstheticRouteTestCase):
    """A refused form, or a language switch, brings the form back as it was sent."""

    def test_form_kept_after_an_error(self):
        resp = self.client.post("/intake", data=FULL_FORM | {"age_years": "abc"})
        self.assertEqual(resp.status_code, 400)
        page = resp.get_data(as_text=True)
        for name, value in FULL_FORM.items():
            if name == "age_years":
                continue
            with self.subTest(name=name):
                if name in ("activity_description", "functional_goals", "comorbidities", "intake_notes"):
                    self.assertRegex(page, rf'<textarea id="{name}"[^>]*>{re.escape(value)}</textarea>')
                elif name in ("amputation_level", "side", "etiology", "wound_status", "volume_stability",
                              "k_level", "device_1_current"):
                    self.assertRegex(page, rf'(?s)<select id="{name}"[^>]*>(?:(?!</select>).)*'
                                           rf'<option value="{value}" selected>')
                else:
                    self.assertRegex(page, rf'name="{name}"[^>]*value="{re.escape(str(escape(value)))}"')
        self.assertIn('name="age_years" value="abc"', page)  # the bad value too, to correct it

    def test_checkbox_and_unknown_choice(self):
        resp = self.post_intake(no_prior_devices="1", amputation_level="banana", side="right")
        page = resp.get_data(as_text=True)
        self.assertIn('name="no_prior_devices" value="1" checked', page)
        self.assertIn('<option value="right" selected>', page)
        # A value that isn't an option: the "Select…" placeholder, never a guessed level.
        self.assertIn('<option value="" disabled selected>Select…</option>', page)
        self.assertNotRegex(page, r'(?s)<select id="amputation_level"(?:(?!</select>).)*value="[a-z_]+" selected')

    def test_typed_text_is_escaped(self):
        page = self.post_intake(age_years="x", pain='"><b>bold</b>').get_data(as_text=True)
        self.assertIn('value="&#34;&gt;&lt;b&gt;bold&lt;/b&gt;"', page)
        self.assertNotIn("<b>bold</b>", page)

    def test_language_switch_keeps_the_input(self):
        before = len(store.all())
        resp = self.client.post("/intake", data={
            "switch_language": "ar", "amputation_level": "transfemoral", "pain": "ألم شبحي",
            "comorbidities": "Diabetes", "device_1_description": "socket"})  # side not chosen yet
        self.assertEqual(resp.status_code, 200)
        self.assertIn("lang=ar", resp.headers["Set-Cookie"])
        page = resp.get_data(as_text=True)
        self.assertIn('<html lang="ar" dir="rtl">', page)
        self.assertIn('<option value="transfemoral" selected>بتر فوق الركبة</option>', page)
        self.assertIn('value="ألم شبحي"', page)
        self.assertIn(">Diabetes</textarea>", page)
        self.assertIn('name="device_1_description" dir="auto"', page)
        self.assertIn('value="socket"', page)
        self.assertNotIn('class="error"', page)  # not a submission: nothing checked, nothing saved
        self.assertEqual(len(store.all()), before)
        self.assertIn('dir="rtl"', self.client.get("/intake").get_data(as_text=True))  # remembered

        back = self.client.post("/intake", data={"switch_language": "en", "pain": "ألم شبحي"})
        self.assertIn('<html lang="en" dir="ltr">', back.get_data(as_text=True))
        self.assertIn('value="ألم شبحي"', back.get_data(as_text=True))

    def test_unknown_language_refused(self):
        resp = self.client.post("/intake", data={"switch_language": "fr", **BASE_FORM})
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn("Set-Cookie", resp.headers)

    def test_enter_sends_the_case_not_the_language_button(self):
        # Enter in a field submits with the form's first submit button in the page.
        page = self.client.get("/intake").get_data(as_text=True)
        buttons = re.findall(r"<button [^>]*>", page)
        self.assertIn('form="intake-form" class="default-submit"', buttons[0])
        self.assertNotIn("name=", buttons[0])
        self.assertIn('name="switch_language"', buttons[1])


class IntakeErrorTests(ProstheticRouteTestCase):
    """Refused values are explained with the form's own labels, in the page's language."""

    CASES = [
        ({"age_years": "abc"}, "Age (years): enter a whole number.",
         "العمر (بالسنوات): أدخل عدداً صحيحاً."),
        ({"age_years": "64.5"}, "Age (years): enter a whole number.",
         "العمر (بالسنوات): أدخل عدداً صحيحاً."),
        ({"age_years": "-5"}, "Age (years): enter 0 or more.", "العمر (بالسنوات): أدخل صفراً أو أكثر."),
        ({"body_weight_kg": "0"}, "Body weight (kg): enter a number greater than 0.",
         "وزن الجسم (كغ): أدخل رقماً أكبر من صفر."),
        ({"body_weight_kg": "heavy"}, "Body weight (kg): enter a number.", "وزن الجسم (كغ): أدخل رقماً."),
        ({"months_since_amputation": "nan"}, "Months since amputation: enter a number.",
         "عدد الأشهر منذ البتر: أدخل رقماً."),
        ({"months_since_amputation": "inf"}, "Months since amputation: enter a number.",
         "عدد الأشهر منذ البتر: أدخل رقماً."),
        ({"amputation_level": "banana"}, "Amputation level: choose one of the listed options.",
         "مستوى البتر: اختر أحد الخيارات المعروضة."),
        ({"side": "middle"}, "Side: choose one of the listed options.", "الجانب: اختر أحد الخيارات المعروضة."),
        ({"etiology": "magic"}, "Etiology: choose one of the listed options.",
         "سبب البتر: اختر أحد الخيارات المعروضة."),
        ({"wound_status": "bleeding"}, "Wound status: choose one of the listed options.",
         "حالة الجرح: اختر أحد الخيارات المعروضة."),
        ({"volume_stability": "big"}, "Volume stability: choose one of the listed options.",
         "ثبات الحجم: اختر أحد الخيارات المعروضة."),
        ({"k_level": "K9"}, "K-level (lower limb only): choose one of the listed options.",
         "المستوى الوظيفي K (للطرف السفلي فقط): اختر أحد الخيارات المعروضة."),
        ({"device_1_description": "socket", "device_1_years": "x"},
         "prior device 1: Years used: enter a number.", "الجهاز السابق 1: سنوات الاستخدام: أدخل رقماً."),
        ({"device_1_description": "socket", "device_1_years": "-1"},
         "prior device 1: Years used: enter 0 or more.", "الجهاز السابق 1: سنوات الاستخدام: أدخل صفراً أو أكثر."),
    ]
    PYTHON_WORDING = ("invalid literal", "could not convert", "is not a valid", "must be 0 or greater",
                      "must be greater than 0")

    def test_errors_in_both_languages(self):
        for lang, prefix, column in (("en", "Case not saved: ", 1), ("ar", "لم تُحفظ الحالة: ", 2)):
            self.client.set_cookie("lang", lang)
            for case in self.CASES:
                fields, expected = case[0], case[column]
                with self.subTest(lang=lang, **fields):
                    before = len(store.all())
                    resp = self.post_intake(**fields)
                    self.assertEqual(resp.status_code, 400)
                    page = visible_text(resp.get_data(as_text=True))
                    self.assertIn(prefix + expected, page)
                    for wording in self.PYTHON_WORDING:
                        self.assertNotIn(wording, page)
                    self.assertEqual(len(store.all()), before)

    def test_unexpected_error_shown_without_python_wording(self):
        with patch("prosthetics.intake._case_from_form", side_effect=ValueError("boom: internal detail")):
            resp = self.post_intake()
        self.assertEqual(resp.status_code, 400)
        page = visible_text(resp.get_data(as_text=True))
        self.assertIn("Case not saved: A value could not be read. Check the form and try again.", page)
        self.assertNotIn("boom", page)


class ReviewRouteTests(ProstheticRouteTestCase):
    def test_unknown_case_is_404(self):
        self.assertEqual(self.client.get("/review/does-not-exist").status_code, 404)

    def test_gaps_show_the_quoted_source(self):
        page = self.client.get(self.post_intake().headers["Location"]).get_data(as_text=True)
        self.assertIn("Residual limb volume stability", page)
        self.assertIn("Residual limb volume should be stable before the definitive socket is cast.", page)
        self.assertIn("Test Guideline (2024), p. 14", page)
        self.assertIn("test_guideline_2024-0007", page)
        self.assertIn("The lists may be incomplete", page)
        self.assertIn("It does not choose or rank components.", page)
        self.assertIn("No source cited.", page)  # the other gaps have no passage here

    def test_missing_source_library_is_shown(self):
        with patch("reasoning.pathway.retrieve_relevant_chunks",
                   side_effect=KnowledgeBaseMissing("No vector store.")):
            resp = self.post_intake()
        page = self.client.get(resp.headers["Location"]).get_data(as_text=True)
        self.assertIn("The source library was not searched: No vector store.", page)
        self.assertIn("Residual limb wound status", page)  # gaps are still listed

    def new_case_id(self) -> str:
        self.post_intake()
        return store.all()[-1].case.case_id

    def post_decision(self, case_id: str, **data):
        return self.client.post(f"/review/{case_id}/decision", data=data, follow_redirects=True)

    def test_gaps_offer_a_judgement(self):
        page = self.client.get(self.post_intake().headers["Location"]).get_data(as_text=True)
        self.assertIn('name="gap:residual_limb.volume_stability" value="needed"', page)
        self.assertIn('name="gap:residual_limb.volume_stability" value="not_needed"', page)

    def test_decision_is_saved_to_the_log_and_shown(self):
        case_id = self.new_case_id()
        resp = self.post_decision(
            case_id,
            decision="approve",
            note="looks complete",
            **{"gap:residual_limb.volume_stability": "needed", "gap:residual_limb.wound_status": ""},
        )
        self.assertEqual(resp.status_code, 200)
        page = resp.get_data(as_text=True)
        self.assertIn("Decision saved to the review log: <strong>approve</strong>", page)
        self.assertIn("Logged decisions for this case (1)", page)
        self.assertIn("looks complete", page)

        [entry] = read_decisions(case_id, path=self.log_path)
        self.assertEqual((entry["decision"], entry["note"]), ("approve", "looks complete"))
        self.assertEqual(entry["ui_language"], "en")
        judgements = {g["field"]: g["reviewer_judgement"] for g in entry["gaps"]}
        self.assertEqual(judgements["residual_limb.volume_stability"], "needed")
        self.assertIsNone(judgements["residual_limb.wound_status"])  # left on "not marked"
        volume = next(g for g in entry["gaps"] if g["field"] == "residual_limb.volume_stability")
        self.assertEqual(volume["source"]["citation"], "Test Guideline (2024), p. 14")

    def test_each_decision_is_added(self):
        case_id = self.new_case_id()
        self.post_decision(case_id, decision="reject", note="duplicate")
        page = self.post_decision(case_id, decision="approve").get_data(as_text=True)
        self.assertIn("Logged decisions for this case (2)", page)
        self.assertEqual([e["decision"] for e in read_decisions(case_id, path=self.log_path)],
                         ["reject", "approve"])

    def test_invalid_decision_refused_and_not_logged(self):
        case_id = self.new_case_id()
        for data in [{"decision": "maybe"}, {},
                     {"decision": "approve", "gap:residual_limb.wound_status": "yes"}]:
            with self.subTest(**data):
                resp = self.post_decision(case_id, **data)
                self.assertEqual(resp.status_code, 400)
                self.assertIn(b"Decision not saved:", resp.data)
        self.assertEqual(read_decisions(path=self.log_path), [])

    def test_edit_without_note_keeps_the_choices(self):
        case_id = self.new_case_id()
        resp = self.post_decision(
            case_id, decision="edit", **{"gap:residual_limb.volume_stability": "not_needed"}
        )
        self.assertEqual(resp.status_code, 400)
        page = resp.get_data(as_text=True)
        self.assertIn("An edit needs a note", page)
        self.assertIn('value="not_needed" checked', page)
        self.assertEqual(read_decisions(path=self.log_path), [])

    def test_decision_for_unknown_case_is_404(self):
        self.assertEqual(self.post_decision("does-not-exist", decision="approve").status_code, 404)


class ComponentRouteTests(ProstheticRouteTestCase):
    """The functional-level and component sections of the review page (the RAG)."""

    def review(self, **fields) -> str:
        resp = self.post_intake(**fields)
        return visible_text(self.client.get(resp.headers["Location"]).get_data(as_text=True))

    def knee_id(self) -> str:
        return next(c.statement.id for c in store.all()[-1].components.statements if c.statement.component == "knee")

    def test_transfemoral_k2_shows_ai_summaries_over_checked_quotes(self):
        page = self.review(amputation_level="transfemoral", k_level="K2", functional_goals="walk to church")
        components = store.all()[-1].components
        self.assertIn("Recorded K-level: K2", page)
        self.assertIn("walk to church", page)
        self.assertRegex(page, r"(?s)What the sources say about the functional level:.*AI summary — check it "
                               r"against the quote below:AI sentence about functional_level\.\s+Level 2: Has the "
                               r"ability or potential for\s+Lower Limb Prosthetic Workgroup Consensus Document "
                               r"\(2017\), p\. 5")
        self.assertIn(f"What the sources say about components ({len(components.component_sections[0].statements)} "
                      "statements)", page)
        self.assertIn("It does not choose or rank components.", page)
        # The AI's sentence, labelled, then the passage's own words and the catalog's citation.
        self.assertRegex(page, r"Knee unit\s+Source grade: none given\s+guideline or protocol\s+rag-knee-[0-9a-f]{10}"
                               r"\s+AI summary — check it against the quote below:AI sentence about knee\.\s+"
                               r"For prosthetic ambulators, we suggest prescribing microprocessor knee\s+"
                               r"VA/DoD [^\n]*\(2024\), p\. 56")
        self.assertIn("lower_limb_amputation_va_dod_cpg_2024-0901", page)  # the passage id, and the full passage
        self.assertIn("over non-microprocessor knee units. Weak for Reviewed, New-added", page)
        raw = self.client.get(f"/review/{store.all()[-1].case.case_id}").get_data(as_text=True)
        self.assertIn(f'name="opt:{self.knee_id()}" value="relevant"', raw)
        self.assertNotIn("va_dod_ll_17_microprocessor_knee", raw)  # the hand-written statements are the answer key now

    def test_what_the_model_was_asked(self):
        self.review(amputation_level="transfemoral", k_level="K2")

        def topics(schema):
            return schema["properties"]["items"]["items"]["properties"]["topic"]["enum"]

        system, user, schema = next(call for call in self.writer.calls if "knee" in topics(call[2]))
        self.assertIn("never advise", system)
        self.assertIn('"amputation_level": "transfemoral"', user)
        self.assertIn('"functional_level_recorded": "K2"', user)
        self.assertNotIn("case_id", user)  # nothing generated, nothing identifying
        for typed in ("test case", "intact"):  # the intake notes and cognitive status as typed are not sent
            self.assertNotIn(typed, user)
        self.assertIn('<passage id="lower_limb_amputation_va_dod_cpg_2024-0901"', user)
        self.assertEqual(set(topics(schema)), {"functional_level", "knee"})  # only topics with passages are asked

    def test_section_without_passages_says_the_search_found_none(self):
        # Never "the sources say nothing": only what code knows (here, no passage was found).
        page = self.review(amputation_level="transfemoral", k_level="K3")
        self.assertRegex(page, r"Foot and ankle\s+The search found no passage for this section\.")
        self.assertNotIn("say nothing", page)

    def test_section_the_ai_left_empty_lists_the_passages(self):
        self.app.config["RAG_WRITER"] = FakeWriter({"items": []})  # answers, but reports nothing
        page = self.review(amputation_level="transfemoral", k_level="K2")
        self.assertRegex(page, r"Knee unit\s+No AI summary for this section: the AI reported nothing from the "
                               r"passages the search found\. Check them below\.\s+Passages the search found for "
                               r"this section, not summarised \(1\)\s+For prosthetic ambulators, we suggest")

    def test_the_model_that_answered_is_named(self):
        page = self.review(amputation_level="transfemoral", k_level="K2")
        self.assertIn(f"AI summaries on this page were written by fake-model (prompt version {PROMPT_VERSION}).",
                      page)
        self.assertIn("Research prototype, not validated for clinical use.", page)  # the disclaimer

    def test_a_licensed_source_is_credited_under_its_citation(self):
        licensed = catalogued_passage("phantom_limb_pain_review_2020-0901",
                            "Prosthetic socket fit affects residual limb pain and the comfort of daily wear.", 4)
        with patch("reasoning.pathway.retrieve_relevant_chunks",
                   side_effect=lambda case: {**fake_retrieval(case), "socket": [licensed]}):
            page = self.review(amputation_level="transfemoral", k_level="K2")
        authors, licence = attributions()["phantom_limb_pain_review_2020"]
        self.assertEqual(licence, "CC BY 4.0")
        self.assertIn(f"{authors}; licence: {licence}", page)
        # A US federal work records no licence: nothing is added under the knee statement's citation.
        self.assertRegex(page, r"VA/DoD [^\n]*\(2024\), p\. 56\s+\S")
        self.assertNotRegex(page, r"VA/DoD [^\n]*\(2024\), p\. 56\s+[^\n]*licence:")

    def test_no_model_named_without_the_ai(self):
        self.app.config["RAG_WRITER"] = FakeWriter(error="offline")
        page = self.review(amputation_level="transfemoral", k_level="K2")
        self.assertNotIn("were written by", page)

    def test_without_the_ai_the_passages_are_listed_and_the_reason_shown(self):
        self.app.config["RAG_WRITER"] = FakeWriter(error="no Claude API key: set ANTHROPIC_API_KEY")
        page = self.review(amputation_level="transfemoral", k_level="K2")
        for part in ("the information gaps", "the functional level and components", "design and fitting"):
            self.assertIn(f"AI summaries are not available for {part}: no Claude API key: set ANTHROPIC_API_KEY "
                          "The passages the search found are listed without summaries.", page)
        self.assertRegex(page, r"Knee unit\s+Passages the search found for this section, not summarised \(1\)\s+"
                               r"For prosthetic ambulators, we suggest")
        self.assertNotIn("AI summary", page)
        # The gaps fall back to the search and topic-word check.
        gap = next(g for g in store.all()[-1].gaps if g.field == "residual_limb.volume_stability")
        self.assertEqual(gap.excerpt, VOLUME_PASSAGE.text)
        self.assertIsNone(gap.summary_en)

    def test_a_misquote_is_removed_and_counted(self):
        def answer(user, schema):
            topics = schema["properties"]["items"]["items"]["properties"]["topic"]["enum"]
            if "knee" not in topics:
                return {"items": []}
            return {"items": [{"topic": "knee", "passage_id": KNEE_PASSAGE.chunk_id,
                               "quote": "we strongly recommend microprocessor knee units for everyone",
                               "sentence_en": "Made up.", "sentence_ar": "مختلق.", "grade": "Strong for"}]}
        self.app.config["RAG_WRITER"] = FakeWriter(answer)
        page = self.review(amputation_level="transfemoral", k_level="K2")
        self.assertIn("1 AI summary or summaries removed by the checks (for example, a quote not found word for "
                      "word in its passage); each reason is kept in the log.", page)
        self.assertNotIn("Made up.", page)
        self.assertRegex(page, r"Knee unit\s+No AI summary for this section: the checks removed the AI's 1 summary "
                               r"or summaries for it \(each reason is kept in the log\)\. Check the passages the "
                               r"search found below\.\s+Passages the search found for this section, not "
                               r"summarised \(1\)\s+For prosthetic ambulators, we suggest")
        [removed] = store.all()[-1].generation.part("components").removed
        self.assertEqual(removed["reason"], "quote not found word for word in the passage")

    def test_a_quote_shown_under_an_earlier_section_is_not_shown_again(self):
        # The fake writer quotes the same words for the knee and for alignment: shown once, and said why.
        with patch("reasoning.pathway.retrieve_relevant_chunks",
                   side_effect=lambda case: {**fake_retrieval(case), "alignment": [KNEE_PASSAGE]}):
            page = self.review(amputation_level="transfemoral", k_level="K2")
        self.assertRegex(page, r"Alignment\s+No AI summary for this section: the AI gave it only a quote that is "
                               r"already shown under an earlier section\. Check the passages the search found below\.")
        self.assertEqual(page.count("AI sentence about knee."), 1)
        self.assertNotIn("AI sentence about alignment.", page)
        self.assertNotIn("removed by the checks", page)  # not a failed check

    def test_upper_limb(self):
        page = self.review(amputation_level="transradial")
        self.assertIn("K-levels describe the intended use of a lower-limb prosthesis", page)
        self.assertRegex(page, r"(?s)Type of prosthesis\s+.*AI sentence about prosthesis_type\.\s+For patients with "
                               r"a major unilateral upper limb")
        self.assertNotIn("Recorded K-level", page)
        self.assertNotIn("Knee unit", page)

    def test_statement_judgements_logged(self):
        self.post_intake(amputation_level="transfemoral", k_level="K3")
        record = store.all()[-1]
        case_id, knee = record.case.case_id, self.knee_id()
        functional = record.components.functional_section.statements[0].statement.id
        resp = self.client.post(f"/review/{case_id}/decision", follow_redirects=True, data={
            "decision": "approve", f"opt:{knee}": "relevant", f"opt:{functional}": "not_relevant"})
        self.assertEqual(resp.status_code, 200)
        [entry] = read_decisions(case_id, path=self.log_path)
        statements = {s["id"]: s for section in entry["components"]["sections"] for s in section["statements"]}
        self.assertEqual(statements[knee]["reviewer_judgement"], "relevant")
        self.assertEqual(statements[functional]["reviewer_judgement"], "not_relevant")
        self.assertEqual(statements[knee]["origin"], "rag")
        self.assertEqual(statements[knee]["summary_en"], "AI sentence about knee.")
        self.assertEqual(statements[knee]["chunk_id"], KNEE_PASSAGE.chunk_id)
        self.assertEqual(statements[knee]["passage"], KNEE_PASSAGE.text)
        self.assertEqual(statements[knee]["quote"], "For prosthetic ambulators, we suggest prescribing microprocessor knee")
        self.assertEqual(entry["generation"]["parts"]["components"]["status"], "ok")
        self.assertEqual(entry["generation"]["parts"]["components"]["model"], "fake-model")
        self.assertIn("; components: 1 relevant, 1 not relevant", visible_text(resp.get_data(as_text=True)))

    def test_bad_statement_judgements_refused(self):
        self.post_intake(amputation_level="transfemoral", k_level="K3")
        case_id = store.all()[-1].case.case_id
        for data, message in [
            ({"opt:made_up_statement": "relevant"}, "is not one of the statements shown"),
            ({"opt:va_dod_ll_17_microprocessor_knee": "relevant"}, "is not one of the statements shown"),  # hand-written
            ({f"opt:{self.knee_id()}": "maybe"}, "Unknown judgement 'maybe'"),
        ]:
            with self.subTest(**data):
                resp = self.client.post(f"/review/{case_id}/decision", data={"decision": "approve", **data})
                self.assertEqual(resp.status_code, 400)
                self.assertIn(message, visible_text(resp.get_data(as_text=True)))
        self.assertEqual(read_decisions(path=self.log_path), [])

    def test_refused_form_keeps_statement_choices(self):
        self.post_intake(amputation_level="transfemoral", k_level="K3")
        case_id, knee = store.all()[-1].case.case_id, self.knee_id()
        resp = self.client.post(f"/review/{case_id}/decision", data={"decision": "edit", f"opt:{knee}": "not_relevant"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn(f'name="opt:{knee}" value="not_relevant" checked', resp.get_data(as_text=True))


class FittingRouteTests(ProstheticRouteTestCase):
    """The design and fitting section of the review page (the RAG)."""

    def review(self, **fields) -> str:
        resp = self.post_intake(**fields)
        return visible_text(self.client.get(resp.headers["Location"]).get_data(as_text=True))

    def test_transtibial(self):
        page = self.review()
        fitting = store.all()[-1].fitting
        self.assertIn(f"What the sources say about design and fitting ({len(fitting.statements)} statements)", page)
        self.assertIn("They do not say whether this patient is ready", page)
        self.assertIn("Socket, interface and suspension are listed with the components above.", page)
        for heading in ("Readiness for fitting", "Preparatory or definitive prosthesis",
                        "Fitting, check-out and follow-up", "Alignment"):
            self.assertIn(heading, page)
        self.assertRegex(page, r"AI sentence about readiness\.\s+Those who are ready for fitting are free\s+"
                               r"Prosthetic Gait Analysis for Physiotherapists[^\n]*\(2014\), p\. 49")
        self.assertIn("professional knowledge (manual)", page)  # shown as what it is: a manual
        self.assertRegex(page, r"Alignment\s+The search found no passage for this section\.")
        raw = self.client.get(f"/review/{store.all()[-1].case.case_id}").get_data(as_text=True)
        readiness = fitting.sections[0].statements[0].statement.id
        self.assertTrue(readiness.startswith("rag-readiness-"))
        self.assertIn(f'name="opt:{readiness}" value="relevant"', raw)

    def test_recorded_values_shown_as_entered(self):
        page = self.review(wound_status="open", volume_stability="fluctuating", skin_condition="adherent scar",
                           comorbidities="none", months_since_amputation="3")
        self.assertRegex(page, r"Recorded at intake for this case \(as entered, not judged\):\s+"
                               r"Time since amputation\s*3 months\s+Residual limb wound status\s*open\s+"
                               r"Residual limb volume stability\s*fluctuating\s+"
                               r"Residual limb skin condition\s*adherent scar")
        self.assertRegex(page, r"Comorbidities\s*none reported")
        self.assertRegex(page, r"Cognitive status\s*not recorded")

    def test_upper_limb_gets_every_fitting_section(self):
        page = self.review(amputation_level="transradial")
        for heading in ("Readiness for fitting", "Preparatory or definitive prosthesis",
                        "Fitting, check-out and follow-up", "Alignment"):
            self.assertIn(heading, page)

    def test_fitting_judgements_logged(self):
        self.post_intake(amputation_level="transfemoral")
        record = store.all()[-1]
        case_id = record.case.case_id
        readiness = record.fitting.sections[0].statements[0].statement.id
        knee = next(c.statement.id for c in record.components.statements if c.statement.component == "knee")
        resp = self.client.post(f"/review/{case_id}/decision", follow_redirects=True, data={
            "decision": "approve", f"opt:{readiness}": "relevant",
            f"opt:{knee}": "relevant",  # a component statement, same form
        })
        self.assertEqual(resp.status_code, 200)
        [entry] = read_decisions(case_id, path=self.log_path)
        marks = {s["id"]: s["reviewer_judgement"]
                 for section in entry["fitting"]["sections"] for s in section["statements"]}
        self.assertEqual(marks, {readiness: "relevant"})
        self.assertIn("; design and fitting: 1 relevant", visible_text(resp.get_data(as_text=True)))

    def test_arabic_headings_and_ai_sentence_quotes_in_english(self):
        self.client.set_cookie("lang", "ar")
        page = self.review(comorbidities="لا يوجد")
        self.assertIn("ما تقوله المصادر عن التصميم والتركيب", page)
        self.assertIn("الجاهزية للتركيب", page)
        self.assertIn("المحاذاة", page)
        self.assertRegex(page, r"الأمراض المصاحبة\s*لا يوجد")
        self.assertIn("معرفة مهنية (دليل تدريبي)", page)
        self.assertIn("ملخص بالذكاء الاصطناعي — قارنه بالاقتباس أدناه:جملة الذكاء الاصطناعي عن readiness.", page)
        self.assertIn("Those who are ready for fitting", page)  # the source's own words
        self.assertNotIn("AI sentence about readiness", page)
        self.assertNotIn("Readiness for fitting", page)


class ArabicPageTests(ProstheticRouteTestCase):
    """The same pages with the language cookie set to Arabic."""

    def setUp(self):
        super().setUp()
        self.client.set_cookie("lang", "ar")

    def review_page(self, **fields) -> str:
        resp = self.post_intake(**fields)
        return visible_text(self.client.get(resp.headers["Location"]).get_data(as_text=True))

    def test_intake_form_is_arabic_right_to_left(self):
        page = self.client.get("/intake").get_data(as_text=True)
        self.assertIn('<html lang="ar" dir="rtl">', page)
        self.assertIn("إدخال حالة جديدة", page)
        self.assertIn("مستوى البتر", page)
        # Shown in Arabic, but the value sent is still the stored code.
        self.assertIn('<option value="transtibial">بتر تحت الركبة</option>', page)
        self.assertIn('<option value="yes">نعم</option>', page)
        self.assertIn('name="switch_language" value="en"', page)  # the language button posts the form
        self.assertNotIn("New Case Intake", page)

    def test_review_page_is_arabic_with_sources_untranslated(self):
        page = self.review_page()
        self.assertIn("مراجعة الحالة", page)
        self.assertIn("ثبات حجم الطرف المتبقي", page)  # gap label
        self.assertIn("لم يُسجَّل البند «ثبات حجم الطرف المتبقي» عند إدخال الحالة.", page)
        self.assertIn("يتناول المصدر المذكور أدناه هذا الموضوع (انظر الاقتباس)", page)
        self.assertIn("لم يُستشهد بأي مصدر.", page)
        self.assertIn("قد تكون القوائم غير مكتملة", page)  # the disclaimer
        # The quote and citation stay in the source's own words.
        self.assertIn("Residual limb volume should be stable before the definitive socket is cast.", page)
        self.assertIn("Test Guideline (2024), p. 14", page)
        self.assertIn("إنجليزي · التشابه 0.71", page)
        self.assertNotIn("was not recorded at intake", page)
        self.assertNotIn("The lists may be incomplete", page)

    def test_component_sections_in_arabic_with_quotes_in_english(self):
        page = self.review_page(amputation_level="transfemoral", k_level="K3")
        self.assertIn("المستوى الوظيفي والأهداف", page)
        self.assertIn("المستوى الوظيفي المسجَّل (K): K3", page)
        self.assertIn("ما تقوله المصادر عن المستوى الوظيفي:", page)
        self.assertIn("ما تقوله المصادر عن المكوّنات", page)
        self.assertIn("وحدة الركبة", page)
        self.assertRegex(page, r"درجة التوصية في المصدر: غير محددة\s+دليل إرشادي أو بروتوكول")
        self.assertIn("جملة الذكاء الاصطناعي عن knee.", page)  # the AI's Arabic sentence
        self.assertIn("For prosthetic ambulators, we suggest prescribing microprocessor knee", page)  # the quote
        self.assertNotIn("AI sentence about knee", page)
        self.assertNotIn("Knee unit", page)
        self.assertNotIn("Source grade", page)

    def test_ai_unavailable_explained_in_arabic(self):
        self.app.config["RAG_WRITER"] = FakeWriter(error="the Claude API could not be reached (offline?)")
        page = self.review_page(amputation_level="transfemoral")
        self.assertIn("ملخصات الذكاء الاصطناعي غير متاحة لقسم المستوى الوظيفي والمكوّنات. التفاصيل التقنية: "
                      "the Claude API could not be reached (offline?) تُعرض المقاطع التي وجدها البحث دون ملخصات.", page)

    def test_arabic_case_values(self):
        page = self.review_page(etiology="trauma", device_1_description="PTB socket",
                                device_1_years="2", device_1_current="yes")
        self.assertIn("بتر تحت الركبة", page)
        self.assertIn("أيسر", page)
        self.assertIn("رضّي (إصابة)", page)
        self.assertIn("PTB socket · سنوات الاستخدام: 2.0 · قيد الاستخدام", page)

    def test_missing_source_library_is_explained_in_arabic(self):
        with patch("reasoning.pathway.retrieve_relevant_chunks",
                   side_effect=KnowledgeBaseMissing("No vector store.")):
            page = self.review_page()
        self.assertIn("لم يُبحث في مكتبة المصادر. التفاصيل التقنية: "
                      "The source library was not searched: No vector store.", page)

    def test_intake_errors_in_arabic(self):
        for fields, message in [
            ({"device_2_years": "3"}, "الجهاز السابق 2: صِف الجهاز نفسه، لا تفاصيله فقط"),
            ({"no_prior_devices": "1", "device_1_description": "socket"},
             "خيار «لا يوجد طرف اصطناعي سابق» محدَّد، لكن وُصف جهاز"),
            ({"device_1_description": "socket", "device_1_current": "maybe"},
             "الجهاز السابق 1: القيمة المتوقعة «نعم» أو «لا»، والمُرسَلة «maybe»"),
            ({"side": ""}, "الجانب مطلوب"),
        ]:
            with self.subTest(**fields):
                resp = self.post_intake(**fields)
                self.assertEqual(resp.status_code, 400)
                page = visible_text(resp.get_data(as_text=True))
                self.assertIn("لم تُحفظ الحالة: " + message, page)
                self.assertNotIn("Case not saved", page)

    def test_number_error_in_arabic(self):
        # The browser's number input prevents this; if it happens, the message is Arabic too.
        resp = self.post_intake(age_years="abc")
        self.assertEqual(resp.status_code, 400)
        page = visible_text(resp.get_data(as_text=True))
        self.assertIn("لم تُحفظ الحالة: العمر (بالسنوات): أدخل عدداً صحيحاً.", page)
        self.assertNotIn("invalid literal", page)

    def test_comorbidities_none_in_arabic(self):
        self.post_intake(comorbidities="لا يوجد")
        record = store.all()[-1]
        self.assertEqual(record.case.comorbidities, [])
        self.assertNotIn("comorbidities", [g.field for g in record.gaps])

    def test_decision_logged_in_english_with_the_page_language(self):
        self.post_intake()
        record = store.all()[-1]
        case_id = record.case.case_id
        resp = self.client.post(
            f"/review/{case_id}/decision", follow_redirects=True,
            data={"decision": "edit", "note": "يجب قياس حجم الطرف",
                  "gap:residual_limb.volume_stability": "needed"},
        )
        page = visible_text(resp.get_data(as_text=True)).replace("\u2068", "").replace("\u2069", "")
        self.assertIn(f"حُفظ القرار في سجل المراجعة: تعديل (مطلوب: 1، بلا تحديد: 16؛ المكوّنات: بلا تحديد: "
                      f"{len(record.components.statements)}؛ التصميم والتركيب: بلا تحديد: "
                      f"{len(record.fitting.statements)})", page)
        self.assertIn("القرارات المسجلة لهذه الحالة (1)", page)
        [entry] = read_decisions(case_id, path=self.log_path)
        self.assertEqual((entry["decision"], entry["ui_language"]), ("edit", "ar"))
        volume = next(g for g in entry["gaps"] if g["field"] == "residual_limb.volume_stability")
        self.assertEqual(volume["label"], "Residual limb volume stability")  # the log stays English
        self.assertTrue(volume["why_needed"].startswith("Residual limb volume stability was not recorded"))

    def test_decision_errors_in_arabic(self):
        self.post_intake()
        case_id = store.all()[-1].case.case_id
        resp = self.client.post(f"/review/{case_id}/decision", data={"decision": "edit"})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("لم يُحفظ القرار: التعديل يحتاج إلى ملاحظة توضح ما الذي يجب تغييره.",
                      visible_text(resp.get_data(as_text=True)))
        self.assertEqual(read_decisions(path=self.log_path), [])


class LanguageSwitchTests(ProstheticRouteTestCase):
    def test_switch_sets_cookie_and_returns_to_the_page(self):
        resp = self.client.get("/language/ar?next=/review/abc123")
        self.assertEqual(resp.status_code, 302)
        self.assertEqual(resp.headers["Location"], "/review/abc123")
        self.assertIn("lang=ar", resp.headers["Set-Cookie"])
        self.assertIn('dir="rtl"', self.client.get("/intake").get_data(as_text=True))
        self.client.get("/language/en?next=/intake")
        self.assertIn('dir="ltr"', self.client.get("/intake").get_data(as_text=True))

    def test_only_pages_of_this_app(self):
        for target in ["//evil.example/x", "https://evil.example", "/\\evil.example", "evil", ""]:
            with self.subTest(target=target):
                resp = self.client.get("/language/ar", query_string={"next": target})
                self.assertEqual(resp.headers["Location"], "/")

    def test_unknown_language(self):
        resp = self.client.get("/language/fr?next=/intake")
        self.assertEqual(resp.status_code, 404)
        self.assertNotIn("Set-Cookie", resp.headers)
        self.client.set_cookie("lang", "fr")  # e.g. an old or edited cookie
        self.assertIn('<html lang="en" dir="ltr">', self.client.get("/intake").get_data(as_text=True))


if __name__ == "__main__":
    unittest.main()

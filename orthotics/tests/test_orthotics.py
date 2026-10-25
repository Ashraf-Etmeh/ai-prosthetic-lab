"""Tests for orthotics (use case 03, stroke AFO; added 2026-10-22).

The case model, its field guide and topics, the domain-filtered search, the
orthotic AI instructions (what the writer may see), the case store and review
log, and the orthotic intake and review pages in English and Arabic. Like the
other tests: no model load, never the API (shared/testing.py fakes both).
"""

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np

from knowledge.models import ProtocolChunk
from knowledge.retrieval import VectorStore, domains_for, retrieve_relevant_chunks
from orthotics.case import GaitDeviation, OrthoticCase, OrthoticExam, Walking
from orthotics.fields import FIELDS as ORTHOTIC_FIELDS
from orthotics.rag import PROFILE, PROMPT_VERSION as ORTHOTIC_PROMPT_VERSION, RECORDED_FIELDS, case_for_prompt
from orthotics.topics import DESIGN_FITTING, DESIGN_SECTIONS, DEVICE_SECTIONS, DEVICES, topics_for_case
from prosthetics.case import Case
from prosthetics.rag import PROFILE as PROSTHETICS
from reasoning.pathway import analyse_case
from orthotics.rag import AI_OFF as ORTHOTIC_AI_OFF
from reasoning.rag import generate, profile_for
from reasoning.rag_topics import GAPS
from reasoning.writer import ClaudeWriter, GeminiWriter, WriterUnavailable
from review.decision_log import build_entry, record_decision
from review.routes import judgement_summary
from shared.case_schema import PriorDevice, case_from_dict
from shared.config import PROMPT_VERSION
from shared.field_guide import NOT_RECORDED, RECORDED_UNKNOWN, build_query, missing_fields
from shared.store import CaseStore, store
from shared.testing import FakeWriter, RouteTestCase, chunk_record, fake_embed, visible_text


def full_case(**changes) -> OrthoticCase:
    """A fake stroke case with every orthotic gap field filled in."""
    values = dict(
        condition="stroke", side="left", months_since_onset=7, functional_goals="walk outdoors without tripping",
        age_years=61, body_weight_kg=74, comorbidities=["hypertension"], cognitive_status="intact",
        walking=Walking(status="independent_with_aid", walking_aid="quad cane", gait_speed_m_s=0.42,
                        gait_speed_test="10-metre walk test", falls_last_6_months=2,
                        deviations=["toe_drag", "knee_hyperextension"]),
        exam=OrthoticExam(dorsiflexion_knee_extended_deg=-5, dorsiflexion_knee_flexed_deg=10,
                          plantarflexor_tone_scale="modified_ashworth", plantarflexor_tone_grade="1+",
                          dorsiflexor_strength="MRC 2/5", knee_extensor_strength="MRC 4/5",
                          knee_in_stance="hyperextends", foot_posture="equinovarus, flexible",
                          protective_sensation="reduced", proprioception="intact", skin_condition="intact"),
        footwear="closed trainers", donning="needs_help", prior_orthoses=[],
        requirements=["clear the toes in swing", "control knee hyperextension"],
    )
    values.update(changes)
    return OrthoticCase(**values)


def passage(chunk_id: str, text: str, page: int = 3) -> ProtocolChunk:
    return ProtocolChunk(chunk_id=chunk_id, text=text, source="01_guidelines/test.pdf", title="Orthotic source",
                         year=2024, page=page, end_page=page, language="en", score=0.7)


ONSET_PASSAGE = passage("stroke_rehabilitation_va_dod_cpg_2024-0001",
                        "In chronic stroke an ankle-foot orthosis can improve walking speed and balance.")
AFO_PASSAGE = passage("afo_stroke_walking_review_2021-0001",
                      "Wearing an ankle-foot orthosis improved walking speed, cadence and step length after stroke.")
DESIGN_PASSAGE = passage("afo_manufacturing_icrc_2010-0001",
                         "The trim line of a rigid orthosis is placed in front of the malleoli.")


def orthotic_retrieval(case):
    """Stands in for the real search for an orthotic case."""
    return {"months_since_onset": [ONSET_PASSAGE], "afo_or_fes": [AFO_PASSAGE], "design": [DESIGN_PASSAGE]}


class SchemaTests(unittest.TestCase):
    def test_round_trip_names_its_domain(self):
        case = full_case()
        data = case.to_dict()
        self.assertEqual(data["domain"], "orthotics")
        self.assertEqual(data["walking"]["deviations"], ["toe_drag", "knee_hyperextension"])
        back = case_from_dict(json.loads(json.dumps(data)))
        self.assertIsInstance(back, OrthoticCase)
        self.assertEqual(back.to_dict(), data)

    def test_a_prosthetics_dict_still_has_no_domain(self):
        self.assertNotIn("domain", Case(amputation_level="transtibial", side="left").to_dict())

    def test_angles_are_signed_but_bounded(self):
        self.assertEqual(OrthoticExam(dorsiflexion_knee_extended_deg=-5).dorsiflexion_knee_extended_deg, -5)
        with self.assertRaises(ValueError):
            OrthoticExam(dorsiflexion_knee_extended_deg=120)

    def test_a_tone_grade_needs_its_scale(self):
        with self.assertRaises(ValueError):
            OrthoticExam(plantarflexor_tone_grade="2")

    def test_a_gait_speed_needs_its_test(self):
        with self.assertRaises(ValueError):
            Walking(gait_speed_m_s=0.5)

    def test_deviations_know_their_phase(self):
        self.assertEqual(GaitDeviation.TOE_DRAG.phase, "swing")
        self.assertEqual(GaitDeviation.KNEE_HYPEREXTENSION.phase, "mid_stance")

    def test_full_case_has_no_gap(self):
        self.assertEqual(missing_fields(full_case()), [])


class FieldGuideTests(unittest.TestCase):
    def test_blank_case_lists_every_orthotic_field_in_order(self):
        blank = OrthoticCase(condition="stroke", side="right")
        self.assertEqual([m.info.path for m in missing_fields(blank)], [info.path for info in ORTHOTIC_FIELDS])
        self.assertTrue(all(m.status == NOT_RECORDED for m in missing_fields(blank)))

    def test_unknown_answer_is_its_own_status(self):
        case = full_case(exam=OrthoticExam(protective_sensation="unknown"))
        statuses = {m.info.path: m.status for m in missing_fields(case)}
        self.assertEqual(statuses["exam.protective_sensation"], RECORDED_UNKNOWN)

    def test_query_is_the_fields_own_wording(self):
        # The side and months since onset cost right passages (FUTURE_WORK.md, orthotics).
        info = ORTHOTIC_FIELDS[0]
        self.assertEqual(build_query(full_case(), info), info.query)

    def test_topic_terms_in_each_language(self):
        sensation = next(i for i in ORTHOTIC_FIELDS if i.path == "exam.protective_sensation")
        self.assertTrue(sensation.mentions_topic("Check protective sensation with a monofilament.", "en"))
        self.assertTrue(sensation.mentions_topic("فحص الإحساس في القدم", "ar"))
        tone = next(i for i in ORTHOTIC_FIELDS if i.path == "exam.plantarflexor_tone_grade")
        self.assertTrue(tone.mentions_topic("Spastik der Wadenmuskulatur", "de"))
        self.assertFalse(tone.mentions_topic("The orthosis is made of polypropylene.", "en"))

    def test_look_alike_words_are_not_the_topic(self):
        # Found in the NICE FES guidance, which the gap search cited for both fields before 2026-10-22.
        sensation = next(i for i in ORTHOTIC_FIELDS if i.path == "exam.protective_sensation")
        skin = next(i for i in ORTHOTIC_FIELDS if i.path == "exam.skin_condition")
        self.assertFalse(sensation.mentions_topic("35 patients treated by conventional therapy (absolute numbers "
                                                  "not given)", "en"))
        self.assertTrue(sensation.mentions_topic("Numbness of the foot.", "en"))
        self.assertFalse(skin.mentions_topic("In skin surface FES, electrodes placed over the nerve", "en"))
        self.assertTrue(skin.mentions_topic("EVA may be moulded to prevent skin breakage.", "en"))


class TopicTests(unittest.TestCase):
    def test_parts_and_order(self):
        case = full_case(footwear=None)
        topics = topics_for_case(case)
        self.assertEqual([t.key for t in topics if t.part == GAPS], ["footwear"])
        self.assertEqual([t.key for t in topics if t.part == DEVICES], list(DEVICE_SECTIONS))
        self.assertEqual([t.key for t in topics if t.part == DESIGN_FITTING], list(DESIGN_SECTIONS))
        for topic in topics:
            self.assertNotIn("left", topic.query)

    def test_keys_never_clash_with_prosthetic_topics_or_fields(self):
        from prosthetics.component_guide import COMPONENT_KEYS
        from prosthetics.fitting_guide import SECTION_KEYS
        prosthetic = set(COMPONENT_KEYS) | set(SECTION_KEYS) | {"functional_level"}
        orthotic = set(DEVICE_SECTIONS) | set(DESIGN_SECTIONS)
        self.assertEqual(orthotic & prosthetic, set())
        self.assertEqual(orthotic & {info.path for info in ORTHOTIC_FIELDS}, set())

    def test_the_shared_entry_point_dispatches(self):
        from reasoning.rag_topics import topics_for_case as shared_topics
        self.assertEqual(shared_topics(full_case()), topics_for_case(full_case()))


class RetrievalTests(unittest.TestCase):
    def setUp(self):
        chunks = [
            chunk_record("prosthetic_doc-0001", "ankle foot orthosis stroke walking", domains=("prosthetics",)),
            chunk_record("orthotic_doc-0001", "ankle foot orthosis stroke walking", domains=("orthotics",),
                         limbs=("lower",)),
            chunk_record("upper_orthotic_doc-0001", "ankle foot orthosis stroke walking", domains=("orthotics",),
                         limbs=("upper",)),
        ]
        self.store = VectorStore(fake_embed([c["text"] for c in chunks]), chunks)

    def test_an_orthotic_case_searches_only_lower_limb_orthotic_documents(self):
        found = retrieve_relevant_chunks(full_case(footwear=None), store=self.store, embed=fake_embed)
        docs = {chunk.chunk_id.rsplit("-", 1)[0] for chunks in found.values() for chunk in chunks}
        self.assertEqual(docs, {"orthotic_doc"})
        self.assertIn("afo_or_fes", found)
        self.assertIn("footwear", found)

    def test_a_prosthetic_case_never_searches_orthotic_documents(self):
        case = Case(amputation_level="transtibial", side="left")
        found = retrieve_relevant_chunks(case, store=self.store, embed=fake_embed)
        docs = {chunk.chunk_id.rsplit("-", 1)[0] for chunks in found.values() for chunk in chunks}
        self.assertEqual(docs, {"prosthetic_doc"})
        self.assertEqual(domains_for(case), ("prosthetics",))
        self.assertEqual(domains_for(full_case()), ("orthotics",))


class RagTests(unittest.TestCase):
    def test_profiles(self):
        self.assertIs(profile_for(full_case()), PROFILE)
        self.assertIs(profile_for(Case(amputation_level="syme", side="left")), PROSTHETICS)
        self.assertEqual(PROSTHETICS.prompt_version, PROMPT_VERSION)
        self.assertEqual(PROFILE.parts, (GAPS, DEVICES, DESIGN_FITTING))

    def test_the_writer_sees_no_typed_text(self):
        case = full_case(functional_goals="SECRET-GOAL", intake_notes="SECRET-NOTE", footwear=None,
                         requirements=["SECRET-REQUIREMENT"], cognitive_status="SECRET-COGNITION")
        self.assertEqual(json.loads(case_for_prompt(case)),
                         {"condition": "stroke", "limb": "lower", "affected_side": "left", "months_since_onset": 7})
        writer = FakeWriter()
        generate(case, orthotic_retrieval(case) | {"footwear": [AFO_PASSAGE]}, writer)
        self.assertEqual(len(writer.calls), 3)
        for system, user, _ in writer.calls:
            self.assertNotIn("SECRET", system + user)
            self.assertIn("condition, affected side and months since onset only", user)

    def test_instructions_keep_the_source_strength_and_the_page_terms(self):
        from orthotics.rag import ARABIC_TERMS
        from reasoning.rag import FAITHFULNESS
        from reasoning.tests.test_rag import page_arabic

        self.assertEqual(ORTHOTIC_PROMPT_VERSION, "rag-ort-v2")
        self.assertIn(FAITHFULNESS, PROFILE.system_prompt)
        page = page_arabic()
        for english, arabic in ARABIC_TERMS:
            with self.subTest(english):
                self.assertIn(f"{english} = {arabic}", PROFILE.system_prompt)
                self.assertIn(arabic, page)

    def test_instructions_forbid_advice(self):
        prompt = PROFILE.system_prompt
        self.assertIn("never advise", prompt)
        self.assertIn("whether this patient should have an orthosis or FES", prompt)
        self.assertIn("set angles, materials, trim lines or wearing times", prompt)

    def test_generate_asks_the_three_orthotic_parts(self):
        case = full_case(months_since_onset=None)
        generation = generate(case, orthotic_retrieval(case), FakeWriter())
        self.assertEqual(generation.prompt_version, ORTHOTIC_PROMPT_VERSION)
        self.assertEqual(set(generation.parts), {GAPS, DEVICES, DESIGN_FITTING})
        self.assertEqual([item.topic for item in generation.part(DEVICES).items], ["afo_or_fes"])

    def test_record_shapes(self):
        case = full_case(months_since_onset=None)
        record = analyse_case(case, retrieve=orthotic_retrieval, writer=FakeWriter())
        self.assertIsNone(record.components.functional)
        self.assertEqual([s.component for s in record.components.sections], list(DEVICE_SECTIONS))
        self.assertEqual([s.component for s in record.fitting.sections], list(DESIGN_SECTIONS))
        self.assertEqual([path for path, _ in record.fitting.recorded], list(RECORDED_FIELDS))
        self.assertEqual(dict(record.fitting.recorded)["exam.dorsiflexion_knee_extended_deg"], -5)
        [gap] = record.gaps
        self.assertEqual((gap.field, gap.summary_en), ("months_since_onset", "AI sentence about months_since_onset."))
        afo = record.components.sections[0].statements[0]
        self.assertEqual(afo.summary_en, "AI sentence about afo_or_fes.")

    def test_without_the_ai_the_gaps_fall_back_to_the_topic_check(self):
        case = full_case(months_since_onset=None)
        record = analyse_case(case, retrieve=orthotic_retrieval, writer=FakeWriter(error="no key"))
        [gap] = record.gaps
        self.assertEqual(gap.evidence.chunk_id, ONSET_PASSAGE.chunk_id)  # "chronic" is a topic word
        self.assertIsNone(gap.summary_en)


class CloudSwitchTests(unittest.TestCase):
    """Owner's decision 2026-10-23: no orthotic case reaches a cloud API while ORTHOTIC_CLOUD_AI is off."""

    def setUp(self):
        self.calls = []
        for cls in (GeminiWriter, ClaudeWriter):  # record the call instead of sending anything
            patcher = patch.object(cls, "write", autospec=True,
                                   side_effect=lambda *args: self.calls.append(args) or _raise("API called"))
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_an_orthotic_case_never_reaches_a_cloud_writer(self):
        case = full_case(months_since_onset=None)
        for writer in (GeminiWriter(), ClaudeWriter()):
            with self.subTest(writer.name):
                generation = generate(case, orthotic_retrieval(case), writer)
                self.assertEqual(self.calls, [])
                self.assertEqual(generation.writer, "offline")
                self.assertEqual({part.reason for part in generation.parts.values()}, {ORTHOTIC_AI_OFF})
                record = analyse_case(case, retrieve=orthotic_retrieval, writer=writer)
                self.assertEqual(self.calls, [])
                self.assertEqual(record.gaps[0].evidence.chunk_id, ONSET_PASSAGE.chunk_id)  # passages still shown

    def test_the_owner_can_switch_it_on(self):
        case = full_case(months_since_onset=None)
        with patch("shared.config.ORTHOTIC_CLOUD_AI", True):
            generate(case, orthotic_retrieval(case), GeminiWriter())
        self.assertEqual(len(self.calls), 3)

    def test_prosthetic_cases_and_test_writers_unchanged(self):
        prosthetic = Case(amputation_level="transtibial", side="left")  # age not recorded: a gap topic
        generate(prosthetic, {"age_years": [ONSET_PASSAGE]}, GeminiWriter())
        self.assertEqual(len(self.calls), 1)
        fake = FakeWriter()
        generate(full_case(months_since_onset=None), orthotic_retrieval(full_case()), fake)
        self.assertEqual(len(fake.calls), 3)


def _raise(reason: str):
    raise WriterUnavailable(reason)


class StoreAndLogTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.folder = Path(tmp.name)
        self.record = analyse_case(full_case(months_since_onset=None), retrieve=orthotic_retrieval,
                                   writer=FakeWriter())

    def test_case_file_round_trip(self):
        CaseStore(self.folder).save(self.record)
        back = CaseStore(self.folder).get(self.record.case.case_id)
        self.assertIsInstance(back.case, OrthoticCase)
        self.assertEqual(back.case.to_dict(), self.record.case.to_dict())
        self.assertEqual([c.statement.id for c in back.shown_statements()],
                         [c.statement.id for c in self.record.shown_statements()])

    def test_log_entry(self):
        afo_id = self.record.components.sections[0].statements[0].statement.id
        entry = record_decision(self.record, "approve", note="Hinged AFO chosen: knee control needed.",
                                path=self.folder / "log.jsonl", statement_judgements={afo_id: "relevant"},
                                gap_judgements={"months_since_onset": "needed"})
        self.assertEqual((entry["log_version"], entry["domain"]), (9, "orthotics"))
        self.assertIsNone(entry["components"]["functional_level"])
        self.assertEqual(entry["settings"]["retrieval_domains"], ["orthotics"])
        self.assertEqual(entry["case"]["domain"], "orthotics")
        self.assertIn("exam.dorsiflexion_knee_extended_deg", entry["fitting"]["recorded"])
        summary = judgement_summary(entry)
        self.assertIn("orthosis and FES: 1 relevant", summary)

    def test_older_entries_read_as_prosthetic(self):
        entry = build_entry(self.record, "approve")
        entry.pop("domain")
        self.assertIn("components:", judgement_summary(entry))


ORTHOTIC_FORM = {"condition": "stroke", "side": "left"}


class OrthoticPageTests(RouteTestCase):
    def setUp(self):
        super().setUp()
        retrieval = patch("reasoning.pathway.retrieve_relevant_chunks", side_effect=orthotic_retrieval)
        retrieval.start()
        self.addCleanup(retrieval.stop)

    def post(self, **fields):
        return self.client.post("/intake/orthotics", data={**ORTHOTIC_FORM, **fields})

    def test_form_in_both_languages(self):
        page = self.client.get("/intake/orthotics").get_data(as_text=True)
        self.assertIn("New Orthotic Case: stroke, ankle-foot orthosis", page)
        self.assertIn("a draft awaiting review by the owner and an orthotist", page)
        self.assertIn('name="deviation" value="toe_drag"', page)
        self.client.set_cookie("lang", "ar")
        page = self.client.get("/intake/orthotics").get_data(as_text=True)
        self.assertIn('dir="rtl"', page)
        self.assertIn("حالة تقويمية جديدة", page)
        self.assertIn("جرّ أصابع القدم", page)

    def test_the_prosthetic_form_links_here(self):
        page = self.client.get("/intake").get_data(as_text=True)
        self.assertIn('href="/intake/orthotics"', page)

    def test_submitted_case_shows_its_review_page(self):
        resp = self.post(months_since_onset="", df_knee_ext="-5", deviation=["toe_drag", "knee_hyperextension"],
                         requirements="clear the toes in swing\ncontrol knee hyperextension",
                         gait_speed_m_s="0.42", gait_speed_test="10-metre walk test")
        self.assertEqual(resp.status_code, 302)
        record = store.all()[-1]
        self.assertIsInstance(record.case, OrthoticCase)
        self.assertEqual(record.case.walking.deviations, [GaitDeviation.TOE_DRAG, GaitDeviation.KNEE_HYPEREXTENSION])
        # The form leads to module 1, the case analysis (the design canvas, 2026-10-23); the review page with what
        # the sources say and the reviewer's marks is one link away.
        self.assertTrue(resp.headers["Location"].endswith(f"/orthotics/{record.case.case_id}/analysis"))
        analysis = visible_text(self.client.get(resp.headers["Location"]).get_data(as_text=True))
        self.assertIn("Functional case analysis", analysis)
        self.assertIn("Toe drag".lower(), analysis.lower())
        page = visible_text(self.client.get(f"/review/{record.case.case_id}").get_data(as_text=True))
        self.assertIn("ankle-foot orthoses and FES", page)  # the orthotic disclaimer
        self.assertIn("What the sources say about ankle-foot orthoses and FES (1)", page)
        self.assertIn("What the sources say about design and fitting (1)", page)
        self.assertIn("AI sentence about afo_or_fes.", page)
        self.assertIn("critical (draft)", page)  # months since onset is a critical (draft) field
        self.assertIn("Swing", page)
        self.assertIn("toe drag", page)
        self.assertIn("clear the toes in swing", page)
        self.assertIn("-5°", page)
        self.assertNotIn("Functional level and goals", page)  # no K-level on an orthotic page
        self.client.set_cookie("lang", "ar")
        page = visible_text(self.client.get(f"/review/{record.case.case_id}").get_data(as_text=True))
        self.assertIn("ما تقوله المصادر عن أجهزة تقويم الكاحل والقدم والتنبيه الكهربائي", page)
        self.assertIn("جملة الذكاء الاصطناعي عن afo_or_fes.", page)
        self.assertIn("حرج (مسوّدة)", page)

    def test_decision_is_logged_with_its_domain(self):
        resp = self.post(months_since_onset="")
        case_id = store.all()[-1].case.case_id
        afo_id = store.all()[-1].components.sections[0].statements[0].statement.id
        resp = self.client.post(f"/review/{case_id}/decision",
                                data={"decision": "approve", "note": "Solid AFO chosen.", f"opt:{afo_id}": "relevant"})
        self.assertEqual(resp.status_code, 302)
        [line] = self.log_path.read_text(encoding="utf-8").splitlines()
        entry = json.loads(line)
        self.assertEqual((entry["domain"], entry["note"]), ("orthotics", "Solid AFO chosen."))

    def test_refusals_are_translated_and_keep_the_form(self):
        cases = [
            ({"tone_grade": "2"}, "needs its scale", "تحتاج إلى مقياسها"),
            ({"gait_speed_m_s": "0.4"}, "needs the test it was measured with", "تحتاج إلى الاختبار"),
            ({"df_knee_ext": "200"}, "enter degrees between -90 and 90", "أدخل عدد الدرجات"),
            ({"no_deviations": "1", "deviation": "toe_drag"}, "deviations are ticked too", "عُلِّمت انحرافات"),
            ({"deviation": "dancing"}, "choose one of the listed options", None),
        ]
        for fields, english, arabic in cases:
            with self.subTest(fields=fields):
                self.client.set_cookie("lang", "en")
                resp = self.post(**fields, footwear="KEEP-ME")
                self.assertEqual(resp.status_code, 400)
                page = resp.get_data(as_text=True)
                self.assertIn(english, visible_text(page))
                self.assertIn("KEEP-ME", page)
                if arabic:
                    self.client.set_cookie("lang", "ar")
                    self.assertIn(arabic, visible_text(self.post(**fields).get_data(as_text=True)))

    def test_switching_language_keeps_the_form_and_saves_nothing(self):
        before = len(store.all())
        resp = self.post(switch_language="ar", footwear="KEEP-ME")
        self.assertEqual(resp.status_code, 200)
        page = resp.get_data(as_text=True)
        self.assertIn('dir="rtl"', page)
        self.assertIn("KEEP-ME", page)
        self.assertEqual(len(store.all()), before)
        self.assertEqual(list(self.cases_dir.glob("*.json")) if self.cases_dir.exists() else [], [])

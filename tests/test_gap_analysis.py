"""Tests for reasoning/gap_analysis.py: which gaps, and which source each cites."""

import unittest

from knowledge.models import ProtocolChunk
from reasoning.gap_analysis import analyze_gaps, explain_gap, find_evidence, topic_excerpt
from shared.case_schema import Case, ResidualLimb
from shared.field_guide import FIELDS_BY_PATH, RECORDED_UNKNOWN, missing_fields

VOLUME = FIELDS_BY_PATH["residual_limb.volume_stability"]


def chunk(chunk_id: str, text: str, score: float, language: str = "en") -> ProtocolChunk:
    return ProtocolChunk(chunk_id, text, "x.pdf", "Guideline", 2024, 12, 12, language, score)


class GapListTests(unittest.TestCase):
    def test_one_gap_per_missing_field_in_guide_order(self):
        case = Case(amputation_level="transtibial", side="left", age_years=60)
        gaps = analyze_gaps(case, {})
        self.assertEqual([g.field for g in gaps], [m.info.path for m in missing_fields(case)])
        self.assertNotIn("age_years", [g.field for g in gaps])
        self.assertEqual(gaps[0].field, "residual_limb.wound_status")

    def test_free_text_notes_are_never_gaps(self):
        fields = [g.field for g in analyze_gaps(Case(amputation_level="syme", side="left"), {})]
        self.assertNotIn("intake_notes", fields)
        self.assertNotIn("residual_limb.notes", fields)

    def test_upper_limb_case_has_no_k_level_gap(self):
        fields = [g.field for g in analyze_gaps(Case(amputation_level="transradial", side="left"), {})]
        self.assertNotIn("activity.k_level", fields)
        self.assertNotIn("contralateral_limb_status", fields)

    def test_unknown_answer_is_a_gap_with_its_own_wording(self):
        case = Case(amputation_level="transtibial", side="left",
                    residual_limb=ResidualLimb(wound_status="unknown"))
        [gap] = [g for g in analyze_gaps(case, {}) if g.field == "residual_limb.wound_status"]
        self.assertEqual(gap.status, RECORDED_UNKNOWN)
        self.assertIn("was recorded as unknown", gap.why_needed)

    def test_no_passages_means_no_source(self):
        gap = analyze_gaps(Case(amputation_level="transtibial", side="left"), {})[0]
        self.assertIsNone(gap.source_protocol_reference)
        self.assertIn("No passage in the source library", gap.why_needed)


class EvidenceTests(unittest.TestCase):
    def test_cites_best_passage_that_mentions_the_topic(self):
        off_topic = chunk("a-0001", "Socket design varies between clinics.", 0.80)
        on_topic = chunk("a-0002", "Limb volume should be stable before casting.", 0.70)
        found, excerpt = find_evidence(VOLUME, [off_topic, on_topic], min_score=0.5)
        self.assertEqual(found.chunk_id, "a-0002")
        self.assertEqual(excerpt, "Limb volume should be stable before casting.")

    def test_low_score_never_cited(self):
        self.assertIsNone(find_evidence(VOLUME, [chunk("a-0001", "Limb volume matters.", 0.30)], 0.5))

    def test_arabic_passage_with_vowel_marks(self):
        found = find_evidence(VOLUME, [chunk("w-0001", "يجب أن يستقر حَجم الطرف.", 0.6, "ar")], 0.5)
        self.assertIsNotNone(found)

    def test_cited_source_is_always_a_retrieved_chunk(self):
        case = Case(amputation_level="transfemoral", side="right")
        retrieved = {
            "residual_limb.volume_stability": [chunk("v-0001", "Volume changes after surgery.", 0.7)],
            "residual_limb.pain": [chunk("p-0001", "Phantom pain is common.", 0.6)],
            "comorbidities": [chunk("c-0001", "Unrelated text.", 0.9)],
        }
        retrieved_ids = {c.chunk_id for chunks in retrieved.values() for c in chunks}
        cited = [g for g in analyze_gaps(case, retrieved, min_score=0.5) if g.source_protocol_reference]
        self.assertEqual({g.source_protocol_reference for g in cited}, {"v-0001", "p-0001"})
        self.assertTrue(all(g.source_protocol_reference in retrieved_ids for g in cited))
        self.assertTrue(all(g.evidence.chunk_id == g.source_protocol_reference for g in cited))

    def test_reason_names_the_source_and_never_recommends(self):
        case = Case(amputation_level="transtibial", side="left")
        retrieved = {"residual_limb.volume_stability": [chunk("v-0001", "Volume changes.", 0.7)]}
        for gap in analyze_gaps(case, retrieved, min_score=0.5):
            self.assertNotIn("recommend", gap.why_needed.lower())
        [gap] = [g for g in analyze_gaps(case, retrieved, 0.5) if g.source_protocol_reference]
        self.assertIn("Guideline (2024), p. 12", gap.why_needed)

    def test_explanation_in_the_reviewers_language(self):
        case = Case(amputation_level="transtibial", side="left",
                    residual_limb=ResidualLimb(wound_status="unknown"))
        retrieved = {"residual_limb.volume_stability": [chunk("v-0001", "Volume changes.", 0.7)]}
        gaps = {g.field: g for g in analyze_gaps(case, retrieved, min_score=0.5)}
        for gap in gaps.values():
            self.assertEqual(explain_gap(gap, "en"), gap.why_needed)  # the logged text
        self.assertEqual(
            explain_gap(gaps["residual_limb.volume_stability"], "ar"),
            "لم يُسجَّل البند «\u2068ثبات حجم الطرف المتبقي\u2069» عند إدخال الحالة. "
            "يتناول المصدر المذكور أدناه هذا الموضوع (انظر الاقتباس)؛ "
            "تحقَّق مما إذا كان ينطبق على هذه الحالة.",
        )
        self.assertTrue(explain_gap(gaps["residual_limb.wound_status"], "ar").startswith(
            "سُجِّل البند «\u2068حالة جرح الطرف المتبقي\u2069» على أنه غير معروف. لم يُعثر"
        ))


class ExcerptTests(unittest.TestCase):
    def test_only_sentences_on_the_topic(self):
        text = "Intro sentence. Volume is checked weekly. Other topic. Edema is reduced by shrinkers."
        self.assertEqual(
            topic_excerpt(VOLUME, chunk("a", text, 0.7)),
            "Volume is checked weekly. … Edema is reduced by shrinkers.",
        )

    def test_adjacent_sentences_joined_plainly(self):
        text = "Volume is checked. Edema is common."
        self.assertEqual(topic_excerpt(VOLUME, chunk("a", text, 0.7)), text)

    def test_long_sentence_shows_the_words_around_the_topic(self):
        text = "alpha " * 100 + "limb volume changes daily " + "omega " * 100
        excerpt = topic_excerpt(VOLUME, chunk("a", text, 0.7))
        self.assertIn("limb volume changes daily", excerpt)
        self.assertTrue(excerpt.startswith("… alpha") and excerpt.endswith("omega …"))
        self.assertLessEqual(len(excerpt), 260)

    def test_arabic_term_with_vowel_marks_located(self):
        text = "كلمة " * 80 + "حَجم الطرف" + " كلمة" * 80
        self.assertIn("حَجم الطرف", topic_excerpt(VOLUME, chunk("a", text, 0.7, "ar")))

"""Tests for reasoning/rag.py, rag_topics.py and writer.py: the RAG, with a fake writer (no API calls)."""

import io
import json
import os
import unittest
import urllib.error
from types import SimpleNamespace
from unittest import mock

from knowledge.models import ProtocolChunk
from reasoning import rag, writer as writer_module
from reasoning.models import FUNCTIONAL_LEVEL, ORIGIN_RAG
from reasoning.rag import (
    ARABIC_TERMS,
    NO_PASSAGES,
    OK,
    REPEAT,
    SYSTEM_PROMPT,
    UNAVAILABLE,
    Generation,
    answer_schema,
    case_for_prompt,
    check_items,
    components_from,
    fitting_from,
    gaps_from,
    generate,
    item_id,
    run_part,
    user_message,
)
from reasoning.rag_topics import COMPONENTS_PART, FITTING, GAPS, topics_for_case
from reasoning.writer import ClaudeWriter, GeminiWriter, OfflineWriter, WriterUnavailable, default_writer
from shared.case_schema import ActivityProfile, Case
from shared.config import GEMINI_API_KEY_ENV, OFFLINE_ENV, PROMPT_VERSION
from shared.i18n import TEXT, VALUE_LABELS
from tests.helpers import FakeWriter, quote_every_topic


def page_arabic() -> str:
    """Every Arabic text the pages can show (shared/i18n.py), to check a term is the page's own."""
    return " ".join([entry["ar"] for entry in TEXT.values() if isinstance(entry, dict) and "ar" in entry]
                    + [label for labels in VALUE_LABELS["ar"].values() for label in labels.values()])

VOLUME = "residual_limb.volume_stability"
WOUND = "residual_limb.wound_status"


def chunk(chunk_id: str, text: str, page: int = 10) -> ProtocolChunk:
    return ProtocolChunk(chunk_id=chunk_id, text=text, source="x.pdf", title="Title", year=2024, page=page,
                         end_page=page, language="en", score=0.7)


KNEE = chunk("lower_limb_amputation_va_dod_cpg_2024-0901",
             "For prosthetic ambulators, we suggest prescribing microprocessor knee units over "
             "non-microprocessor knee units. Weak for Reviewed, New-added", 56)
VOLUME_TEXT = chunk("lower_limb_amputation_va_dod_cpg_2024-0902",
                    "Residual limb volume should be stable before the definitive socket is cast.", 30)
WOUND_TEXT = chunk("lower_limb_amputation_va_dod_cpg_2024-0903",
                   "The residual limb wound must be healed before a prosthesis is fitted.", 31)


def item(topic, passage, quote, grade="", en="An English sentence.", ar="جملة عربية."):
    return {"topic": topic, "passage_id": passage.chunk_id, "quote": quote, "sentence_en": en, "sentence_ar": ar,
            "grade": grade}


def transfemoral(**fields) -> Case:
    return Case(amputation_level="transfemoral", side="left", **fields)


class TopicTests(unittest.TestCase):
    def test_lower_limb_topics(self):
        case = transfemoral(activity=ActivityProfile(k_level="K2"))
        topics = topics_for_case(case)
        parts = {t.part for t in topics}
        self.assertEqual(parts, {GAPS, COMPONENTS_PART, FITTING})
        keys = [t.key for t in topics if t.part != GAPS]
        self.assertEqual(keys, [FUNCTIONAL_LEVEL, "knee", "foot_ankle", "pylon", "socket", "interface", "suspension",
                                "readiness", "prosthesis_stage", "fitting", "alignment"])
        knee = next(t for t in topics if t.key == "knee")
        self.assertIn("transfemoral amputation (lower limb), functional level K2", knee.query)
        functional = next(t for t in topics if t.key == FUNCTIONAL_LEVEL)
        self.assertIn("level K2", functional.query)

    def test_upper_limb_topics(self):
        topics = topics_for_case(Case(amputation_level="transradial", side="bilateral"))
        keys = [t.key for t in topics if t.part != GAPS]
        self.assertEqual(keys, ["prosthesis_type", "control_and_fit", "readiness", "prosthesis_stage", "fitting",
                                "alignment"])  # no functional level: K-levels describe lower-limb prostheses
        self.assertIn("transradial amputation (upper limb), bilateral", topics[-1].query)

    def test_gap_topics_are_the_missing_fields(self):
        topics = [t for t in topics_for_case(transfemoral()) if t.part == GAPS]
        self.assertIn(VOLUME, [t.key for t in topics])
        self.assertTrue(all("(transfemoral amputation, lower limb)" in t.query for t in topics))


class PromptTests(unittest.TestCase):
    def test_instructions(self):
        # Principle 1: report, never advise; every sentence backed by a quote copied exactly.
        for words in ("Use only the passages given", "character for character", "never advise",
                      "Do not recommend, prescribe, choose or rank", "ready for fitting", "give each side",
                      "Never infer a grade", "never translate it"):
            self.assertIn(words, SYSTEM_PROMPT)

    def test_v3_keeps_the_source_strength_and_the_page_terms(self):
        # After the first live run (2026-10-23): a hedge dropped, a claim from outside the quote, "must"
        # added; and one concept in two Arabic words. rag-v3 names each, and gives the page's terms.
        self.assertEqual(PROMPT_VERSION, "rag-v3")
        for words in ("never state it as a plain fact", "into an instruction", "only where the quote does",
                      "not from the rest of the passage", "the same term every time"):
            self.assertIn(words, SYSTEM_PROMPT)
        page = page_arabic()
        for english, arabic in ARABIC_TERMS:
            with self.subTest(english):
                self.assertIn(f"{english} = {arabic}", SYSTEM_PROMPT)
                self.assertIn(arabic, page)  # the review page's own word

    def test_schema_allows_only_the_topics_and_passages_given(self):
        schema = answer_schema(["knee"], [KNEE.chunk_id])
        item_schema = schema["properties"]["items"]["items"]
        self.assertEqual(item_schema["properties"]["topic"]["enum"], ["knee"])
        self.assertEqual(item_schema["properties"]["passage_id"]["enum"], [KNEE.chunk_id])
        self.assertIn("Weak for", item_schema["properties"]["grade"]["enum"])
        self.assertEqual(set(item_schema["required"]), set(item_schema["properties"]))
        self.assertFalse(item_schema["additionalProperties"])

    def test_user_message_holds_the_case_and_each_passage_once(self):
        case = transfemoral(age_years=60)
        topics = [t for t in topics_for_case(case) if t.key in ("knee", "socket")]
        message = user_message(COMPONENTS_PART, case, topics, {"knee": [KNEE], "socket": [KNEE]})
        self.assertEqual(message.count(f'<passage id="{KNEE.chunk_id}"'), 1)
        self.assertIn('found_for="knee, socket"', message)
        self.assertIn('"amputation_level": "transfemoral"', message)
        self.assertNotIn(case.case_id, message)  # nothing generated, nothing identifying
        self.assertIn("- knee: Knee unit", message)

    def test_only_the_facts_the_rules_use_are_sent(self):
        # Prompt rule 7: level, side and recorded K-level decide relevance; nothing typed at intake is sent.
        case = transfemoral(age_years=67, intake_notes="Mr Example, 12 Main Street, confirm K4 components",
                            comorbidities=["diabetes"],
                            activity=ActivityProfile(k_level="K3", functional_goals="walk to the mosque"))
        self.assertEqual(json.loads(case_for_prompt(case)), {
            "amputation_level": "transfemoral", "limb": "lower", "side": "left", "functional_level_recorded": "K3"})
        message = user_message(COMPONENTS_PART, case, [t for t in topics_for_case(case) if t.key == "knee"],
                               {"knee": [KNEE]})
        for typed in ("Mr Example", "Main Street", "confirm K4", "diabetes", "mosque", "67"):
            self.assertNotIn(typed, message)

    def test_upper_limb_case_sent_without_k_level(self):
        case = Case(amputation_level="transradial", side="left")
        self.assertEqual(json.loads(case_for_prompt(case)), {
            "amputation_level": "transradial", "limb": "upper", "side": "left", "functional_level_recorded": None})


class CheckItemsTests(unittest.TestCase):
    def check(self, part, items, topics=("knee",), passages=(KNEE,)):
        topic_objects = [SimpleNamespace(key=key) for key in topics]
        return check_items(part, {"items": items}, topic_objects, {p.chunk_id: p for p in passages})

    def test_a_good_item_is_kept_with_the_passage_own_words_and_page(self):
        [kept], removed = self.check(COMPONENTS_PART, [item("knee", KNEE, "we suggest prescribing microprocessor "
                                                                         "knee units", grade="Weak for")])
        self.assertEqual(removed, [])
        self.assertEqual((kept.topic, kept.chunk_id, kept.doc_id, kept.quote, kept.grade, kept.page),
                         ("knee", KNEE.chunk_id, "lower_limb_amputation_va_dod_cpg_2024",
                          "we suggest prescribing microprocessor knee units", "Weak for", 56))
        self.assertTrue(kept.id.startswith("rag-knee-"))

    def test_the_same_quote_has_the_same_id_in_every_case(self):
        self.assertEqual(item_id("knee", "doc", "a quote"), item_id("knee", "doc", "a quote"))
        self.assertNotEqual(item_id("knee", "doc", "a quote"), item_id("socket", "doc", "a quote"))

    def test_every_reason_to_remove_an_item(self):
        other = chunk("other_doc-0001", "A passage that was never given to the model at all.")
        items = [
            item("hip", KNEE, "we suggest prescribing microprocessor knee units"),
            item("knee", other, "A passage that was never given"),
            item("knee", KNEE, "we strongly recommend microprocessor knee units"),
            item("knee", KNEE, "microprocessor knee units"),
            item("knee", KNEE, "we suggest prescribing microprocessor knee units", en=""),
            item("knee", KNEE, "we suggest prescribing microprocessor knee units", ar="no Arabic here"),
        ]
        kept, removed = self.check(COMPONENTS_PART, items)
        self.assertEqual(kept, [])
        self.assertEqual([entry["reason"] for entry in removed], [
            "not one of the topics asked about", "names a passage that was not given",
            "quote not found word for word in the passage", "quote shorter than 5 words",
            "no English sentence", "no Arabic sentence"])
        self.assertTrue(all(entry["dropped"] == "item" for entry in removed))

    def test_repeats_and_the_limit_per_topic(self):
        quote = "we suggest prescribing microprocessor knee units"
        kept, removed = self.check(COMPONENTS_PART, [item("knee", KNEE, quote), item("knee", KNEE, quote)])
        self.assertEqual((len(kept), removed[0]["reason"]), (1, "the same quote again for this topic"))
        # Missing information: one item per field.
        kept, removed = self.check(GAPS, [item(VOLUME, VOLUME_TEXT, "Residual limb volume should be stable"),
                                          item(VOLUME, VOLUME_TEXT, "before the definitive socket is cast")],
                                   topics=(VOLUME,), passages=(VOLUME_TEXT,))
        self.assertEqual((len(kept), removed[0]["reason"]), (1, "more than 1 item(s) for this topic"))

    def test_a_grade_not_printed_after_the_quote_is_dropped_the_item_kept(self):
        [kept], [removed] = self.check(COMPONENTS_PART, [item("knee", KNEE, "we suggest prescribing microprocessor "
                                                                             "knee units", grade="Strong for")])
        self.assertIsNone(kept.grade)
        self.assertEqual((removed["dropped"], removed["reason"]),
                         ("grade", "grade 'Strong for' not printed after the quote"))


class RunTests(unittest.TestCase):
    def setUp(self):
        self.case = transfemoral()
        self.topics = topics_for_case(self.case)
        self.passages = {"knee": [KNEE], VOLUME: [VOLUME_TEXT], WOUND: [WOUND_TEXT]}

    def test_three_parts_asked_at_once(self):
        writer = FakeWriter()
        generation = generate(self.case, self.passages, writer, self.topics)
        self.assertEqual(set(generation.parts), {GAPS, COMPONENTS_PART, FITTING})
        self.assertEqual((generation.part(GAPS).status, generation.part(COMPONENTS_PART).status),
                         (OK, OK))
        self.assertEqual(generation.part(FITTING).status, NO_PASSAGES)  # nothing found: no call
        self.assertEqual(len(writer.calls), 2)
        self.assertEqual(generation.part(COMPONENTS_PART).model, "fake-model")
        self.assertEqual(generation.part(COMPONENTS_PART).topics, ["knee"])

    def test_writer_unavailable_or_failing(self):
        part = run_part(COMPONENTS_PART, self.case, self.topics, self.passages, FakeWriter(error="offline"))
        self.assertEqual((part.status, part.reason, part.items), (UNAVAILABLE, "offline", []))

        def broken(user, schema):
            raise KeyError("bug")
        with self.assertLogs("reasoning.rag", "ERROR"):
            part = run_part(COMPONENTS_PART, self.case, self.topics, self.passages, FakeWriter(broken))
        self.assertEqual((part.status, part.reason), (UNAVAILABLE, "unexpected error: KeyError: 'bug'"))

    def test_generation_kept_and_read_back(self):
        generation = generate(self.case, self.passages, FakeWriter(), self.topics)
        again = Generation.from_dict(json.loads(json.dumps(generation.to_dict())))
        self.assertEqual(again, generation)


class RepeatTests(unittest.TestCase):
    """A quote the AI gives under topics of two parts is shown once, under the first (drop_repeats)."""

    def setUp(self):
        self.case = transfemoral()
        self.passages = {"knee": [KNEE], "alignment": [KNEE], VOLUME: [KNEE]}  # one passage for three topics

    def test_shown_once_and_not_counted_as_a_failed_check(self):
        generation = generate(self.case, self.passages, FakeWriter())  # quotes the same 8 words for each topic
        components, fitting = generation.part(COMPONENTS_PART), generation.part(FITTING)
        self.assertEqual([item.topic for item in components.items], ["knee"])
        self.assertEqual(fitting.items, [])
        [repeat] = fitting.removed
        self.assertEqual((repeat["topic"], repeat["dropped"], repeat["reason"]),
                         ("alignment", REPEAT, "the same quote is shown under knee"))
        self.assertEqual((fitting.repeats_for("alignment"), fitting.removed_items, fitting.removed_for("alignment")),
                         (1, 0, 0))
        self.assertEqual([item.topic for item in generation.part(GAPS).items], [VOLUME])  # a gap keeps its quote

    def test_a_quote_holding_one_already_shown_is_a_repeat(self):
        def answer(user, schema):
            data = quote_every_topic(user, schema, words=6)
            for entry in data["items"]:
                if entry["topic"] == "alignment":  # a longer stretch around the knee quote
                    entry["quote"] = "For prosthetic ambulators, we suggest prescribing microprocessor knee units over"
            return data
        fitting = generate(self.case, self.passages, FakeWriter(answer)).part(FITTING)
        self.assertEqual((fitting.items, fitting.repeats_for("alignment")), ([], 1))
        other = {"knee": [KNEE], "alignment": [WOUND_TEXT]}  # a different quote is kept
        self.assertEqual([i.topic for i in generate(self.case, other, FakeWriter()).part(FITTING).items],
                         ["alignment"])


class PageShapeTests(unittest.TestCase):
    def setUp(self):
        self.case = transfemoral(activity=ActivityProfile(k_level="K3"))
        self.passages = {"knee": [KNEE], VOLUME: [VOLUME_TEXT], WOUND: [WOUND_TEXT]}

    def test_gaps_cite_the_ai_quote_and_sentence(self):
        def answer(user, schema):
            data = quote_every_topic(user, schema)
            # The wound gap may quote a passage found for another missing field.
            for entry in data["items"]:
                if entry["topic"] == WOUND:
                    entry.update(passage_id=VOLUME_TEXT.chunk_id, quote="Residual limb volume should be stable")
            return data
        generation = generate(self.case, self.passages, FakeWriter(answer))
        gaps = {gap.field: gap for gap in gaps_from(self.case, self.passages, generation)}
        volume, wound = gaps[VOLUME], gaps[WOUND]
        self.assertEqual((volume.evidence, volume.excerpt, volume.summary_en),
                         (VOLUME_TEXT, "Residual limb volume should be stable before the",
                          f"AI sentence about {VOLUME}."))
        self.assertEqual(volume.summary("ar"), f"جملة الذكاء الاصطناعي عن {VOLUME}.")
        self.assertTrue(volume.why_needed.startswith("Residual limb volume stability was not recorded"))
        self.assertEqual(wound.evidence, VOLUME_TEXT)
        self.assertIsNone(gaps["age_years"].evidence)  # no passage: no source

    def test_without_the_ai_the_gaps_come_from_the_topic_word_check(self):
        generation = generate(self.case, self.passages, OfflineWriter())
        gaps = {gap.field: gap for gap in gaps_from(self.case, self.passages, generation)}
        self.assertEqual(gaps[VOLUME].excerpt, VOLUME_TEXT.text)  # the topic-word check quotes whole sentences
        self.assertIsNone(gaps[VOLUME].summary_en)

    def test_components_and_fitting(self):
        generation = generate(self.case, self.passages, FakeWriter())
        components = components_from(self.case, generation)
        self.assertEqual(components.functional.k_level, "K3")
        self.assertEqual(components.functional_section.statements, [])  # no passage for it here
        keys = [section.component for section in components.component_sections]
        self.assertEqual(keys, ["knee", "foot_ankle", "socket", "interface", "suspension"])  # no pylon: nothing said
        [knee] = components.component_sections[0].statements
        self.assertEqual((knee.origin, knee.chunk_id, knee.summary_en, knee.source_type),
                         (ORIGIN_RAG, KNEE.chunk_id, "AI sentence about knee.", "protocol"))
        self.assertIn("Rehabilitation of Individuals with Lower Limb Amputation", knee.title)  # from the catalog
        self.assertTrue(knee.citation(knee.statement.quote).endswith(" (2024), p. 56"))
        fitting = fitting_from(self.case, generation)
        self.assertEqual([s.component for s in fitting.sections],
                         ["readiness", "prosthesis_stage", "fitting", "alignment"])
        self.assertEqual(fitting.statements, [])
        self.assertEqual(dict(fitting.recorded)["cognitive_status"], None)

    def test_upper_limb_has_no_functional_section(self):
        case = Case(amputation_level="transradial", side="left")
        components = components_from(case, generate(case, {}, FakeWriter()))
        self.assertIsNone(components.functional_section)
        self.assertEqual([s.component for s in components.sections], ["prosthesis_type", "control_and_fit"])


class ClaudeWriterTests(unittest.TestCase):
    """The Claude API call itself, with the SDK client replaced: never the network."""

    def writer_answering(self, text='{"items": []}', stop_reason="end_turn", stop_details=None):
        message = SimpleNamespace(
            stop_reason=stop_reason, stop_details=stop_details, model="claude-opus-5-5",
            content=[SimpleNamespace(type="thinking", thinking=""), SimpleNamespace(type="text", text=text)],
            usage=SimpleNamespace(to_dict=lambda: {"input_tokens": 1200, "output_tokens": 300, "service_tier": "x"}))
        stream = mock.MagicMock()
        stream.__enter__.return_value.get_final_message.return_value = message
        client = mock.MagicMock()
        client.beta.messages.stream.return_value = stream
        writer = ClaudeWriter()
        writer._client = client
        return writer, client

    def test_the_request(self):
        writer, client = self.writer_answering()
        result = writer.write("system text", "user text", {"type": "object"})
        kwargs = client.beta.messages.stream.call_args.kwargs
        self.assertEqual(kwargs["model"], "claude-opus-5-5")
        self.assertEqual(kwargs["system"], "system text")
        self.assertEqual(kwargs["messages"], [{"role": "user", "content": "user text"}])
        self.assertEqual(kwargs["output_config"], {"effort": "medium",
                                                   "format": {"type": "json_schema", "schema": {"type": "object"}}})
        self.assertEqual((kwargs["betas"], kwargs["fallbacks"]), (["server-side-fallback-2026-07-01"], "default"))
        self.assertNotIn("thinking", kwargs)  # adaptive: always on for this model
        self.assertEqual((result.data, result.model), ({"items": []}, "claude-opus-5-5"))
        self.assertEqual(result.usage, {"input_tokens": 1200, "output_tokens": 300})

    def test_answers_that_cannot_be_used(self):
        for kwargs, reason in [
            ({"stop_reason": "refusal", "stop_details": SimpleNamespace(category="bio")}, r"declined to answer \(refusal, bio\)"),
            ({"stop_reason": "max_tokens"}, "cut off at 32000 tokens"),
            ({"text": "not json"}, "not valid JSON"),
        ]:
            with self.subTest(reason):
                writer, _ = self.writer_answering(**kwargs)
                with self.assertRaisesRegex(WriterUnavailable, reason):
                    writer.write("s", "u", {})

    def test_no_key_and_no_connection(self):
        import anthropic
        import httpx2

        for error, reason in [
            (TypeError("Could not resolve authentication method. Expected one of api_key"), "no Claude API key"),
            (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://api.anthropic.com")),
             "could not be reached"),
        ]:
            with self.subTest(reason):
                writer, client = self.writer_answering()
                client.beta.messages.stream.side_effect = error
                with self.assertRaisesRegex(WriterUnavailable, reason):
                    writer.write("s", "u", {})

    def test_default_writer(self):
        with mock.patch.dict(os.environ, {OFFLINE_ENV: "1"}):
            self.assertIsInstance(default_writer(), OfflineWriter)
            with self.assertRaisesRegex(WriterUnavailable, "switched off"):
                default_writer().write("s", "u", {})
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop(OFFLINE_ENV, None)
            try:  # made, never called here
                self.assertIsInstance(default_writer(), GeminiWriter)  # LLM_PROVIDER "gemini"
                with mock.patch.object(writer_module, "LLM_PROVIDER", "claude"):
                    self.assertIsInstance(default_writer(), ClaudeWriter)
            finally:
                os.environ[OFFLINE_ENV] = "1"


def http_error(code: int, message: str = "") -> urllib.error.HTTPError:
    body = json.dumps({"error": {"code": code, "message": message, "status": "X"}}).encode("utf-8")
    return urllib.error.HTTPError("https://generativelanguage.googleapis.com", code, "error", None, io.BytesIO(body))


class GeminiWriterTests(unittest.TestCase):
    """The Gemini API call itself, with urlopen replaced: never the network."""

    def setUp(self):
        for patcher in (mock.patch.dict(os.environ, {GEMINI_API_KEY_ENV: "test-key"}),
                        mock.patch.object(writer_module.time, "sleep")):
            self.addCleanup(patcher.stop)
            self.slept = patcher.start()

    def reply(self, text='{"items": []}', finish="STOP", **extra) -> dict:
        return {"candidates": [{"content": {"parts": [{"text": "thinking ...", "thought": True}, {"text": text}]},
                                "finishReason": finish}],
                "usageMetadata": {"promptTokenCount": 1200, "candidatesTokenCount": 250, "thoughtsTokenCount": 50,
                                  "totalTokenCount": 1500},
                "modelVersion": "gemini-3.8-flash", **extra}

    def answering(self, *replies):
        """urlopen replaced: each call gives the next reply (a dict), or raises it (an exception)."""
        answers = iter(replies)

        def urlopen(request, timeout):
            answer = next(answers)
            if isinstance(answer, Exception):
                raise answer
            response = mock.MagicMock()
            response.__enter__.return_value.read.return_value = json.dumps(answer).encode("utf-8")
            return response

        patcher = mock.patch.object(writer_module.urllib.request, "urlopen", side_effect=urlopen)
        self.addCleanup(patcher.stop)
        return patcher.start()

    def test_the_request(self):
        urlopen = self.answering(self.reply())
        result = GeminiWriter().write("system text", "user text", {"type": "object"})
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_method(), "POST")
        self.assertTrue(request.full_url.endswith("/v1beta/models/gemini-3.8-flash:generateContent"))
        self.assertEqual(request.get_header("X-goog-api-key"), "test-key")  # in a header, never in the URL
        self.assertNotIn("test-key", request.full_url)
        self.assertEqual(json.loads(request.data), {
            "systemInstruction": {"parts": [{"text": "system text"}]},
            "contents": [{"role": "user", "parts": [{"text": "user text"}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": {"type": "object"},
                                 "maxOutputTokens": 32000}})
        self.assertEqual((result.data, result.model), ({"items": []}, "gemini-3.8-flash"))  # thought part skipped
        self.assertEqual(result.usage, {"input_tokens": 1200, "output_tokens": 300})

    def test_answers_that_cannot_be_used(self):
        for reply, reason in [
            (self.reply(finish="MAX_TOKENS"), "cut off at 32000 tokens"),
            (self.reply(finish="SAFETY"), r"declined to answer \(SAFETY\)"),
            ({"promptFeedback": {"blockReason": "PROHIBITED_CONTENT"}}, r"request blocked: PROHIBITED_CONTENT"),
            (self.reply(text="not json"), "not valid JSON"),
            (self.reply(text=""), "held no text"),
        ]:
            with self.subTest(reason):
                self.answering(reply)
                with self.assertRaisesRegex(WriterUnavailable, reason):
                    GeminiWriter().write("s", "u", {})

    def test_no_key_and_errors(self):
        with mock.patch.dict(os.environ, {GEMINI_API_KEY_ENV: ""}):
            with self.assertRaisesRegex(WriterUnavailable, f"no Gemini API key: set {GEMINI_API_KEY_ENV}"):
                GeminiWriter().write("s", "u", {})
        for error, reason in [
            (http_error(400, "API key not valid. Please pass a valid API key."), "refused the API key"),
            (http_error(400, "User location is not supported for the API use."), "refused the request: User location"),
            (http_error(404, "models/x is not found"), "model gemini-3.8-flash not found"),
            (urllib.error.URLError(ConnectionRefusedError()), "could not be reached"),
            (urllib.error.URLError(TimeoutError()), "did not answer within 300 s"),
            (TimeoutError(), "did not answer within 300 s"),
        ]:
            with self.subTest(reason):
                self.answering(error)
                with self.assertRaisesRegex(WriterUnavailable, reason):
                    GeminiWriter().write("s", "u", {})

    def test_rate_limit_and_overload_are_tried_again(self):
        urlopen = self.answering(http_error(503), self.reply())
        self.assertEqual(GeminiWriter().write("s", "u", {}).data, {"items": []})
        self.assertEqual(urlopen.call_count, 2)
        urlopen = self.answering(http_error(429), http_error(429), http_error(429))
        with self.assertRaisesRegex(WriterUnavailable, "rate limit or daily quota"):
            GeminiWriter().write("s", "u", {})
        self.assertEqual(urlopen.call_count, 3)  # the first try and two more


if __name__ == "__main__":
    unittest.main()

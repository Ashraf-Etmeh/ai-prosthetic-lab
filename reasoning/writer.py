"""The writer: the one place the app talks to a language model.

reasoning/rag.py hands a writer a system prompt, a user message and a JSON
schema, and gets back the parsed JSON answer with the model that wrote it
and its token counts. Everything else in the app depends only on the
`Writer` shape below, so another model (or a local one) can replace the one
in use by adding one class here (the owner's decision, 2026-10-11).
shared/config.py LLM_PROVIDER picks the class: "gemini" (since 2026-10-13)
or "claude".

A writer that can't answer raises WriterUnavailable with a reason for the
page and the log (no API key, offline, refused, cut off, ...). The page then
shows the passages found, without summaries.

GeminiWriter uses the Gemini API's REST endpoint with Python's own HTTP
client (no SDK):
- model GEMINI_MODEL, its thinking left at the model's default,
- structured output: the schema goes in responseJsonSchema, so the answer
  must match it,
- a request refused with 429 (rate limit) or 500/503 (overloaded) is tried
  twice more, a few seconds apart; a daily free-tier quota stays refused.
The key is read from GEMINI_API_KEY and sent in a header, never in the URL.

ClaudeWriter uses the Claude API through the official SDK:
- model LLM_MODEL with adaptive thinking (always on for this model) and
  effort LLM_EFFORT,
- structured output: the answer must match the schema, so it can be read
  without guessing,
- server-side fallbacks (LLM_FALLBACKS): if the safety classifiers decline
  the request, the API reruns it on the model Anthropic recommends; the
  model that answered is recorded,
- streaming, so a long answer doesn't hit an HTTP timeout.
No API key is kept in the project: the SDK reads ANTHROPIC_API_KEY.
"""

import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Optional, Protocol

from shared.config import (
    GEMINI_API_KEY_ENV,
    GEMINI_MODEL,
    GEMINI_URL,
    LLM_EFFORT,
    LLM_FALLBACKS,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_PROVIDER,
    LLM_TIMEOUT_SECONDS,
    OFFLINE_ENV,
)

FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Gemini: answers that are tried again, and how long to wait before each try.
GEMINI_RETRY_STATUSES = (429, 500, 503)
GEMINI_RETRY_SECONDS = (3, 8)
# Gemini finish reasons that mean the model (or its filters) declined.
GEMINI_DECLINED = ("SAFETY", "RECITATION", "BLOCKLIST", "PROHIBITED_CONTENT", "SPII", "LANGUAGE")


class WriterUnavailable(RuntimeError):
    """The writer gave no usable answer. str(error) says why, for the page and the log."""


@dataclass
class WriterResult:
    data: dict  # the answer, parsed from JSON, matching the schema
    model: str  # the model that answered (a fallback model if the first declined)
    usage: dict = field(default_factory=dict)  # token counts as the API reports them
    seconds: float = 0.0


class Writer(Protocol):
    name: str  # e.g. "claude-opus-5-5", logged with every decision

    def write(self, system: str, user: str, schema: dict) -> WriterResult: ...


class OfflineWriter:
    """Never answers: the AI writer is switched off (tests, --no-ai runs)."""

    def __init__(self, reason: str = f"the AI writer is switched off ({OFFLINE_ENV} is set)") -> None:
        self.name = "offline"
        self.reason = reason

    def write(self, system: str, user: str, schema: dict) -> WriterResult:
        raise WriterUnavailable(self.reason)


class ClaudeWriter:
    def __init__(self, model: str = LLM_MODEL, effort: str = LLM_EFFORT,
                 max_tokens: int = LLM_MAX_TOKENS, fallbacks: bool = LLM_FALLBACKS) -> None:
        self.name = model
        self.model = model
        self.effort = effort
        self.max_tokens = max_tokens
        self.fallbacks = fallbacks
        self._client = None

    def _get_client(self):
        if self._client is None:
            import anthropic  # here: only the live app needs the SDK

            self._client = anthropic.Anthropic(timeout=LLM_TIMEOUT_SECONDS, max_retries=2)
        return self._client

    def write(self, system: str, user: str, schema: dict) -> WriterResult:
        import anthropic

        options = {}
        if self.fallbacks:
            options = {"betas": [FALLBACK_BETA], "fallbacks": "default"}
        started = time.perf_counter()
        try:
            with self._get_client().beta.messages.stream(
                model=self.model,
                max_tokens=self.max_tokens,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_config={"effort": self.effort, "format": {"type": "json_schema", "schema": schema}},
                **options,
            ) as stream:
                message = stream.get_final_message()
        # Most specific first; every failure becomes a reason the page can show.
        except anthropic.AuthenticationError:
            raise WriterUnavailable("the Claude API refused the API key (check ANTHROPIC_API_KEY)") from None
        except anthropic.PermissionDeniedError as e:
            raise WriterUnavailable(f"the API key may not use {self.model}: {e.message}") from None
        except anthropic.NotFoundError as e:
            raise WriterUnavailable(f"model {self.model} not found: {e.message}") from None
        except anthropic.RateLimitError:
            raise WriterUnavailable("the Claude API rate limit was reached; try again in a minute") from None
        except anthropic.BadRequestError as e:
            raise WriterUnavailable(f"the Claude API refused the request: {e.message}") from None
        except anthropic.APIStatusError as e:
            raise WriterUnavailable(f"the Claude API answered with an error ({e.status_code}); "
                                    "try again later") from None
        except anthropic.APITimeoutError:
            raise WriterUnavailable(f"the Claude API did not answer within {LLM_TIMEOUT_SECONDS} s") from None
        except anthropic.APIConnectionError:
            raise WriterUnavailable("the Claude API could not be reached (offline?)") from None
        except anthropic.AnthropicError as e:
            raise WriterUnavailable(f"the Claude API call failed: {e}") from None
        except TypeError as e:
            # The SDK's way of saying no credentials were found, before any request.
            if "authentication" in str(e):
                raise WriterUnavailable("no Claude API key: set ANTHROPIC_API_KEY") from None
            raise
        seconds = time.perf_counter() - started

        # Check why the model stopped before reading what it wrote.
        if message.stop_reason == "refusal":
            category = getattr(message.stop_details, "category", None) if message.stop_details else None
            raise WriterUnavailable(f"the model declined to answer (refusal{', ' + category if category else ''})")
        if message.stop_reason == "max_tokens":
            raise WriterUnavailable(f"the answer was cut off at {self.max_tokens} tokens")
        text = next((block.text for block in message.content if block.type == "text"), None)
        if text is None:
            raise WriterUnavailable(f"the answer held no text (stop reason {message.stop_reason})")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            raise WriterUnavailable("the answer was not valid JSON") from None
        usage = message.usage.to_dict() if hasattr(message.usage, "to_dict") else dict(message.usage or {})
        return WriterResult(data=data, model=message.model, usage=_token_counts(usage), seconds=round(seconds, 1))


class GeminiWriter:
    def __init__(self, model: str = GEMINI_MODEL, max_tokens: int = LLM_MAX_TOKENS,
                 timeout: int = LLM_TIMEOUT_SECONDS) -> None:
        self.name = model
        self.model = model
        self.effort = "model default"  # logged with the answer; Gemini's thinking level isn't set
        self.max_tokens = max_tokens
        self.timeout = timeout

    def _post(self, body: dict, key: str) -> dict:
        request = urllib.request.Request(
            GEMINI_URL.format(model=self.model), data=json.dumps(body).encode("utf-8"), method="POST",
            headers={"Content-Type": "application/json", "x-goog-api-key": key})
        for wait in (*GEMINI_RETRY_SECONDS, None):
            try:
                with urllib.request.urlopen(request, timeout=self.timeout) as response:
                    return json.loads(response.read().decode("utf-8"))
            except urllib.error.HTTPError as e:
                reason = _gemini_error(e, self.model)
                e.close()  # release the connection
                if e.code in GEMINI_RETRY_STATUSES and wait is not None:
                    time.sleep(wait)
                    continue
                raise WriterUnavailable(reason) from None
            except OSError as e:  # URLError, a timeout, a dropped connection
                if isinstance(e, TimeoutError) or isinstance(getattr(e, "reason", None), TimeoutError):
                    raise WriterUnavailable(f"the Gemini API did not answer within {self.timeout} s") from None
                raise WriterUnavailable("the Gemini API could not be reached (offline?)") from None
            except ValueError:
                raise WriterUnavailable("the Gemini API's reply was not JSON") from None

    def write(self, system: str, user: str, schema: dict) -> WriterResult:
        key = os.environ.get(GEMINI_API_KEY_ENV)
        if not key:
            raise WriterUnavailable(f"no Gemini API key: set {GEMINI_API_KEY_ENV}")
        body = {
            "systemInstruction": {"parts": [{"text": system}]},
            "contents": [{"role": "user", "parts": [{"text": user}]}],
            "generationConfig": {"responseMimeType": "application/json", "responseJsonSchema": schema,
                                 "maxOutputTokens": self.max_tokens},
        }
        started = time.perf_counter()
        reply = self._post(body, key)
        seconds = time.perf_counter() - started

        # Check why the model stopped before reading what it wrote.
        blocked = (reply.get("promptFeedback") or {}).get("blockReason")
        if blocked:
            raise WriterUnavailable(f"the model declined to answer (request blocked: {blocked})")
        candidate = (reply.get("candidates") or [{}])[0]
        finish = candidate.get("finishReason", "")
        if finish == "MAX_TOKENS":
            raise WriterUnavailable(f"the answer was cut off at {self.max_tokens} tokens")
        if finish in GEMINI_DECLINED:
            raise WriterUnavailable(f"the model declined to answer ({finish})")
        text = "".join(part.get("text", "") for part in (candidate.get("content") or {}).get("parts", [])
                       if not part.get("thought"))
        if not text:
            raise WriterUnavailable(f"the answer held no text (finish reason {finish or 'none'})")
        try:
            data = json.loads(text)
        except json.JSONDecodeError:
            raise WriterUnavailable("the answer was not valid JSON") from None
        usage = reply.get("usageMetadata") or {}
        output = [usage.get(k) for k in ("candidatesTokenCount", "thoughtsTokenCount") if isinstance(usage.get(k), int)]
        tokens = {"input_tokens": usage.get("promptTokenCount"), "output_tokens": sum(output) if output else None,
                  "cache_read_input_tokens": usage.get("cachedContentTokenCount")}
        return WriterResult(data=data, model=reply.get("modelVersion") or self.model,
                            usage=_token_counts(tokens), seconds=round(seconds, 1))


def _gemini_error(error: urllib.error.HTTPError, model: str) -> str:
    """The reason for the page and the log, from the Gemini API's error reply."""
    try:
        message = json.loads(error.read().decode("utf-8")).get("error", {}).get("message", "")
    except (ValueError, OSError, AttributeError):
        message = ""
    if error.code in (400, 401, 403) and "api key" in message.lower():
        return f"the Gemini API refused the API key (check {GEMINI_API_KEY_ENV})"
    if error.code == 403:
        return f"the API key may not use {model}: {message}"
    if error.code == 404:
        return f"model {model} not found: {message}"
    if error.code == 429:
        return ("the Gemini API's rate limit or daily quota was reached (the free tier's limits are shown "
                "in Google AI Studio); try again later")
    if error.code == 400:
        return f"the Gemini API refused the request: {message}"
    return f"the Gemini API answered with an error ({error.code}); try again later"


def _token_counts(usage: dict) -> dict:
    """The token counts worth logging (the API reports more)."""
    keys = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    return {key: usage[key] for key in keys if isinstance(usage.get(key), int)}


WRITERS = {"gemini": GeminiWriter, "claude": ClaudeWriter}


def is_cloud(writer: Writer) -> bool:
    """Whether the writer sends what it is given to a cloud API (every LLM_PROVIDER writer does)."""
    return isinstance(writer, tuple(WRITERS.values()))


def provider_writer() -> Writer:
    """The writer of LLM_PROVIDER, even when the AI is switched off (golden_cases --rag)."""
    return WRITERS[LLM_PROVIDER]()


def default_writer() -> Writer:
    """The writer the app uses: LLM_PROVIDER's, unless switched off (OFFLINE_ENV)."""
    if os.environ.get(OFFLINE_ENV):
        return OfflineWriter()
    return provider_writer()

"""The writer: the one place the app talks to a language model.

reasoning/rag.py hands a writer a system prompt, a user message and a JSON
schema, and gets back the parsed JSON answer with the model that wrote it
and its token counts. Everything else in the app depends only on the
`Writer` shape below, so a local model can replace the Claude API later by
adding one class here (the owner's decision, 2026-10-11).

A writer that can't answer raises WriterUnavailable with a reason for the
page and the log (no API key, offline, refused, cut off, ...). The page then
shows the passages found, without summaries.

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
from dataclasses import dataclass, field
from typing import Optional, Protocol

from shared.config import (
    LLM_EFFORT,
    LLM_FALLBACKS,
    LLM_MAX_TOKENS,
    LLM_MODEL,
    LLM_TIMEOUT_SECONDS,
    OFFLINE_ENV,
)

FALLBACK_BETA = "server-side-fallback-2026-07-01"


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
    """Never answers: the Claude API is switched off (tests, --no-ai runs)."""

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


def _token_counts(usage: dict) -> dict:
    """The token counts worth logging (the API reports more)."""
    keys = ("input_tokens", "output_tokens", "cache_creation_input_tokens", "cache_read_input_tokens")
    return {key: usage[key] for key in keys if isinstance(usage.get(key), int)}


def default_writer() -> Writer:
    """The writer the app uses: the Claude API, unless switched off (OFFLINE_ENV)."""
    if os.environ.get(OFFLINE_ENV):
        return OfflineWriter()
    return ClaudeWriter()

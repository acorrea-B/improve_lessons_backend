"""Ollama chat client adapter (T119, US-12).

Talks to the Ollama native API (``POST /api/chat``) and translates every
provider failure into the domain hierarchy of ``app/core/ports/ai_errors.py``:

- retryable (``TransientAIError``): timeout, connection error, HTTP 429,
  HTTP >= 500, and an unusable answer (unparseable body, truncated answer).
- permanent (``NonTransientAIError``): HTTP 400/401/403/404.

The HTTP client is ``niquests`` in SYNCHRONOUS mode, wrapped in
``asyncio.to_thread`` — the house pattern for synchronous clients
(``ses_email_sender.py``, ``secrets_manager_secret_provider.py``,
``local_mail_bridge.py``). Synchronous mode is not a style choice: it is
the only mode vcrpy intercepts (vcrpy patches the standard ``urllib3``,
while niquests' async mode drives ``urllib3-future`` under its own alias),
so the synchronous path is what keeps the suite free of network access.

The port stays ``async``: only the adapter's internals are synchronous.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Callable

from app.core.ports.ai_errors import NonTransientAIError, TransientAIError
from app.utils.logging import get_logger, report_info

logger = get_logger("ai.ollama")

#: Provider status codes that mean "try again later".
TRANSIENT_STATUS_CODES = frozenset({408, 429, 500, 502, 503, 504, 529})


@dataclass(frozen=True)
class OllamaChatRequest:
    """A single ``POST /api/chat`` request."""

    model: str
    messages: list[dict[str, str]]
    num_predict: int
    keep_alive: str = "10m"
    temperature: float = 0.4
    json_format: str = "json"


@dataclass(frozen=True)
class OllamaChatResponse:
    """The useful part of an ``/api/chat`` answer."""

    content: str
    model: str
    done_reason: str
    eval_count: int
    prompt_eval_count: int


def extract_json_object(text: str) -> str:
    """Return the JSON object embedded in ``text``.

    Ollama sometimes wraps the answer in a markdown fence (`` ```json ... ```
    ``) or prefixes it with prose. Rather than a fragile regex, the first
    ``{`` and the last ``}`` delimit the object; everything outside is
    discarded.
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end < start:
        raise TransientAIError(
            "the provider answer contains no JSON object",
            provider="ollama",
        )
    return text[start : end + 1]


class OllamaClient:
    """Thin client over the Ollama native chat API."""

    def __init__(
        self,
        base_url: str,
        *,
        timeout_seconds: int = 180,
        session_factory: Callable[[], Any] | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = timeout_seconds
        self._session_factory = session_factory

    @property
    def base_url(self) -> str:
        return self._base_url

    async def chat(self, request: OllamaChatRequest) -> OllamaChatResponse:
        """Send one chat request and return the parsed answer.

        Raises ``TransientAIError`` / ``NonTransientAIError`` (never a
        provider-specific exception).
        """
        body = self._build_body(request)
        raw = await asyncio.to_thread(self._post_sync, body)
        return self._parse(raw)

    # -- internals ------------------------------------------------------------

    def _build_body(self, request: OllamaChatRequest) -> dict:
        return {
            "model": request.model,
            "messages": request.messages,
            "stream": False,
            "format": request.json_format,
            "keep_alive": request.keep_alive,
            "options": {
                "num_predict": request.num_predict,
                "temperature": request.temperature,
            },
        }

    def _post_sync(self, body: dict) -> dict:
        import niquests

        url = f"{self._base_url}/api/chat"
        session = (
            self._session_factory()
            if self._session_factory is not None
            else niquests.Session()
        )
        try:
            with session:
                response = session.post(url, json=body, timeout=self._timeout)
        except Exception as exc:
            # Timeouts and connection errors are retryable.
            raise TransientAIError(
                f"the AI provider is unreachable: {exc}",
                provider="ollama",
            ) from exc
        status = response.status_code
        if status >= 400:
            detail = _error_detail(response)
            if status in TRANSIENT_STATUS_CODES or status >= 500:
                raise TransientAIError(
                    f"the AI provider failed with status {status}: {detail}",
                    provider="ollama",
                    status_code=status,
                )
            raise NonTransientAIError(
                f"the AI provider rejected the request with status {status}: {detail}",
                provider="ollama",
                status_code=status,
            )
        try:
            return response.json()
        except Exception as exc:
            raise TransientAIError(
                f"the AI provider returned a non-JSON answer: {exc}",
                provider="ollama",
                status_code=status,
            ) from exc

    def _parse(self, raw: dict) -> OllamaChatResponse:
        message = raw.get("message")
        if not isinstance(message, dict):
            raise TransientAIError(
                "the AI provider answer has no message", provider="ollama"
            )
        content = message.get("content")
        if not isinstance(content, str) or not content.strip():
            raise TransientAIError(
                "the AI provider returned an empty answer", provider="ollama"
            )
        done_reason = str(raw.get("done_reason") or "")
        if done_reason == "length":
            # Truncated answer: the material would be incomplete, so it is
            # refused rather than delivered half-written. Retrying with the
            # same budget may still fail, but the loop decides that.
            raise TransientAIError(
                "the AI provider truncated the answer (done_reason=length)",
                provider="ollama",
            )
        report_info(
            "ai.ollama.chat",
            "provider answered",
            model=raw.get("model"),
            eval_count=raw.get("eval_count"),
            done_reason=done_reason or "stop",
        )
        return OllamaChatResponse(
            content=content,
            model=str(raw.get("model") or ""),
            done_reason=done_reason,
            eval_count=int(raw.get("eval_count") or 0),
            prompt_eval_count=int(raw.get("prompt_eval_count") or 0),
        )


def _error_detail(response: Any) -> str:
    """Short, non-sensitive description of a provider error body."""
    try:
        payload = response.json()
    except Exception:
        text = getattr(response, "text", "") or ""
        return text[:200]
    if isinstance(payload, dict):
        error = payload.get("error")
        if isinstance(error, str):
            return error[:200]
    return str(payload)[:200]

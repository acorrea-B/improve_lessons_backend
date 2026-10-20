"""Ollama client contract tests (T119).

The HTTP path is exercised through VCR cassettes: the suite never touches
the network. The adapter calls the provider with a SYNCHRONOUS
``niquests`` session inside ``asyncio.to_thread`` — that is the only
combination vcrpy intercepts (vcrpy patches the standard ``urllib3``,
while niquests' async mode drives ``urllib3-future`` under its own
alias), so the cassettes prove the production path.
"""

from __future__ import annotations

import unittest
from asyncio import run

from app.adapters.external.ai.ollama_client import (
    OllamaChatRequest,
    OllamaClient,
    extract_json_object,
)
from app.core.ports.ai_errors import NonTransientAIError, TransientAIError
from tests.commons.vcr_config import make_vcr

BASE_URL = "http://ollama.test:11434"


class FakeResponse:
    """Minimal stand-in for a niquests response."""

    def __init__(self, status_code: int, payload: dict | None = None, text: str = "") -> None:
        self.status_code = status_code
        self._payload = payload
        self.text = text

    def json(self):
        if self._payload is None:
            raise ValueError("no JSON body")
        return self._payload


class FakeSession:
    """Session factory recording the request and returning a canned answer."""

    def __init__(self, response: FakeResponse | Exception) -> None:
        self.response = response
        self.requests: list[dict] = []
        self.closed = False

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.closed = True
        return False

    def post(self, url, json=None, timeout=None):
        self.requests.append({"url": url, "json": json, "timeout": timeout})
        if isinstance(self.response, Exception):
            raise self.response
        return self.response


def make_client(response: FakeResponse | Exception) -> tuple[OllamaClient, FakeSession]:
    session = FakeSession(response)
    client = OllamaClient(BASE_URL, timeout_seconds=42, session_factory=lambda: session)
    return client, session


def chat_request(**overrides) -> OllamaChatRequest:
    payload = {
        "model": "minimax-m3.1-flash:cloud",
        "messages": [{"role": "system", "content": "role"}, {"role": "user", "content": "task"}],
        "num_predict": 8000,
    }
    payload.update(overrides)
    return OllamaChatRequest(**payload)


class TestOllamaClient(unittest.TestCase):
    def test_posts_the_ollama_chat_contract(self):
        client, session = make_client(
            FakeResponse(
                200,
                {
                    "model": "minimax-m3.1-flash:cloud",
                    "message": {"role": "assistant", "content": '{"ok": true}'},
                    "done": True,
                    "done_reason": "stop",
                    "eval_count": 12,
                    "prompt_eval_count": 34,
                },
            )
        )
        response = run(client.chat(chat_request()))

        self.assertEqual(len(session.requests), 1)
        sent = session.requests[0]
        self.assertEqual(sent["url"], f"{BASE_URL}/api/chat")
        body = sent["json"]
        self.assertEqual(body["model"], "minimax-m3.1-flash:cloud")
        self.assertFalse(body["stream"])
        self.assertEqual(body["format"], "json")
        self.assertEqual(body["options"]["num_predict"], 8000)
        self.assertEqual(body["keep_alive"], "10m")
        self.assertEqual([m["role"] for m in body["messages"]], ["system", "user"])

        self.assertEqual(response.content, '{"ok": true}')
        self.assertEqual(response.done_reason, "stop")
        self.assertEqual(response.eval_count, 12)
        self.assertEqual(response.prompt_eval_count, 34)

    def test_timeout_and_connection_errors_are_transient(self):
        client, _ = make_client(ConnectionError("connection refused"))
        with self.assertRaises(TransientAIError):
            run(client.chat(chat_request()))

    def test_server_errors_are_transient(self):
        for status in (429, 500, 502, 503):
            client, _ = make_client(FakeResponse(status, {"error": "overloaded"}))
            with self.assertRaises(TransientAIError):
                run(client.chat(chat_request()))

    def test_client_errors_are_non_transient(self):
        for status in (400, 401, 403, 404):
            client, _ = make_client(FakeResponse(status, {"error": "model not found"}))
            with self.assertRaises(NonTransientAIError):
                run(client.chat(chat_request()))

    def test_truncated_answer_is_transient(self):
        client, _ = make_client(
            FakeResponse(
                200,
                {
                    "model": "m",
                    "message": {"role": "assistant", "content": '{"partial": '},
                    "done": True,
                    "done_reason": "length",
                },
            )
        )
        with self.assertRaises(TransientAIError):
            run(client.chat(chat_request()))

    def test_empty_answer_is_transient(self):
        client, _ = make_client(
            FakeResponse(200, {"model": "m", "message": {"role": "assistant", "content": "  "}})
        )
        with self.assertRaises(TransientAIError):
            run(client.chat(chat_request()))

    def test_non_json_body_is_transient(self):
        client, _ = make_client(FakeResponse(200, None, text="<html>gateway</html>"))
        with self.assertRaises(TransientAIError):
            run(client.chat(chat_request()))

    def test_missing_message_is_transient(self):
        client, _ = make_client(FakeResponse(200, {"model": "m", "done": True}))
        with self.assertRaises(TransientAIError):
            run(client.chat(chat_request()))


class TestExtractJsonObject(unittest.TestCase):
    def test_plain_json_is_returned_unchanged(self):
        self.assertEqual(extract_json_object('{"a": 1}'), '{"a": 1}')

    def test_markdown_fence_is_stripped(self):
        raw = '```json\n{"a": 1}\n```'
        self.assertEqual(extract_json_object(raw), '{"a": 1}')

    def test_prose_around_the_object_is_removed(self):
        raw = 'Here you go:\n{"a": 1}\nHope it helps.'
        self.assertEqual(extract_json_object(raw), '{"a": 1}')

    def test_answer_without_an_object_is_transient(self):
        with self.assertRaises(TransientAIError):
            extract_json_object("no json here")


class TestOllamaClientWithCassette(unittest.TestCase):
    """Replays a recorded provider exchange — no network access."""

    def test_replays_the_recorded_chat(self):
        vcr = make_vcr("ollama_chat.yaml")
        client = OllamaClient("http://ollama.test:11434", timeout_seconds=42)
        with vcr.use_cassette("ollama_chat.yaml"):
            response = run(client.chat(chat_request()))
        self.assertTrue(response.content)
        self.assertEqual(response.done_reason, "stop")


if __name__ == "__main__":
    unittest.main()

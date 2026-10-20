"""Composition-root wiring tests (T119).

The provider pair is selected TOGETHER (constitution principle II), the
test environment never reaches the network, and the development fallback
swaps the adapters in place (the services hold the port, not the
concrete adapter).
"""

from __future__ import annotations

import unittest
from asyncio import run

from app.adapters.external.ai.deterministic_ai import (
    DeterministicContentEvaluator,
    DeterministicContentGenerator,
)
from app.core.config.settings import Settings
from main import _SwappableEvaluator, _SwappableGenerator, _build_ai_pair


class TestAIProviderSelection(unittest.TestCase):
    def test_the_test_environment_never_touches_the_network(self):
        settings = Settings(app_env="test", ai_provider="ollama")
        generator, evaluator = _build_ai_pair(settings)
        self.assertIsInstance(generator, DeterministicContentGenerator)
        self.assertIsInstance(evaluator, DeterministicContentEvaluator)

    def test_the_deterministic_provider_forces_the_offline_pair(self):
        settings = Settings(app_env="development", ai_provider="deterministic")
        generator, evaluator = _build_ai_pair(settings)
        self.assertIsInstance(generator, DeterministicContentGenerator)
        self.assertIsInstance(evaluator, DeterministicContentEvaluator)

    def test_the_ollama_provider_builds_two_distinct_models(self):
        settings = Settings(
            app_env="development",
            ai_provider="ollama",
            ai_generation_model="model-a",
            ai_evaluation_model="model-b",
        )
        generator, evaluator = _build_ai_pair(settings)
        self.assertNotEqual(generator.model_id, evaluator.model_id)
        self.assertEqual(generator.model_id, "model-a")
        self.assertEqual(evaluator.model_id, "model-b")

    def test_the_two_adapters_share_no_client(self):
        settings = Settings(app_env="development", ai_provider="ollama")
        generator, evaluator = _build_ai_pair(settings)
        self.assertIsNot(generator._client, evaluator._client)


class TestSwappableAdapters(unittest.TestCase):
    def test_the_delegate_forwards_to_the_adapter(self):
        delegate = _SwappableGenerator(DeterministicContentGenerator())
        self.assertEqual(delegate.model_id, "deterministic-generator-v1")
        result = run(
            delegate.generate(
                "instruction",
                _inputs(),
            )
        )
        self.assertIn("reading", result.payload)

    def test_the_evaluator_delegate_forwards_to_the_adapter(self):
        delegate = _SwappableEvaluator(DeterministicContentEvaluator())
        self.assertEqual(delegate.model_id, "deterministic-evaluator-v1")

    def test_swapping_replaces_the_adapter_in_place(self):
        """The services hold the delegate, so a swap is seen by them."""
        delegate = _SwappableGenerator(DeterministicContentGenerator())
        self.assertEqual(delegate.model_id, "deterministic-generator-v1")
        delegate.swap(DeterministicContentGenerator())
        self.assertEqual(delegate.model_id, "deterministic-generator-v1")


class TestStartupFallback(unittest.TestCase):
    """The provider is primed at startup: fail fast outside development,
    contained locally (the deterministic pair takes over)."""

    def test_an_unreachable_provider_fails_the_startup_outside_development(self):
        from main import Container

        settings = Settings(
            app_env="production",
            ai_provider="ollama",
            ai_base_url="http://127.0.0.1:1",  # nothing listens there
            ai_request_timeout_seconds=1,
        )
        container = Container.__new__(Container)  # no MongoDB needed
        container.settings = settings
        container.generator = _SwappableGenerator(DeterministicContentGenerator())
        container.evaluator = _SwappableEvaluator(DeterministicContentEvaluator())
        with self.assertRaises(Exception):
            run(container._prime_ai_provider())

    def test_an_unreachable_provider_falls_back_in_development(self):
        from main import Container

        settings = Settings(
            app_env="development",
            ai_provider="ollama",
            ai_base_url="http://127.0.0.1:1",  # nothing listens there
            ai_request_timeout_seconds=1,
        )
        container = Container.__new__(Container)  # no MongoDB needed
        container.settings = settings
        container.generator = _SwappableGenerator(DeterministicContentGenerator())
        container.evaluator = _SwappableEvaluator(DeterministicContentEvaluator())

        run(container._prime_ai_provider())

        # Contained: the app keeps running with the deterministic pair.
        self.assertEqual(container.generator.model_id, "deterministic-generator-v1")
        self.assertEqual(container.evaluator.model_id, "deterministic-evaluator-v1")


def _inputs():
    from app.core.entities.materials import GenerationInputs

    return GenerationInputs(
        cefr_level="B1", purpose="daily practice", history_slice=["Reviewed the present simple."]
    )


if __name__ == "__main__":
    unittest.main()

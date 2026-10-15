"""Settings.validate_mandatory tests: SECRETS_ENDPOINT_URL is mandatory only
for the ``localstack`` provider; the real Secrets Manager provider (AWS or a
LocalStack edge via AWS_ENDPOINT_URL) validates without it."""

from __future__ import annotations

import unittest

from app.core.config import Settings
from app.core.errors import ConfigurationError


def make_settings(**overrides) -> Settings:
    base = {"mongodb_uri": "mongodb://localhost:27017"}
    base.update(overrides)
    return Settings(**base).validate_mandatory()


class TestAwsClientCredentials(unittest.TestCase):
    """The environment — not the URL — decides the boto3 kwargs dict."""

    def test_development_gets_localstack_parameterization(self):
        from app.core.config import aws_client_credentials

        settings = aws_client_credentials("development")
        self.assertEqual(settings["aws_access_key_id"], "test")
        self.assertEqual(settings["aws_secret_access_key"], "test")
        self.assertIn("endpoint_url", settings)

    def test_non_development_gets_the_basic_client(self):
        from app.core.config import aws_client_credentials

        self.assertEqual(aws_client_credentials("production"), {})
        self.assertEqual(aws_client_credentials("test"), {})
        self.assertEqual(aws_client_credentials("staging"), {})


class TestSettingsMandatory(unittest.TestCase):
    def test_localstack_without_endpoint_endpoint_is_rejected(self):
        self.assertRaises(
            ConfigurationError,
            make_settings,
            secrets_provider="localstack",
            secrets_endpoint_url="",
        )

    def test_localstack_with_endpoint_is_accepted(self):
        settings = make_settings(
            secrets_provider="localstack",
            secrets_endpoint_url="http://localhost:4566",
        )
        self.assertEqual(settings.secrets_endpoint_url, "http://localhost:4566")

    def test_real_secrets_manager_provider_validates_without_endpoint(self):
        settings = make_settings(secrets_provider="secretsmanager", secrets_endpoint_url="")
        self.assertEqual(settings.aws_region, "us-east-1")

    def test_aws_provider_alias_is_accepted(self):
        make_settings(secrets_provider="aws", secrets_endpoint_url="")

    def test_missing_mongodb_uri_is_rejected(self):
        self.assertRaises(
            ConfigurationError, make_settings, mongodb_uri="", secrets_endpoint_url=""
        )

    def test_empty_mongodb_database_is_rejected(self):
        self.assertRaises(
            ConfigurationError,
            make_settings,
            mongodb_database=" ",
            secrets_endpoint_url="",
        )


if __name__ == "__main__":
    unittest.main()
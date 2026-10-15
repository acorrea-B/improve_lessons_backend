"""Public surface of the configuration package.

Import-only facade: re-exports from the sibling modules. No functional
code lives in ``__init__`` (module definition files: ``settings.py`` and
``secret_provider.py``).
"""

from app.core.config.settings import (
    DEFAULT_CORRECTIVE_LOOP_BOUND,
    FEATURES,
    LOCALSTACK_AWS_CREDENTIALS,
    Settings,
    aws_client_credentials,
    get_settings,
)

__all__ = [
    "DEFAULT_CORRECTIVE_LOOP_BOUND",
    "FEATURES",
    "LOCALSTACK_AWS_CREDENTIALS",
    "Settings",
    "aws_client_credentials",
    "get_settings",
]
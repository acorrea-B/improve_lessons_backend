"""Provider error hierarchy for the AI adapters (constitution principle X).

The corrective loop distinguishes two failure classes:

- ``TransientAIError`` — retryable (timeout, connection error, HTTP 429,
  HTTP >= 500, truncated/unparseable answer). The loop absorbs it and
  retries, within the SAME bound as a corrective revision (A-17: no
  separate transient-failure counter is maintained).
- ``NonTransientAIError`` — permanent (unknown model, invalid request,
  unauthorized). Retrying is pointless, so the failure leaves the loop
  immediately.

Both are domain errors of the provider boundary; the API layer maps
them to the documented error envelope without leaking provider text.
"""

from __future__ import annotations


class AIProviderError(Exception):
    """Base class for every AI provider failure."""

    def __init__(self, message: str, *, provider: str = "", status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code


class TransientAIError(AIProviderError):
    """Retryable provider failure (absorbed by the corrective loop within
    the same bound; constitution principle X)."""


class NonTransientAIError(AIProviderError):
    """Permanent provider failure (leaves the corrective loop at once)."""

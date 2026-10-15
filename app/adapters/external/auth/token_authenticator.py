"""HMAC token authenticator (T035, research.md § 7 placeholder).

The exact authentication mechanism is a deferred decision; this adapter
implements the ``Authenticator`` port with a signed stateless token
(stdlib ``hmac``/``hashlib`` — no extra dependency) whose signing key is
read through the ``SecretProvider`` boundary. Logout revokes all tokens
issued before the revocation instant via ``users.session_valid_after``
(enforced by the caller using the returned ``issued_at``).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
from datetime import timedelta

from app.core.ports.auth import AuthContext
from app.core.time.utc import now_utc, parse_iso_to_utc


class TokenAuthenticator:
    TOKEN_TTL_SECONDS = 7 * 24 * 3600

    def __init__(self, signing_key: str, token_ttl_seconds: int | None = None) -> None:
        self._signing_key = signing_key.encode()
        if token_ttl_seconds:
            self.TOKEN_TTL_SECONDS = token_ttl_seconds

    async def issue_token(self, user_id: str) -> str:
        issued_at = now_utc()
        body = f"{user_id}|{issued_at.isoformat()}"
        signature = hmac.new(self._signing_key, body.encode(), hashlib.sha256).hexdigest()
        payload = base64.urlsafe_b64encode(body.encode()).decode().rstrip("=")
        return f"{payload}.{signature}"

    async def authenticate(self, token: str) -> "AuthContext | None":
        try:
            payload, signature = token.rsplit(".", 1)
            body = base64.urlsafe_b64decode(
                payload + "=" * (-len(payload) % 4)
            ).decode()
            expected = hmac.new(self._signing_key, body.encode(), hashlib.sha256).hexdigest()
            if not hmac.compare_digest(signature, expected):
                return None
            user_id, issued_at_iso = body.split("|", 1)
            issued_at = parse_iso_to_utc(issued_at_iso)
        except Exception:
            return None
        if now_utc() - issued_at > timedelta(seconds=self.TOKEN_TTL_SECONDS):
            return None
        return AuthContext(user_id=user_id, issued_at=issued_at)
"""User service (T034, US-1).

Owns registration, profile read/update, profile-history append, and the
audit rows for every US-1 operation (T036).
"""

from __future__ import annotations

import hashlib
import secrets
from typing import TYPE_CHECKING

from app.core.entities.enums import CEFRLevel
from app.core.entities.feature_availability import AuditEvent
from app.core.entities.user import ProfileChange, User
from app.core.errors import ConflictError, NotFoundError, UnauthorizedError, ValidationErrorDetail
from app.core.ports.audit_event_repository import AuditEventRepository
from app.core.ports.user_profile_history_repository import UserProfileHistoryRepository
from app.core.ports.user_repository import UserRepository
from app.core.strategies.submission_status_strategy import validate_time_zone
from app.core.time.utc import now_utc
from app.utils.logging import get_logger, report_info

if TYPE_CHECKING:
    from datetime import datetime

logger = get_logger("services.user")


def hash_password(plain: str | None) -> str | None:
    """PBKDF2-HMAC password hash (stdlib; research.md § 7 placeholder)."""
    if plain is None:
        return None
    salt = secrets.token_hex(16)
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 100_000)
    return f"pbkdf2${salt}${digest.hex()}"


def verify_password(plain: str, stored: str) -> bool:
    try:
        algorithm, salt, expected_hex = stored.split("$")
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", plain.encode(), salt.encode(), 100_000)
    return algorithm == "pbkdf2" and secrets.compare_digest(digest.hex(), expected_hex)


_CEFR = {value.value for value in CEFRLevel}


def _validate_cefr(value: str) -> CEFRLevel:
    try:
        return CEFRLevel(value)
    except ValueError as exc:
        raise ValidationErrorDetail(
            code="invalid_cefr_level",
            message="cefr_level must be one of A1, A2, B1, B2, C1, C2.",
            details={"field": "cefr_level", "value": value},
        ) from exc


class UserService:
    def __init__(
        self,
        users: UserRepository,
        profile_history: UserProfileHistoryRepository,
        audit_events: AuditEventRepository,
    ) -> None:
        self._users = users
        self._profile_history = profile_history
        self._audit = audit_events

    async def register(
        self,
        *,
        name: str,
        email: str,
        cefr_level: str,
        time_zone: str,
        password: str | None = None,
    ) -> User:
        if not name.strip():
            raise ValidationErrorDetail(
                code="invalid_name", message="name must not be empty.",
                details={"field": "name"},
            )
        validate_time_zone(time_zone)
        level = _validate_cefr(cefr_level)
        normalized = email.strip().lower()
        existing = await self._users.get_by_email(normalized)
        if existing is not None:
            raise ConflictError(
                "email_already_registered",
                "An account with this email already exists.",
                details={"field": "email"},
            )
        from datetime import UTC, datetime as _datetime

        stamp = now_utc()
        user = User(
            name=name.strip(),
            email=normalized,
            cefr_level=level,
            time_zone=time_zone,
            password_hash=hash_password(password),
            created_at=stamp,
            updated_at=stamp,
            version=1,
        )
        await self._users.insert_user(user)
        await self._audit.insert(
            AuditEvent(
                owner_user_id=str(user.id),
                event_type="user.registered",
                payload={"cefr_level": level.value, "time_zone": time_zone},
            )
        )
        report_info("user.registered", "user registered", user_id=str(user.id))
        return user

    async def get_me(self, user_id: str) -> User:
        user = await self._users.get_by_id(user_id)
        if user is None:
            raise NotFoundError(
                "user_not_found", "No user matches the authenticated principal."
            )
        return user

    async def update_me(
        self, user_id: str, changes: dict[str, str | None]
    ) -> User:
        user = await self.get_me(user_id)
        previous: dict[str, str | None] = {}
        for field, value in changes.items():
            if field not in ("name", "preferred_name", "email", "cefr_level", "time_zone"):
                raise ValidationErrorDetail(
                    code="invalid_field", message=f"Field '{field}' is not updatable.",
                    details={"field": field},
                )
            current = getattr(user, field)
            current_str = str(current.value if isinstance(current, CEFRLevel) else current)
            if field == "cefr_level":
                new_value = str(_validate_cefr(str(value)).value)
                setattr(user, field, _validate_cefr(str(value)))
            elif field == "time_zone":
                validate_time_zone(str(value))
                new_value = str(value)
                setattr(user, field, new_value)
            elif field == "email":
                new_value = str(value).strip().lower()
                conflicting = await self._users.get_by_email(new_value)
                if conflicting is not None and str(conflicting.id) != user_id:
                    raise ConflictError(
                        "email_already_registered",
                        "An account with this email already exists.",
                        details={"field": "email"},
                    )
                current_str = current_str.lower()
                setattr(user, field, new_value)
            else:
                if value is not None and not str(value).strip() and field in ("name",):
                    raise ValidationErrorDetail(
                        code="invalid_name", message="name must not be empty.",
                        details={"field": "name"},
                    )
                new_value = None if value is None else str(value)
                setattr(user, field, new_value)
            previous[field] = current_str
        await self._users.update(user)
        await self._profile_history.append(
            ProfileChange(
                user_id=user_id,
                changed_fields={
                    field: {"previous": old, "new": str(getattr(user, field))}
                    for field, old in previous.items()
                },
                changed_at=now_utc(),
                version=1,
            )
        )
        await self._audit.insert(
            AuditEvent(
                owner_user_id=user_id,
                event_type="user.updated",
                payload={
                    "changed_fields": sorted(previous),
                    "time_zone": user.time_zone,
                },
            )
        )
        await self._audit.insert(
            AuditEvent(
                owner_user_id=user_id,
                event_type="user.profile_history_appended",
                payload={"changed_fields": sorted(previous)},
            )
        )
        report_info("user.updated", "profile updated", user_id=user_id)
        return user

    async def verify_login(self, email: str, password: str | None) -> User:
        """Credential check (mechanism deferred; email-only when the
        account has no password set)."""
        user = await self._users.get_by_email(email.strip().lower())
        if user is None:
            raise UnauthorizedError("invalid_credentials", "Email or password is incorrect.")
        if user.password_hash is None:
            return user
        if password is None or not verify_password(password, user.password_hash):
            raise UnauthorizedError("invalid_credentials", "Email or password is incorrect.")
        return user

    async def record_logout(self, user_id: str) -> None:
        user = await self.get_me(user_id)
        user.session_valid_after = now_utc()
        await self._users.update(user)
        await self._audit.insert(
            AuditEvent(
                owner_user_id=user_id,
                event_type="user.logged_out",
                payload={"session_valid_after": now_utc().isoformat()},
            )
        )
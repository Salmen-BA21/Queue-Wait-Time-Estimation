"""Authentication helpers for QueueVision API."""

from __future__ import annotations

import hashlib
import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal, Optional
from uuid import uuid4

from jose import JWTError, jwt
from passlib.context import CryptContext

from src.config import (
    AUTH_ACCESS_TOKEN_TTL_MINUTES,
    AUTH_BOOTSTRAP_ADMIN_EMAIL,
    AUTH_BOOTSTRAP_ADMIN_NAME,
    AUTH_BOOTSTRAP_ADMIN_PASSWORD,
    AUTH_LOCKOUT_MINUTES,
    AUTH_MAX_FAILED_LOGINS,
    AUTH_MIN_PASSWORD_LENGTH,
    AUTH_REFRESH_TOKEN_TTL_HOURS,
    AUTH_SECRET_KEY,
)
from src.database import create_auth_audit_event, create_user, get_user_by_email


ACCESS_TOKEN_COOKIE_NAME = "queuevision_access_token"
REFRESH_TOKEN_COOKIE_NAME = "queuevision_refresh_token"
ACCESS_TOKEN_COOKIE_MAX_AGE = AUTH_ACCESS_TOKEN_TTL_MINUTES * 60
REFRESH_TOKEN_COOKIE_MAX_AGE = AUTH_REFRESH_TOKEN_TTL_HOURS * 3600
JWT_ALGORITHM = "HS256"

password_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


@dataclass(frozen=True)
class AuthenticatedUser:
    """Authenticated user record used by API dependencies."""

    id: int
    email: str
    display_name: str
    role: Literal["admin", "manager"]
    is_active: bool
    created_at: str
    last_login_at: Optional[str]


@dataclass(frozen=True)
class DecodedAccessToken:
    """Decoded and validated access token payload."""

    user_id: int
    email: str
    role: Literal["admin", "manager"]
    expires_at: datetime


def utc_now() -> datetime:
    """Return a timezone-aware UTC timestamp."""
    return datetime.now(timezone.utc)


def isoformat_utc(dt: datetime) -> str:
    """Serialize a datetime as UTC ISO string."""
    return dt.astimezone(timezone.utc).isoformat()


def parse_iso_datetime(value: str | None) -> Optional[datetime]:
    """Parse ISO datetime strings from SQLite columns."""
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def hash_password(password: str) -> str:
    """Hash one plaintext password with bcrypt."""
    return password_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Verify plaintext password against bcrypt hash."""
    return password_context.verify(password, password_hash)


def hash_refresh_token(token: str) -> str:
    """Hash refresh-token material before persistence."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def create_access_token(*, user_id: int, email: str, role: Literal["admin", "manager"]) -> str:
    """Build a signed short-lived access JWT."""
    expires_at = utc_now() + timedelta(minutes=AUTH_ACCESS_TOKEN_TTL_MINUTES)
    payload = {
        "sub": str(user_id),
        "email": email,
        "role": role,
        "typ": "access",
        "exp": int(expires_at.timestamp()),
    }
    return jwt.encode(payload, AUTH_SECRET_KEY, algorithm=JWT_ALGORITHM)


def decode_access_token(token: str) -> Optional[DecodedAccessToken]:
    """Decode and validate an access JWT payload."""
    try:
        payload = jwt.decode(token, AUTH_SECRET_KEY, algorithms=[JWT_ALGORITHM])
    except JWTError:
        return None

    if payload.get("typ") != "access":
        return None

    raw_user_id = payload.get("sub")
    raw_email = payload.get("email")
    raw_role = payload.get("role")
    raw_exp = payload.get("exp")

    if not isinstance(raw_user_id, str) or not raw_user_id.isdigit():
        return None
    if not isinstance(raw_email, str) or not raw_email.strip():
        return None
    if raw_role not in {"admin", "manager"}:
        return None
    if not isinstance(raw_exp, (int, float)):
        return None

    return DecodedAccessToken(
        user_id=int(raw_user_id),
        email=raw_email,
        role=raw_role,
        expires_at=datetime.fromtimestamp(raw_exp, tz=timezone.utc),
    )


def generate_refresh_token() -> str:
    """Generate high-entropy refresh token material."""
    return secrets.token_urlsafe(48)


def create_refresh_session_id() -> str:
    """Generate unique refresh-session ID."""
    return str(uuid4())


def refresh_token_expiry_iso() -> str:
    """Return ISO expiration for refresh session rows."""
    return isoformat_utc(utc_now() + timedelta(hours=AUTH_REFRESH_TOKEN_TTL_HOURS))


def is_account_locked(user_record: dict[str, Any]) -> bool:
    """Return True when a user is still inside lockout window."""
    locked_until = parse_iso_datetime(user_record.get("locked_until"))
    return bool(locked_until and utc_now() < locked_until)


def next_lockout_until_iso() -> str:
    """Compute lockout-until timestamp from security policy."""
    return isoformat_utc(utc_now() + timedelta(minutes=AUTH_LOCKOUT_MINUTES))


def validate_password_policy(password: str) -> Optional[str]:
    """Return violation message when a password breaks policy constraints."""
    if len(password) < AUTH_MIN_PASSWORD_LENGTH:
        return f"Password must be at least {AUTH_MIN_PASSWORD_LENGTH} characters long."

    has_upper = any(ch.isupper() for ch in password)
    has_lower = any(ch.islower() for ch in password)
    has_digit = any(ch.isdigit() for ch in password)

    if not (has_upper and has_lower and has_digit):
        return "Password must include upper-case, lower-case, and numeric characters."

    return None


def lockout_threshold_reached(failed_attempts: int) -> bool:
    """Return True when failed attempts should trigger account lockout."""
    return failed_attempts >= AUTH_MAX_FAILED_LOGINS


def user_record_to_authenticated_user(user_record: dict[str, Any]) -> AuthenticatedUser:
    """Convert a database user row into dependency-friendly object."""
    return AuthenticatedUser(
        id=int(user_record["id"]),
        email=str(user_record["email"]),
        display_name=str(user_record["display_name"]),
        role=user_record["role"],
        is_active=bool(user_record["is_active"]),
        created_at=str(user_record["created_at"]),
        last_login_at=user_record.get("last_login_at"),
    )


def ensure_bootstrap_admin_account() -> None:
    """Create initial admin account from environment variables when missing."""
    email = AUTH_BOOTSTRAP_ADMIN_EMAIL.strip().lower()
    password = AUTH_BOOTSTRAP_ADMIN_PASSWORD.strip()
    display_name = AUTH_BOOTSTRAP_ADMIN_NAME.strip() or "QueueVision Admin"

    if not email or not password:
        return

    existing = get_user_by_email(email)
    if existing:
        return

    policy_error = validate_password_policy(password)
    if policy_error:
        create_auth_audit_event(
            user_id=None,
            event_type="bootstrap_admin",
            event_status="failed",
            details={"email": email, "reason": policy_error},
        )
        return

    try:
        admin_id = create_user(
            email=email,
            display_name=display_name,
            password_hash=hash_password(password),
            role="admin",
        )
    except sqlite3.IntegrityError:
        return

    create_auth_audit_event(
        user_id=admin_id,
        event_type="bootstrap_admin",
        event_status="created",
        details={"email": email},
    )

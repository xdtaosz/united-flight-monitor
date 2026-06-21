"""Session persistence manager for United Airlines auth tokens and cookies.

Stores:
  - Browser cookies (Playwright-compatible format)
  - Bearer token (x-authorization-api for direct API calls)

Avoids repeated login + MFA challenges by persisting session state to disk.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

DEFAULT_SESSION_TTL_HOURS = 24
MAX_IDLE_HOURS = 12
SESSION_VERSION = 2


class SessionManager:
    """Persistent auth session manager.

    Session file: {sessions_dir}/united_session.json
    Contains: version, airline, cookies, bearer_token, created_at, expires_at, last_used.
    """

    def __init__(self, session_dir: Path | None = None):
        if session_dir is None:
            from config import settings
            session_dir = settings.sessions_dir
        self.session_dir = Path(session_dir)
        self.session_dir.mkdir(parents=True, exist_ok=True)

    def _file_path(self, airline: str) -> Path:
        return self.session_dir / f"{airline}_session.json"

    # --- Load ---

    def load(self, airline: str) -> dict[str, Any] | None:
        """Load session data. Returns None if missing, expired, idle too long, or corrupt."""
        path = self._file_path(airline)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return None

        if not isinstance(data, dict):
            return None

        expires_str = data.get("expires_at", "")
        if self._is_expired(expires_str):
            path.unlink(missing_ok=True)
            return None

        last_used_str = data.get("last_used", data.get("created_at", ""))
        if self._is_idle_too_long(last_used_str):
            path.unlink(missing_ok=True)
            return None

        return data

    def is_valid(self, airline: str) -> bool:
        return self.load(airline) is not None

    def touch(self, airline: str) -> bool:
        """Update last_used timestamp and extend expiry."""
        path = self._file_path(airline)
        if not path.exists():
            return False
        try:
            data = json.loads(path.read_text())
        except (json.JSONDecodeError, OSError):
            return False
        now = datetime.now(timezone.utc)
        data["last_used"] = now.isoformat()
        data["expires_at"] = (now + timedelta(hours=DEFAULT_SESSION_TTL_HOURS)).isoformat()
        path.write_text(json.dumps(data, indent=2))
        return True

    # --- Save ---

    def save(
        self,
        airline: str,
        cookies: list[dict[str, Any]],
        bearer_token: str,
        ttl_hours: int = DEFAULT_SESSION_TTL_HOURS,
        metadata: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now(timezone.utc)
        data: dict[str, Any] = {
            "version": SESSION_VERSION,
            "airline": airline,
            "cookies": cookies,
            "bearer_token": bearer_token,
            "created_at": now.isoformat(),
            "expires_at": (now + timedelta(hours=ttl_hours)).isoformat(),
            "last_used": now.isoformat(),
            "metadata": metadata or {},
        }
        path = self._file_path(airline)
        path.write_text(json.dumps(data, indent=2))

    # --- Delete ---

    def delete(self, airline: str) -> None:
        self._file_path(airline).unlink(missing_ok=True)

    # --- Accessors ---

    def get_bearer_token(self, airline: str) -> str | None:
        data = self.load(airline)
        if data:
            return data.get("bearer_token")
        return None

    def get_cookies_playwright(self, airline: str) -> list[dict[str, Any]] | None:
        """Return cookies in Playwright-compatible format."""
        data = self.load(airline)
        if data:
            return data.get("cookies")
        return None

    # --- Internal ---

    @staticmethod
    def _is_expired(expires_str: str) -> bool:
        if not expires_str:
            return True
        try:
            expires = datetime.fromisoformat(expires_str)
            return datetime.now(timezone.utc) > expires
        except ValueError:
            return True

    @staticmethod
    def _is_idle_too_long(last_used_str: str) -> bool:
        if not last_used_str:
            return True
        try:
            last_used = datetime.fromisoformat(last_used_str)
            idle = datetime.now(timezone.utc) - last_used
            return idle > timedelta(hours=MAX_IDLE_HOURS)
        except ValueError:
            return True


# ---------------------------------------------------------------------------
# Helper: extract x-authorization-api bearer token from request headers
# ---------------------------------------------------------------------------

def extract_bearer_from_request_headers(headers: dict[str, str]) -> str | None:
    """Extract bearer token from x-authorization-api header.

    United's API uses:  x-authorization-api: bearer DAAAA...
    """
    raw = headers.get("x-authorization-api", "")
    if raw.lower().startswith("bearer "):
        token = raw[7:].strip()
        if token:
            return token
    return None

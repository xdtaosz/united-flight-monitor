"""Tests for session manager."""

import json
from datetime import datetime, timedelta, timezone

from session import SessionManager, extract_bearer_from_request_headers


class TestSessionManager:
    def test_save_and_load(self, tmp_path):
        sm = SessionManager(session_dir=tmp_path)
        sm.save("united", [{"name": "test", "value": "v1", "domain": ".united.com"}], "token_abc")
        data = sm.load("united")
        assert data is not None
        assert data["bearer_token"] == "token_abc"
        assert len(data["cookies"]) == 1

    def test_is_valid(self, tmp_path):
        sm = SessionManager(session_dir=tmp_path)
        assert sm.is_valid("united") is False
        sm.save("united", [], "token")
        assert sm.is_valid("united") is True

    def test_delete(self, tmp_path):
        sm = SessionManager(session_dir=tmp_path)
        sm.save("united", [], "token")
        assert sm.is_valid("united") is True
        sm.delete("united")
        assert sm.is_valid("united") is False

    def test_missing_file(self, tmp_path):
        sm = SessionManager(session_dir=tmp_path)
        assert sm.load("nonexistent") is None

    def test_expired_session(self, tmp_path):
        sm = SessionManager(session_dir=tmp_path)
        data = {
            "version": 2,
            "airline": "united",
            "cookies": [],
            "bearer_token": "old_token",
            "created_at": (datetime.now(timezone.utc) - timedelta(hours=48)).isoformat(),
            "expires_at": (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat(),
        }
        path = sm._file_path("united")
        path.write_text(json.dumps(data))
        assert sm.load("united") is None

    def test_touch(self, tmp_path):
        sm = SessionManager(session_dir=tmp_path)
        sm.save("united", [], "token")
        assert sm.touch("united") is True
        data = sm.load("united")
        assert data is not None

    def test_get_bearer_token(self, tmp_path):
        sm = SessionManager(session_dir=tmp_path)
        sm.save("united", [], "secret_token")
        assert sm.get_bearer_token("united") == "secret_token"

    def test_get_cookies_playwright(self, tmp_path):
        sm = SessionManager(session_dir=tmp_path)
        cookies = [{"name": "sid", "value": "abc123", "domain": ".united.com"}]
        sm.save("united", cookies, "token")
        loaded = sm.get_cookies_playwright("united")
        assert loaded is not None
        assert loaded[0]["name"] == "sid"
        assert loaded[0]["value"] == "abc123"


class TestExtractBearer:
    def test_extract_valid(self):
        headers = {"x-authorization-api": "bearer DAAAA123456"}
        token = extract_bearer_from_request_headers(headers)
        assert token == "DAAAA123456"

    def test_extract_missing(self):
        headers = {"x-authorization-api": "token DAAAA"}
        token = extract_bearer_from_request_headers(headers)
        assert token is None

    def test_extract_no_header(self):
        token = extract_bearer_from_request_headers({})
        assert token is None

    def test_extract_empty_token(self):
        headers = {"x-authorization-api": "bearer "}
        token = extract_bearer_from_request_headers(headers)
        assert token is None

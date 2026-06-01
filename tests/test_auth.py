import json
import time
import pytest

from kudostracker import auth


def test_build_authorize_url():
    url = auth.build_authorize_url(
        client_id=123,
        redirect_uri="http://localhost:8765/callback",
        scopes=["read", "activity:read"],
    )
    assert "client_id=123" in url
    assert "response_type=code" in url
    assert "redirect_uri=http%3A%2F%2Flocalhost%3A8765%2Fcallback" in url
    assert "scope=read%2Cactivity%3Aread" in url
    assert url.startswith("https://www.strava.com/oauth/authorize")


def test_save_and_load_tokens(tmp_path):
    target = tmp_path / "tokens.json"
    auth.save_tokens(
        target,
        access_token="A",
        refresh_token="R",
        expires_at=1_900_000_000,
        client_id=123,
        client_secret="SEC",
    )
    loaded = auth.load_tokens(target)
    assert loaded == {
        "access_token": "A",
        "refresh_token": "R",
        "expires_at": 1_900_000_000,
        "client_id": 123,
        "client_secret": "SEC",
    }


def test_save_tokens_writes_0600_on_unix(tmp_path):
    import os
    import sys
    if sys.platform == "win32":
        pytest.skip("chmod semantics differ on Windows")
    target = tmp_path / "tokens.json"
    auth.save_tokens(target, "A", "R", 1, 1, "S")
    mode = target.stat().st_mode & 0o777
    assert mode == 0o600


def test_tokens_are_fresh_when_far_from_expiry():
    assert auth.tokens_are_fresh({"expires_at": int(time.time()) + 3600}) is True


def test_tokens_are_stale_when_expired():
    assert auth.tokens_are_fresh({"expires_at": int(time.time()) - 1}) is False


def test_tokens_are_stale_within_buffer():
    # Buffer is 60s
    assert auth.tokens_are_fresh({"expires_at": int(time.time()) + 30}) is False


def test_refresh_tokens_calls_stravalib_and_writes(tmp_path, mocker):
    target = tmp_path / "tokens.json"
    auth.save_tokens(target, "old_a", "old_r", 1, 999, "SEC")

    mock_client_cls = mocker.patch("kudostracker.auth.stravalib.Client")
    instance = mock_client_cls.return_value
    instance.refresh_access_token.return_value = {
        "access_token": "new_a",
        "refresh_token": "new_r",
        "expires_at": 1_999_999_999,
    }

    new = auth.refresh_tokens(target)
    instance.refresh_access_token.assert_called_once_with(
        client_id=999, client_secret="SEC", refresh_token="old_r"
    )
    assert new["access_token"] == "new_a"
    # File on disk is also updated
    on_disk = json.loads(target.read_text())
    assert on_disk["access_token"] == "new_a"
    assert on_disk["refresh_token"] == "new_r"
    assert on_disk["client_id"] == 999  # preserved
    assert on_disk["client_secret"] == "SEC"

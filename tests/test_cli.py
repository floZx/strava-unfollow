import json

from kudostracker import cli


def test_main_no_args_prints_help(capsys, monkeypatch):
    monkeypatch.setenv("KUDOSTRACKER_DATA_DIR", "/tmp/unused")
    rc = cli.main([])
    captured = capsys.readouterr()
    assert "usage" in captured.out.lower()
    assert rc != 0


def test_paste_followers_reads_clipboard_and_writes(tmp_path, monkeypatch, mocker):
    monkeypatch.setenv("KUDOSTRACKER_DATA_DIR", str(tmp_path))
    payload = json.dumps([
        {"id": 1, "name": "X", "url": "https://strava.com/athletes/1"},
    ])
    mocker.patch("kudostracker.cli.follower_io.read_from_clipboard", return_value=payload)
    rc = cli.main(["paste", "followers"])
    assert rc == 0
    saved = json.loads((tmp_path / "followers.json").read_text())
    assert saved[0]["id"] == 1


def test_paste_following_uses_following_path(tmp_path, monkeypatch, mocker):
    monkeypatch.setenv("KUDOSTRACKER_DATA_DIR", str(tmp_path))
    payload = json.dumps([
        {"id": 2, "name": "Y", "url": "https://strava.com/athletes/2"},
    ])
    mocker.patch("kudostracker.cli.follower_io.read_from_clipboard", return_value=payload)
    rc = cli.main(["paste", "following"])
    assert rc == 0
    assert (tmp_path / "following.json").exists()
    assert not (tmp_path / "followers.json").exists()


def test_paste_falls_back_to_editor_when_clipboard_unavailable(
    tmp_path, monkeypatch, mocker
):
    monkeypatch.setenv("KUDOSTRACKER_DATA_DIR", str(tmp_path))
    from kudostracker.follower_io import ClipboardUnavailable
    mocker.patch(
        "kudostracker.cli.follower_io.read_from_clipboard",
        side_effect=ClipboardUnavailable("nope"),
    )
    payload = json.dumps([
        {"id": 3, "name": "Z", "url": "https://strava.com/athletes/3"},
    ])
    mocker.patch("kudostracker.cli.follower_io.read_via_editor", return_value=payload)
    rc = cli.main(["paste", "followers"])
    assert rc == 0
    assert (tmp_path / "followers.json").exists()


def test_paste_invalid_payload_returns_nonzero(tmp_path, monkeypatch, mocker, capsys):
    monkeypatch.setenv("KUDOSTRACKER_DATA_DIR", str(tmp_path))
    mocker.patch(
        "kudostracker.cli.follower_io.read_from_clipboard", return_value="not json"
    )
    rc = cli.main(["paste", "followers"])
    assert rc != 0
    err = capsys.readouterr().err
    assert "JSON" in err


def test_report_writes_file(tmp_path, monkeypatch):
    monkeypatch.setenv("KUDOSTRACKER_DATA_DIR", str(tmp_path))
    # Set up minimal data
    (tmp_path / "followers.json").write_text(json.dumps([
        {"id": 1, "name": "Jean", "url": "https://strava.com/athletes/1"},
    ]))
    (tmp_path / "following.json").write_text(json.dumps([
        {"id": 1, "name": "Jean", "url": "https://strava.com/athletes/1"},
        {"id": 2, "name": "Marie", "url": "https://strava.com/athletes/2"},
    ]))
    # Need a db
    from kudostracker.storage import Storage
    s = Storage(tmp_path / "cache.db")
    s.init_schema()
    s.close()

    rc = cli.main(["report"])
    assert rc == 0
    report_path = tmp_path / "report.md"
    assert report_path.exists()
    content = report_path.read_text()
    assert "Jean" in content
    assert "Marie" in content


def test_report_missing_followers_returns_nonzero(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("KUDOSTRACKER_DATA_DIR", str(tmp_path))
    rc = cli.main(["report"])
    assert rc != 0
    err = capsys.readouterr().err
    assert "paste followers" in err


def test_sync_uses_authenticated_client(tmp_path, monkeypatch, mocker):
    monkeypatch.setenv("KUDOSTRACKER_DATA_DIR", str(tmp_path))
    # Pre-create valid tokens (not expired)
    import time as _time
    from kudostracker.auth import save_tokens
    save_tokens(
        tmp_path / "tokens.json",
        access_token="A", refresh_token="R",
        expires_at=int(_time.time()) + 3600,
        client_id=1, client_secret="S",
    )

    mock_client_cls = mocker.patch("kudostracker.cli.stravalib.Client")
    mock_sync_activities = mocker.patch(
        "kudostracker.cli.sync.sync_activities", return_value=3
    )
    mock_sync_kudoers = mocker.patch(
        "kudostracker.cli.sync.sync_kudoers", return_value=3
    )

    rc = cli.main(["sync"])
    assert rc == 0
    mock_client_cls.assert_called_once_with(access_token="A")
    assert mock_sync_activities.called
    assert mock_sync_kudoers.called


def test_sync_refreshes_expired_tokens(tmp_path, monkeypatch, mocker):
    monkeypatch.setenv("KUDOSTRACKER_DATA_DIR", str(tmp_path))
    import time as _time
    from kudostracker.auth import save_tokens
    save_tokens(
        tmp_path / "tokens.json",
        access_token="OLD", refresh_token="R",
        expires_at=int(_time.time()) - 10,
        client_id=1, client_secret="S",
    )

    def fake_refresh(path):
        save_tokens(path, "NEW", "R2", int(_time.time()) + 3600, 1, "S")
        return {"access_token": "NEW"}

    mocker.patch("kudostracker.cli.auth.refresh_tokens", side_effect=fake_refresh)
    mock_client_cls = mocker.patch("kudostracker.cli.stravalib.Client")
    mocker.patch("kudostracker.cli.sync.sync_activities", return_value=0)
    mocker.patch("kudostracker.cli.sync.sync_kudoers", return_value=0)

    rc = cli.main(["sync"])
    assert rc == 0
    mock_client_cls.assert_called_once_with(access_token="NEW")


def test_sync_missing_tokens_returns_nonzero(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("KUDOSTRACKER_DATA_DIR", str(tmp_path))
    rc = cli.main(["sync"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "auth" in err.lower()


def test_sync_returns_3_on_sync_aborted(tmp_path, monkeypatch, mocker):
    monkeypatch.setenv("KUDOSTRACKER_DATA_DIR", str(tmp_path))
    import time as _time
    from kudostracker.auth import save_tokens
    save_tokens(
        tmp_path / "tokens.json",
        access_token="A", refresh_token="R",
        expires_at=int(_time.time()) + 3600,
        client_id=1, client_secret="S",
    )
    mocker.patch("kudostracker.cli.stravalib.Client")
    mocker.patch(
        "kudostracker.cli.sync.sync_activities",
        side_effect=cli.sync.SyncAborted("rate limit"),
    )
    rc = cli.main(["sync"])
    assert rc == 3


def test_report_missing_following_returns_nonzero(tmp_path, monkeypatch, capsys):
    import json
    monkeypatch.setenv("KUDOSTRACKER_DATA_DIR", str(tmp_path))
    (tmp_path / "followers.json").write_text(json.dumps([]))
    rc = cli.main(["report"])
    assert rc != 0
    err = capsys.readouterr().err
    assert "paste following" in err


def test_auth_missing_credentials_returns_2(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("KUDOSTRACKER_DATA_DIR", str(tmp_path))
    monkeypatch.delenv("STRAVA_CLIENT_ID", raising=False)
    monkeypatch.delenv("STRAVA_CLIENT_SECRET", raising=False)
    rc = cli.main(["auth"])
    assert rc == 2
    err = capsys.readouterr().err
    assert "client" in err.lower()


def test_resolve_since_converts_tzaware_to_utc():
    from datetime import datetime, timezone
    result = cli._resolve_since("2026-01-01T12:00:00+02:00")
    # 12:00 +02:00 = 10:00 UTC
    assert result == datetime(2026, 1, 1, 10, 0, 0, tzinfo=timezone.utc)


def test_resolve_since_bare_date_assumed_utc():
    from datetime import datetime, timezone
    result = cli._resolve_since("2026-01-01")
    assert result == datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)


def test_sync_returns_2_on_access_unauthorized(tmp_path, monkeypatch, mocker):
    monkeypatch.setenv("KUDOSTRACKER_DATA_DIR", str(tmp_path))
    import time as _time
    from kudostracker.auth import save_tokens
    save_tokens(
        tmp_path / "tokens.json",
        access_token="A", refresh_token="R",
        expires_at=int(_time.time()) + 3600,
        client_id=1, client_secret="S",
    )
    mocker.patch("kudostracker.cli.stravalib.Client")
    import stravalib.exc as exc
    mocker.patch(
        "kudostracker.cli.sync.sync_activities",
        side_effect=exc.AccessUnauthorized("revoked"),
    )
    rc = cli.main(["sync"])
    assert rc == 2


def test_sync_bad_since_returns_1(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("KUDOSTRACKER_DATA_DIR", str(tmp_path))
    import time as _time
    from kudostracker.auth import save_tokens
    save_tokens(
        tmp_path / "tokens.json",
        access_token="A", refresh_token="R",
        expires_at=int(_time.time()) + 3600,
        client_id=1, client_secret="S",
    )
    rc = cli.main(["sync", "--since", "not-a-date"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "since" in err.lower()


def test_paste_returns_nonzero_on_editor_abort(tmp_path, monkeypatch, mocker, capsys):
    monkeypatch.setenv("KUDOSTRACKER_DATA_DIR", str(tmp_path))
    from kudostracker.follower_io import ClipboardUnavailable, EditorAborted
    mocker.patch(
        "kudostracker.cli.follower_io.read_from_clipboard",
        side_effect=ClipboardUnavailable("nope"),
    )
    mocker.patch(
        "kudostracker.cli.follower_io.read_via_editor",
        side_effect=EditorAborted("user aborted"),
    )
    rc = cli.main(["paste", "followers"])
    assert rc == 1
    err = capsys.readouterr().err
    assert "aborted" in err

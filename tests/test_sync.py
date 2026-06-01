from datetime import datetime, timezone
from types import SimpleNamespace

import pytest

from kudostracker import sync


def make_activity(id_, start_iso, name):
    return SimpleNamespace(
        id=id_,
        start_date=datetime.fromisoformat(start_iso.replace("Z", "+00:00")),
        name=name,
    )


def make_athlete(id_or_none, firstname, lastname):
    return SimpleNamespace(id=id_or_none, firstname=firstname, lastname=lastname)


def test_sync_activities_inserts_new_rows(storage, mocker):
    client = mocker.MagicMock()
    client.get_activities.return_value = iter([
        make_activity(1, "2026-01-01T10:00:00Z", "Run A"),
        make_activity(2, "2026-01-02T10:00:00Z", "Run B"),
    ])
    since = datetime(2025, 6, 1, tzinfo=timezone.utc)
    n = sync.sync_activities(client, storage, since=since)
    assert n == 2
    client.get_activities.assert_called_once_with(after=since)
    assert {a["id"] for a in storage.all_activities()} == {1, 2}


def test_sync_activities_is_idempotent(storage, mocker):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "Run A")
    client = mocker.MagicMock()
    client.get_activities.return_value = iter([
        make_activity(1, "2026-01-01T10:00:00Z", "Run A"),
        make_activity(2, "2026-01-02T10:00:00Z", "Run B"),
    ])
    since = datetime(2025, 6, 1, tzinfo=timezone.utc)
    sync.sync_activities(client, storage, since=since)
    assert len(storage.all_activities()) == 2


def test_sync_kudoers_fetches_only_pending(storage, mocker):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")
    storage.upsert_activity(2, "2026-01-02T10:00:00Z", "B")
    storage.mark_kudos_synced(1)

    client = mocker.MagicMock()
    client.get_activity_kudos.return_value = iter([
        make_athlete(None, "Jean", "D."),
        make_athlete(None, "Marie", "M."),
    ])

    n = sync.sync_kudoers(client, storage)
    assert n == 1  # one activity synced
    client.get_activity_kudos.assert_called_once_with(2)
    rows = storage.kudoers_for_activity(2)
    assert {r["firstname"] for r in rows} == {"Jean", "Marie"}
    pending_after = storage.activities_needing_kudos_sync()
    assert pending_after == []


def test_sync_kudoers_marks_activity_synced_even_when_empty(storage, mocker):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")
    client = mocker.MagicMock()
    client.get_activity_kudos.return_value = iter([])

    sync.sync_kudoers(client, storage)
    assert storage.activities_needing_kudos_sync() == []


def test_sync_kudoers_handles_none_firstname_lastname(storage, mocker):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")
    client = mocker.MagicMock()
    # Athlete with no name fields — stored as empty strings
    client.get_activity_kudos.return_value = iter([
        make_athlete(None, None, None),
    ])

    sync.sync_kudoers(client, storage)
    rows = storage.kudoers_for_activity(1)
    assert len(rows) == 1
    assert rows[0]["firstname"] == ""
    assert rows[0]["lastname"] == ""


def test_sync_kudoers_retries_on_rate_limit(storage, mocker):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")

    import stravalib.exc as exc
    client = mocker.MagicMock()
    rate_err = exc.RateLimitExceeded("limit hit")
    client.get_activity_kudos.side_effect = [
        rate_err,
        iter([make_athlete(None, "Jean", "D.")]),
    ]
    mock_sleep = mocker.patch("kudostracker.sync.time.sleep")

    sync.sync_kudoers(client, storage)
    assert client.get_activity_kudos.call_count == 2
    rows = storage.kudoers_for_activity(1)
    assert len(rows) == 1
    assert rows[0]["firstname"] == "Jean"
    mock_sleep.assert_called_once_with(2.0)


def test_sync_kudoers_skips_activity_after_max_retries(storage, mocker):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")
    import stravalib.exc as exc
    client = mocker.MagicMock()
    client.get_activity_kudos.side_effect = exc.RateLimitExceeded("hit")
    mocker.patch("kudostracker.sync.time.sleep")

    n = sync.sync_kudoers(client, storage)
    assert n == 0
    # Activity remains unsynced
    assert len(storage.activities_needing_kudos_sync()) == 1


def test_sync_activities_skips_none_start_date(storage, mocker, capsys):
    client = mocker.MagicMock()
    bad = SimpleNamespace(id=42, start_date=None, name="weird")
    good = make_activity(43, "2026-01-02T10:00:00Z", "ok")
    client.get_activities.return_value = iter([bad, good])
    since = datetime(2025, 6, 1, tzinfo=timezone.utc)
    n = sync.sync_activities(client, storage, since=since)
    assert n == 1
    assert {a["id"] for a in storage.all_activities()} == {43}
    captured = capsys.readouterr()
    assert "42" in captured.out


def test_sync_kudoers_stores_kudoer_with_none_id(storage, mocker):
    """Production case: Strava returns id=None for all kudoers — they must still be stored."""
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")
    client = mocker.MagicMock()
    client.get_activity_kudos.return_value = iter([
        make_athlete(None, "Joshua", "D."),
        make_athlete(None, "Nicolas", "R."),
    ])
    sync.sync_kudoers(client, storage)
    rows = storage.kudoers_for_activity(1)
    assert {r["firstname"] for r in rows} == {"Joshua", "Nicolas"}


def test_sync_kudoers_treats_fault_429_as_rate_limit(storage, mocker):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")

    import stravalib.exc as exc
    from types import SimpleNamespace
    client = mocker.MagicMock()
    fault_429 = exc.Fault("429 Too Many", response=SimpleNamespace(status_code=429))
    client.get_activity_kudos.side_effect = [
        fault_429,
        iter([make_athlete(None, "Jean", "D.")]),
    ]
    mocker.patch("kudostracker.sync.time.sleep")
    sync.sync_kudoers(client, storage)
    assert client.get_activity_kudos.call_count == 2
    rows = storage.kudoers_for_activity(1)
    assert len(rows) == 1
    assert rows[0]["firstname"] == "Jean"


def test_sync_kudoers_propagates_non_retryable_fault(storage, mocker):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")
    import stravalib.exc as exc
    from types import SimpleNamespace
    client = mocker.MagicMock()
    auth_fault = exc.Fault("401 Unauthorized", response=SimpleNamespace(status_code=401))
    client.get_activity_kudos.side_effect = auth_fault
    mocker.patch("kudostracker.sync.time.sleep")
    with pytest.raises(exc.Fault):
        sync.sync_kudoers(client, storage)


def test_sync_kudoers_treats_fault_500_as_retryable(storage, mocker):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")
    import stravalib.exc as exc
    from types import SimpleNamespace
    client = mocker.MagicMock()
    server_err = exc.Fault("500", response=SimpleNamespace(status_code=500))
    client.get_activity_kudos.side_effect = [
        server_err,
        iter([make_athlete(None, "Jean", "Dupont")]),
    ]
    mocker.patch("kudostracker.sync.time.sleep")
    n = sync.sync_kudoers(client, storage)
    assert n == 1
    assert client.get_activity_kudos.call_count == 2


def test_sync_kudoers_skips_failing_activity_and_continues(storage, mocker, capsys):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")
    storage.upsert_activity(2, "2026-01-02T10:00:00Z", "B")
    import stravalib.exc as exc
    from types import SimpleNamespace
    client = mocker.MagicMock()
    server_err = exc.Fault("500", response=SimpleNamespace(status_code=500))
    client.get_activity_kudos.side_effect = [
        server_err, server_err, server_err,  # activity 1: 3 retries all fail
        iter([make_athlete(None, "Marie", "M.")]),  # activity 2: success
    ]
    mocker.patch("kudostracker.sync.time.sleep")
    n = sync.sync_kudoers(client, storage)
    assert n == 1  # only activity 2 was synced
    pending_after = storage.activities_needing_kudos_sync()
    assert {a["id"] for a in pending_after} == {1}
    err = capsys.readouterr().out
    assert "1" in err  # activity 1 mentioned in output

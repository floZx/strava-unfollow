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


def make_athlete(id_, firstname, lastname):
    return SimpleNamespace(id=id_, firstname=firstname, lastname=lastname)


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
        make_athlete(100, "Jean", "Dupont"),
        make_athlete(101, "Marie", "Martin"),
    ])

    n = sync.sync_kudoers(client, storage)
    assert n == 1  # one activity synced
    client.get_activity_kudos.assert_called_once_with(2)
    assert storage.kudos_count_per_athlete() == {100: 1, 101: 1}
    pending_after = storage.activities_needing_kudos_sync()
    assert pending_after == []


def test_sync_kudoers_marks_activity_synced_even_when_empty(storage, mocker):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")
    client = mocker.MagicMock()
    client.get_activity_kudos.return_value = iter([])

    sync.sync_kudoers(client, storage)
    assert storage.activities_needing_kudos_sync() == []


def test_sync_kudoers_handles_private_athlete(storage, mocker):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")
    client = mocker.MagicMock()
    # Private athlete has firstname/lastname = None
    client.get_activity_kudos.return_value = iter([
        make_athlete(100, None, None),
    ])

    sync.sync_kudoers(client, storage)
    rows = storage.kudoers_for_activity(1)
    assert rows[0]["firstname"] is None
    assert rows[0]["lastname"] is None


def test_sync_kudoers_retries_on_rate_limit(storage, mocker):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")

    import stravalib.exc as exc
    client = mocker.MagicMock()
    rate_err = exc.RateLimitExceeded("limit hit")
    client.get_activity_kudos.side_effect = [
        rate_err,
        iter([make_athlete(100, "Jean", "Dupont")]),
    ]
    mocker.patch("kudostracker.sync.time.sleep")

    sync.sync_kudoers(client, storage)
    assert client.get_activity_kudos.call_count == 2
    assert storage.kudos_count_per_athlete() == {100: 1}


def test_sync_kudoers_gives_up_after_max_retries(storage, mocker):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")
    import stravalib.exc as exc
    client = mocker.MagicMock()
    client.get_activity_kudos.side_effect = exc.RateLimitExceeded("hit")
    mocker.patch("kudostracker.sync.time.sleep")

    with pytest.raises(sync.SyncAborted):
        sync.sync_kudoers(client, storage)
    # Activity remains unsynced
    assert len(storage.activities_needing_kudos_sync()) == 1

def test_init_schema_is_idempotent(storage):
    storage.init_schema()  # should not raise


def test_upsert_activity_inserts_then_idempotent(storage):
    storage.upsert_activity(
        activity_id=1, start_date="2026-01-01T10:00:00Z", name="Morning run"
    )
    storage.upsert_activity(
        activity_id=1, start_date="2026-01-01T10:00:00Z", name="Morning run"
    )
    rows = storage.all_activities()
    assert len(rows) == 1
    assert rows[0]["id"] == 1
    assert rows[0]["kudos_synced"] == 0


def test_upsert_activity_updates_name_on_conflict(storage):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "Original name")
    storage.mark_kudos_synced(1)
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "Renamed")
    rows = storage.all_activities()
    assert len(rows) == 1
    assert rows[0]["name"] == "Renamed"
    # kudos_synced must NOT be reset
    assert rows[0]["kudos_synced"] == 1


def test_activities_needing_kudos_sync(storage):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")
    storage.upsert_activity(2, "2026-01-02T10:00:00Z", "B")
    storage.mark_kudos_synced(1)
    pending = storage.activities_needing_kudos_sync()
    assert [a["id"] for a in pending] == [2]


def test_insert_kudoer_then_mark_synced(storage):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")
    storage.insert_kudoer(activity_id=1, firstname="Jean", lastname="D.")
    storage.insert_kudoer(activity_id=1, firstname="Marie", lastname="M.")
    storage.mark_kudos_synced(1)

    rows = storage.kudoers_for_activity(1)
    assert {r["firstname"] for r in rows} == {"Jean", "Marie"}


def test_insert_kudoer_is_idempotent(storage):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")
    storage.insert_kudoer(1, "Jean", "D.")
    storage.insert_kudoer(1, "Jean", "D.")  # duplicate
    rows = storage.kudoers_for_activity(1)
    assert len(rows) == 1


def test_kudoers_for_activity_returns_empty_for_unknown(storage):
    rows = storage.kudoers_for_activity(999)
    assert rows == []


def test_all_kudoers_returns_all_rows(storage):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")
    storage.upsert_activity(2, "2026-01-02T10:00:00Z", "B")
    storage.insert_kudoer(1, "Jean", "D.")
    storage.insert_kudoer(2, "Jean", "D.")
    storage.insert_kudoer(2, "Marie", "M.")
    rows = storage.all_kudoers()
    assert len(rows) == 3
    activity_ids = {r["activity_id"] for r in rows}
    assert activity_ids == {1, 2}


def test_activity_count(storage):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")
    storage.upsert_activity(2, "2026-01-02T10:00:00Z", "B")
    assert storage.activity_count() == 2

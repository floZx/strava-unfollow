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


def test_activities_needing_kudos_sync(storage):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")
    storage.upsert_activity(2, "2026-01-02T10:00:00Z", "B")
    storage.mark_kudos_synced(1)
    pending = storage.activities_needing_kudos_sync()
    assert [a["id"] for a in pending] == [2]


def test_insert_kudoer_then_mark_synced(storage):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")
    storage.insert_kudoer(activity_id=1, athlete_id=100, firstname="Jean", lastname="Dupont")
    storage.insert_kudoer(activity_id=1, athlete_id=101, firstname="Marie", lastname="Martin")
    storage.mark_kudos_synced(1)

    rows = storage.kudoers_for_activity(1)
    assert {r["athlete_id"] for r in rows} == {100, 101}


def test_insert_kudoer_is_idempotent(storage):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")
    storage.insert_kudoer(1, 100, "Jean", "Dupont")
    storage.insert_kudoer(1, 100, "Jean", "Dupont")  # duplicate
    rows = storage.kudoers_for_activity(1)
    assert len(rows) == 1


def test_kudos_count_per_athlete(storage):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")
    storage.upsert_activity(2, "2026-01-02T10:00:00Z", "B")
    storage.upsert_activity(3, "2026-01-03T10:00:00Z", "C")
    storage.insert_kudoer(1, 100, "Jean", "Dupont")
    storage.insert_kudoer(2, 100, "Jean", "Dupont")
    storage.insert_kudoer(2, 101, "Marie", "Martin")
    counts = storage.kudos_count_per_athlete()
    assert counts == {100: 2, 101: 1}


def test_activity_count(storage):
    storage.upsert_activity(1, "2026-01-01T10:00:00Z", "A")
    storage.upsert_activity(2, "2026-01-02T10:00:00Z", "B")
    assert storage.activity_count() == 2

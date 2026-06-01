from datetime import date

from kudostracker import report


FOLLOWERS = [
    {"id": 100, "name": "Jean Dupont", "url": "https://strava.com/athletes/100"},
    {"id": 101, "name": "Marie Martin", "url": "https://strava.com/athletes/101"},
    {"id": 102, "name": "Paul Durand", "url": "https://strava.com/athletes/102"},
]

FOLLOWING = [
    {"id": 100, "name": "Jean Dupont", "url": "https://strava.com/athletes/100"},
    {"id": 200, "name": "Sophie Bernard", "url": "https://strava.com/athletes/200"},
    {"id": 201, "name": "Lucas Petit", "url": "https://strava.com/athletes/201"},
]


def test_compute_low_kudos_rows_sorted_ascending():
    counts = {100: 5, 101: 0, 102: 2}
    rows = report.compute_low_kudos_rows(FOLLOWERS, counts, activity_count=10)
    # 0 < 2 < 5 → Marie, Paul, Jean
    assert [r["name"] for r in rows] == ["Marie Martin", "Paul Durand", "Jean Dupont"]
    assert rows[0]["count"] == 0
    assert rows[0]["ratio_pct"] == 0.0
    assert rows[2]["ratio_pct"] == 50.0


def test_compute_low_kudos_handles_missing_athlete():
    # follower with no kudoers row at all = 0 kudos
    counts = {}
    rows = report.compute_low_kudos_rows(FOLLOWERS, counts, activity_count=10)
    assert all(r["count"] == 0 for r in rows)


def test_compute_low_kudos_zero_activities():
    counts = {}
    rows = report.compute_low_kudos_rows(FOLLOWERS, counts, activity_count=0)
    # All ratios = 0% (no division by zero)
    assert all(r["ratio_pct"] == 0.0 for r in rows)


def test_compute_non_mutuals():
    out = report.compute_non_mutuals(following=FOLLOWING, followers=FOLLOWERS)
    # 200 and 201 in following but not in followers
    assert [a["id"] for a in out] == [201, 200]  # alpha by name: Lucas, Sophie
    assert out[0]["name"] == "Lucas Petit"


def test_compute_non_mutuals_empty():
    out = report.compute_non_mutuals(following=[], followers=FOLLOWERS)
    assert out == []


def test_render_report_contains_sections():
    rendered = report.render_report(
        generated_on=date(2026, 6, 1),
        window_start=date(2025, 6, 1),
        window_end=date(2026, 6, 1),
        activity_count=10,
        low_kudos_rows=report.compute_low_kudos_rows(FOLLOWERS, {100: 5}, 10),
        non_mutuals=report.compute_non_mutuals(FOLLOWING, FOLLOWERS),
    )
    assert "## Abonnés qui ne te kudosent" in rendered
    assert "## Comptes que tu suis qui ne te suivent pas en retour" in rendered
    assert "Marie Martin" in rendered
    assert "Lucas Petit" in rendered
    assert "2026-06-01" in rendered


def test_render_report_empty_followers_shows_hint():
    rendered = report.render_report(
        generated_on=date(2026, 6, 1),
        window_start=date(2025, 6, 1),
        window_end=date(2026, 6, 1),
        activity_count=0,
        low_kudos_rows=[],
        non_mutuals=[],
    )
    assert "paste followers" in rendered


def test_write_report_creates_parents_and_encodes_utf8(tmp_path):
    p = tmp_path / "nested" / "dir" / "report.md"
    report.write_report("Résultat : é à ü", p)
    assert p.read_bytes() == "Résultat : é à ü".encode("utf-8")


def test_render_report_escapes_pipes_in_names():
    rendered = report.render_report(
        generated_on=date(2026, 6, 1),
        window_start=date(2025, 6, 1),
        window_end=date(2026, 6, 1),
        activity_count=10,
        low_kudos_rows=[
            {"name": "Alice | Triathlete", "url": "https://strava.com/athletes/1",
             "count": 0, "ratio_pct": 0.0},
        ],
        non_mutuals=[
            {"id": 2, "name": "Bob | Runner", "url": "https://strava.com/athletes/2"},
        ],
    )
    # The literal `\|` (backslash-pipe) must appear in the rendered output
    assert r"Alice \| Triathlete" in rendered
    assert r"Bob \| Runner" in rendered

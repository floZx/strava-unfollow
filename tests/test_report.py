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


def _kudoer_rows(*entries):
    """Build a list of dicts simulating sqlite3.Row for kudoer data.

    Each entry is (activity_id, firstname, lastname).
    """
    return [{"activity_id": a, "firstname": f, "lastname": l} for a, f, l in entries]


def test_compute_low_kudos_rows_sorted_ascending():
    # Jean kudoed 5 activities (acts 1-5), Paul kudoed 2 (acts 1-2), Marie 0
    # All 3 followers are also in following (all mutuals), so sort behaviour is preserved.
    following_all = FOLLOWERS[:]  # same list → all are mutuals
    kudoer_rows = _kudoer_rows(
        *[(i, "Jean", "D.") for i in range(1, 6)],
        *[(i, "Paul", "D.") for i in range(1, 3)],
    )
    rows = report.compute_low_kudos_rows(FOLLOWERS, following_all, kudoer_rows, activity_count=10)
    # 0 < 2 < 5 → Marie, Paul, Jean
    assert [r["name"] for r in rows] == ["Marie Martin", "Paul Durand", "Jean Dupont"]
    assert rows[0]["count"] == 0
    assert rows[0]["ratio_pct"] == 0.0
    assert rows[2]["ratio_pct"] == 50.0


def test_compute_low_kudos_handles_missing_athlete():
    # follower with no kudoers row at all = 0 kudos
    rows = report.compute_low_kudos_rows(FOLLOWERS, FOLLOWERS, [], activity_count=10)
    assert all(r["count"] == 0 for r in rows)


def test_compute_low_kudos_zero_activities():
    rows = report.compute_low_kudos_rows(FOLLOWERS, FOLLOWERS, [], activity_count=0)
    # All ratios = 0% (no division by zero)
    assert all(r["ratio_pct"] == 0.0 for r in rows)


def test_compute_low_kudos_excludes_non_mutuals():
    followers = [
        {"id": 1, "name": "Mutual", "url": "https://strava.com/athletes/1"},
        {"id": 2, "name": "Not Followed Back", "url": "https://strava.com/athletes/2"},
    ]
    following = [
        {"id": 1, "name": "Mutual", "url": "https://strava.com/athletes/1"},
    ]
    kudoer_rows = []
    rows = report.compute_low_kudos_rows(followers, following, kudoer_rows, activity_count=10)
    assert len(rows) == 1
    assert rows[0]["name"] == "Mutual"


def test_compute_low_kudos_ambiguous_flag():
    # Two followers whose names normalise to the same (first, initial):
    # "Jean Dupont" → ("jean", "d") and "Jean Dubois" → ("jean", "d")
    followers_with_dup = [
        {"id": 1, "name": "Jean Dupont", "url": "https://strava.com/athletes/1"},
        {"id": 2, "name": "Jean Dubois", "url": "https://strava.com/athletes/2"},
        {"id": 3, "name": "Marie Martin", "url": "https://strava.com/athletes/3"},
    ]
    kudoer_rows = _kudoer_rows((1, "Jean", "D."))
    rows = report.compute_low_kudos_rows(followers_with_dup, followers_with_dup, kudoer_rows, activity_count=5)
    by_name = {r["name"]: r for r in rows}
    assert by_name["Jean Dupont"]["ambiguous"] is True
    assert by_name["Jean Dubois"]["ambiguous"] is True
    assert by_name["Marie Martin"]["ambiguous"] is False


def test_compute_low_kudos_accent_insensitive_matching():
    # Follower "François Dupont" should match kudoer ("Francois", "D.")
    followers_fr = [
        {"id": 1, "name": "François Dupont", "url": "https://strava.com/athletes/1"},
    ]
    kudoer_rows = _kudoer_rows((1, "Francois", "D."), (2, "Francois", "D."))
    rows = report.compute_low_kudos_rows(followers_fr, followers_fr, kudoer_rows, activity_count=5)
    assert rows[0]["count"] == 2


def test_compute_non_mutuals():
    out = report.compute_non_mutuals(following=FOLLOWING, followers=FOLLOWERS)
    # 200 and 201 in following but not in followers
    assert [a["id"] for a in out] == [201, 200]  # alpha by name: Lucas, Sophie
    assert out[0]["name"] == "Lucas Petit"


def test_compute_non_mutuals_empty():
    out = report.compute_non_mutuals(following=[], followers=FOLLOWERS)
    assert out == []


def test_render_report_contains_sections():
    # Jean (id=100) kudoed 5 distinct activities
    # FOLLOWERS has ids 100, 101, 102; use same list as following so all are mutuals
    kudoer_rows = _kudoer_rows(*[(i, "Jean", "D.") for i in range(1, 6)])
    rendered = report.render_report(
        generated_on=date(2026, 6, 1),
        window_start=date(2025, 6, 1),
        window_end=date(2026, 6, 1),
        activity_count=10,
        low_kudos_rows=report.compute_low_kudos_rows(FOLLOWERS, FOLLOWERS, kudoer_rows, 10),
        non_mutuals=report.compute_non_mutuals(FOLLOWING, FOLLOWERS),
    )
    assert "## Mutuels qui ne te kudosent" in rendered
    assert "## Comptes que tu suis qui ne te suivent pas en retour" in rendered
    assert "Marie Martin" in rendered
    assert "Lucas Petit" in rendered
    assert "2026-06-01" in rendered
    assert "Ambigu" in rendered


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


def test_render_report_html_contains_table_and_sections():
    rendered = report.render_report_html(
        generated_on=date(2026, 6, 1),
        window_start=date(2025, 6, 1),
        window_end=date(2026, 6, 1),
        activity_count=10,
        low_kudos_rows=[
            {"name": "Jean", "url": "https://example.com/1", "count": 0, "ratio_pct": 0.0, "ambiguous": False},
        ],
        non_mutuals=[
            {"id": 2, "name": "Marie", "url": "https://example.com/2"},
        ],
    )
    assert "<!DOCTYPE html>" in rendered
    assert "<table>" in rendered
    assert "Jean" in rendered
    assert "Marie" in rendered
    assert "Mutuels qui ne te kudosent" in rendered
    assert "Comptes que tu suis" in rendered


def test_render_report_html_escapes_special_chars():
    rendered = report.render_report_html(
        generated_on=date(2026, 6, 1),
        window_start=date(2025, 6, 1),
        window_end=date(2026, 6, 1),
        activity_count=1,
        low_kudos_rows=[
            {"name": "<script>alert(1)</script>", "url": "u", "count": 0, "ratio_pct": 0.0, "ambiguous": False},
        ],
        non_mutuals=[],
    )
    assert "<script>" not in rendered
    assert "&lt;script&gt;" in rendered


def test_render_report_html_empty_followers_shows_hint():
    rendered = report.render_report_html(
        generated_on=date(2026, 6, 1),
        window_start=date(2025, 6, 1),
        window_end=date(2026, 6, 1),
        activity_count=0,
        low_kudos_rows=[],
        non_mutuals=[],
    )
    assert "paste followers" in rendered


def test_render_report_escapes_pipes_in_names():
    rendered = report.render_report(
        generated_on=date(2026, 6, 1),
        window_start=date(2025, 6, 1),
        window_end=date(2026, 6, 1),
        activity_count=10,
        low_kudos_rows=[
            {"name": "Alice | Triathlete", "url": "https://strava.com/athletes/1",
             "count": 0, "ratio_pct": 0.0, "ambiguous": False},
        ],
        non_mutuals=[
            {"id": 2, "name": "Bob | Runner", "url": "https://strava.com/athletes/2"},
        ],
    )
    # The literal `\|` (backslash-pipe) must appear in the rendered output
    assert r"Alice \| Triathlete" in rendered
    assert r"Bob \| Runner" in rendered

from collections import Counter, defaultdict
from datetime import date
from pathlib import Path
from typing import Any

from jinja2 import Environment, PackageLoader, select_autoescape

from kudostracker.matching import normalize_follower, normalize_kudoer


def _env() -> Environment:
    return Environment(
        loader=PackageLoader("kudostracker", "templates"),
        autoescape=select_autoescape(default=False),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def compute_low_kudos_rows(
    followers: list[dict[str, Any]],
    kudoer_rows: list[Any],  # sqlite3.Row or dict with activity_id, firstname, lastname
    activity_count: int,
) -> list[dict[str, Any]]:
    # Map (first, initial) -> set of activity_ids where someone with that name kudoed
    activities_by_name: dict[tuple[str, str], set[int]] = defaultdict(set)
    for kr in kudoer_rows:
        key = normalize_kudoer(kr["firstname"], kr["lastname"])
        activities_by_name[key].add(kr["activity_id"])
    # Count how many followers share each normalized name (ambiguity detection)
    follower_keys = {f["id"]: normalize_follower(f["name"]) for f in followers}
    key_counter = Counter(follower_keys.values())

    rows = []
    for f in followers:
        key = follower_keys[f["id"]]
        kudosed_count = len(activities_by_name.get(key, set()))
        ratio = (kudosed_count / activity_count * 100) if activity_count > 0 else 0.0
        rows.append(
            {
                "name": f["name"],
                "url": f["url"],
                "count": kudosed_count,
                "ratio_pct": round(ratio, 1),
                "ambiguous": key_counter[key] > 1,
            }
        )
    rows.sort(key=lambda r: (r["count"], r["name"].lower()))
    return rows


def compute_non_mutuals(
    following: list[dict[str, Any]],
    followers: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    follower_ids = {f["id"] for f in followers}
    diff = [a for a in following if a["id"] not in follower_ids]
    diff.sort(key=lambda a: a["name"].lower())
    return diff


def render_report(
    *,
    generated_on: date,
    window_start: date,
    window_end: date,
    activity_count: int,
    low_kudos_rows: list[dict[str, Any]],
    non_mutuals: list[dict[str, Any]],
) -> str:
    template = _env().get_template("report.md.j2")
    return template.render(
        generated_on=generated_on.isoformat(),
        window_start=window_start.isoformat(),
        window_end=window_end.isoformat(),
        activity_count=activity_count,
        low_kudos_rows=low_kudos_rows,
        non_mutuals=non_mutuals,
    )


def write_report(content: str, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")

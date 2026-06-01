import argparse
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import stravalib

from kudostracker import auth, follower_io, paths, report, sync
from kudostracker.storage import Storage


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="kudostracker")
    sub = parser.add_subparsers(dest="cmd")

    p_auth = sub.add_parser("auth", help="Run Strava OAuth flow once")
    p_auth.add_argument("--client-id", type=int, default=None, help="Strava app client id (or env STRAVA_CLIENT_ID)")
    p_auth.add_argument("--client-secret", default=None, help="Strava app client secret (or env STRAVA_CLIENT_SECRET)")

    p_paste = sub.add_parser("paste", help="Load followers/following from clipboard")
    p_paste.add_argument("kind", choices=["followers", "following"])

    p_sync = sub.add_parser("sync", help="Fetch activities + kudoers from Strava")
    p_sync.add_argument(
        "--since",
        default=None,
        help="ISO date (YYYY-MM-DD). Default: 12 months ago.",
    )

    p_report = sub.add_parser("report", help="Generate markdown report")
    p_report.add_argument("--out", default=None, help="Output path (default data/report.md)")
    p_report.add_argument(
        "--since",
        default=None,
        help="ISO date for the window header. Default: 12 months ago.",
    )

    return parser


def _cmd_auth(args) -> int:
    client_id = args.client_id or os.environ.get("STRAVA_CLIENT_ID")
    client_secret = args.client_secret or os.environ.get("STRAVA_CLIENT_SECRET")
    if not client_id or not client_secret:
        print(
            "Missing --client-id/--client-secret (or STRAVA_CLIENT_ID/STRAVA_CLIENT_SECRET env vars).\n"
            "Create an app at https://www.strava.com/settings/api",
            file=sys.stderr,
        )
        return 2
    paths.ensure_data_dir()
    auth.run_oauth_flow(int(client_id), client_secret, paths.tokens_file())
    print(f"Tokens stored in {paths.tokens_file()}")
    return 0


def _cmd_paste(args) -> int:
    target = paths.followers_file() if args.kind == "followers" else paths.following_file()
    paths.ensure_data_dir()

    try:
        raw = follower_io.read_from_clipboard()
    except follower_io.ClipboardUnavailable as e:
        print(f"! {e}\n  Fallback: opening {target} in $EDITOR.", file=sys.stderr)
        raw = follower_io.read_via_editor(target)

    try:
        athletes = follower_io.parse_payload(raw)
    except follower_io.InvalidPayload as e:
        print(f"Erreur de validation JSON : {e}", file=sys.stderr)
        return 1

    follower_io.save_athletes(athletes, target)
    print(f"{len(athletes)} athletes loaded into {target}")
    return 0


def _resolve_since(arg: str | None) -> datetime:
    if arg:
        return datetime.fromisoformat(arg).replace(tzinfo=timezone.utc)
    return datetime.now(tz=timezone.utc) - timedelta(days=365)


def _authenticated_client() -> stravalib.Client:
    tokens_path = paths.tokens_file()
    if not tokens_path.exists():
        raise FileNotFoundError(
            f"No tokens at {tokens_path}. Run `kudostracker auth` first."
        )
    tokens = auth.load_tokens(tokens_path)
    if not auth.tokens_are_fresh(tokens):
        tokens = auth.refresh_tokens(tokens_path)
    return stravalib.Client(access_token=tokens["access_token"])


def _cmd_sync(args) -> int:
    paths.ensure_data_dir()
    try:
        client = _authenticated_client()
    except FileNotFoundError as e:
        print(f"! {e}", file=sys.stderr)
        return 2

    since = _resolve_since(args.since)
    storage = Storage(paths.db_file())
    storage.init_schema()
    try:
        n_act = sync.sync_activities(client, storage, since=since)
        print(f"{n_act} activities seen (since {since.date()})")
        n_kud = sync.sync_kudoers(client, storage)
        print(f"Kudoers fetched for {n_kud} new activities")
    except sync.SyncAborted as e:
        print(f"! {e}\n  Retry later, progress is saved.", file=sys.stderr)
        return 3
    finally:
        storage.close()
    return 0


def _cmd_report(args) -> int:
    paths.ensure_data_dir()
    followers_path = paths.followers_file()
    following_path = paths.following_file()
    if not followers_path.exists():
        print(
            f"! {followers_path} not found. Run `kudostracker paste followers` first.",
            file=sys.stderr,
        )
        return 2
    if not following_path.exists():
        print(
            f"! {following_path} not found. Run `kudostracker paste following` first.",
            file=sys.stderr,
        )
        return 2

    followers = follower_io.load_athletes(followers_path)
    following = follower_io.load_athletes(following_path)

    storage = Storage(paths.db_file())
    storage.init_schema()
    try:
        counts = storage.kudos_count_per_athlete()
        activity_count = storage.activity_count()
    finally:
        storage.close()

    since = _resolve_since(args.since)
    rows = report.compute_low_kudos_rows(followers, counts, activity_count)
    non_mutuals = report.compute_non_mutuals(following, followers)
    content = report.render_report(
        generated_on=date.today(),
        window_start=since.date(),
        window_end=date.today(),
        activity_count=activity_count,
        low_kudos_rows=rows,
        non_mutuals=non_mutuals,
    )
    out_path = Path(args.out) if args.out else paths.report_file()
    report.write_report(content, out_path)
    print(f"Report written: {out_path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    if args.cmd is None:
        parser.print_help()
        return 1
    if args.cmd == "auth":
        return _cmd_auth(args)
    if args.cmd == "paste":
        return _cmd_paste(args)
    if args.cmd == "sync":
        return _cmd_sync(args)
    if args.cmd == "report":
        return _cmd_report(args)
    parser.print_help()
    return 1


if __name__ == "__main__":
    sys.exit(main())

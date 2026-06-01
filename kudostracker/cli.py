import argparse
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import stravalib
import stravalib.exc

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
        try:
            raw = follower_io.read_via_editor(target)
        except follower_io.EditorAborted as ea:
            print(f"! {ea}", file=sys.stderr)
            return 1

    try:
        athletes = follower_io.parse_payload(raw)
    except follower_io.InvalidPayload as e:
        print(f"Erreur de validation JSON : {e}", file=sys.stderr)
        return 1

    added, total = follower_io.merge_athletes(athletes, target)
    print(f"✓ {added} ajoutés ({total} au total dans {target})")
    return 0


def _resolve_since(arg: str | None) -> datetime:
    if arg:
        parsed = datetime.fromisoformat(arg)
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
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

    try:
        since = _resolve_since(args.since)
    except ValueError as e:
        print(f"! --since invalide ({args.since}) : {e}", file=sys.stderr)
        return 1
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
    except stravalib.exc.AccessUnauthorized:
        print(
            "! Token Strava révoqué ou expiré. Relance `kudostracker auth`.",
            file=sys.stderr,
        )
        return 2
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
        kudoer_rows = storage.all_kudoers()
        activity_count = storage.activity_count()
    finally:
        storage.close()

    try:
        since = _resolve_since(args.since)
    except ValueError as e:
        print(f"! --since invalide ({args.since}) : {e}", file=sys.stderr)
        return 1
    rows = report.compute_low_kudos_rows(followers, following, kudoer_rows, activity_count)
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

    html_content = report.render_report_html(
        generated_on=date.today(),
        window_start=since.date(),
        window_end=date.today(),
        activity_count=activity_count,
        low_kudos_rows=rows,
        non_mutuals=non_mutuals,
    )
    html_path = paths.report_html_file() if not args.out else Path(args.out).with_suffix(".html")
    report.write_report(html_content, html_path)
    print(f"✓ Rapport HTML écrit : {html_path}")
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

import time
from datetime import datetime
from typing import Any

import stravalib
import stravalib.exc

from kudostracker.storage import Storage


MAX_RETRIES = 3
BASE_BACKOFF = 2.0


class SyncAborted(RuntimeError):
    pass


def sync_activities(client: stravalib.Client, storage: Storage, since: datetime) -> int:
    n = 0
    for a in client.get_activities(after=since):
        if a.start_date is None:
            print(f"! Activité {a.id} ignorée (start_date manquant)")
            continue
        storage.upsert_activity(
            activity_id=a.id,
            start_date=a.start_date.isoformat(),
            name=getattr(a, "name", None),
        )
        n += 1
    return n


def _is_rate_limit(exc: Exception) -> bool:
    if isinstance(exc, stravalib.exc.RateLimitExceeded):
        return True
    if isinstance(exc, stravalib.exc.Fault):
        response = getattr(exc, "response", None)
        return response is not None and response.status_code == 429
    return False


def _fetch_kudoers_with_retry(client: stravalib.Client, activity_id: int) -> list[Any]:
    for attempt in range(MAX_RETRIES):
        try:
            return list(client.get_activity_kudos(activity_id))
        except (stravalib.exc.Fault, stravalib.exc.RateLimitExceeded) as e:
            if not _is_rate_limit(e):
                raise
            if attempt == MAX_RETRIES - 1:
                raise SyncAborted(
                    f"Rate limit hit on activity {activity_id} after {MAX_RETRIES} retries"
                ) from e
            time.sleep(BASE_BACKOFF * (2**attempt))
    raise SyncAborted("unreachable")


def sync_kudoers(client: stravalib.Client, storage: Storage) -> int:
    pending = storage.activities_needing_kudos_sync()
    synced = 0
    for activity in pending:
        kudoers = _fetch_kudoers_with_retry(client, activity["id"])
        for k in kudoers:
            storage.insert_kudoer(
                activity_id=activity["id"],
                firstname=getattr(k, "firstname", None) or "",
                lastname=getattr(k, "lastname", None) or "",
            )
        storage.mark_kudos_synced(activity["id"])
        synced += 1
    return synced

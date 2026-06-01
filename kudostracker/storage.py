import sqlite3
from pathlib import Path


SCHEMA = """
CREATE TABLE IF NOT EXISTS activities (
  id           INTEGER PRIMARY KEY,
  start_date   TEXT NOT NULL,
  name         TEXT,
  kudos_synced INTEGER NOT NULL DEFAULT 0
);

CREATE TABLE IF NOT EXISTS kudoers (
  activity_id  INTEGER NOT NULL,
  firstname    TEXT NOT NULL,
  lastname     TEXT NOT NULL,
  PRIMARY KEY (activity_id, firstname, lastname),
  FOREIGN KEY (activity_id) REFERENCES activities(id)
);
"""


class Storage:
    def __init__(self, db_path: str | Path):
        self.conn = sqlite3.connect(str(db_path))
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        self.conn.close()

    def init_schema(self) -> None:
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def upsert_activity(self, activity_id: int, start_date: str, name: str | None) -> None:
        self.conn.execute(
            """
            INSERT INTO activities (id, start_date, name)
            VALUES (?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
              start_date = excluded.start_date,
              name       = excluded.name
            """,
            (activity_id, start_date, name),
        )
        self.conn.commit()

    def mark_kudos_synced(self, activity_id: int) -> None:
        self.conn.execute(
            "UPDATE activities SET kudos_synced = 1 WHERE id = ?",
            (activity_id,),
        )
        self.conn.commit()

    def insert_kudoer(self, activity_id: int, firstname: str, lastname: str) -> None:
        self.conn.execute(
            """
            INSERT INTO kudoers (activity_id, firstname, lastname)
            VALUES (?, ?, ?)
            ON CONFLICT(activity_id, firstname, lastname) DO NOTHING
            """,
            (activity_id, firstname or "", lastname or ""),
        )
        self.conn.commit()

    def all_activities(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT * FROM activities ORDER BY start_date"))

    def activities_needing_kudos_sync(self) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM activities WHERE kudos_synced = 0 ORDER BY start_date"
            )
        )

    def kudoers_for_activity(self, activity_id: int) -> list[sqlite3.Row]:
        return list(
            self.conn.execute(
                "SELECT * FROM kudoers WHERE activity_id = ?", (activity_id,)
            )
        )

    def all_kudoers(self) -> list[sqlite3.Row]:
        return list(self.conn.execute("SELECT activity_id, firstname, lastname FROM kudoers"))

    def activity_count(self) -> int:
        row = self.conn.execute("SELECT COUNT(*) AS c FROM activities").fetchone()
        return row["c"]

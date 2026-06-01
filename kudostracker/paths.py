import os
from pathlib import Path


def data_dir() -> Path:
    override = os.environ.get("KUDOSTRACKER_DATA_DIR")
    if override:
        return Path(override)
    return Path.cwd() / "data"


def tokens_file() -> Path:
    return data_dir() / "tokens.json"


def db_file() -> Path:
    return data_dir() / "cache.db"


def followers_file() -> Path:
    return data_dir() / "followers.json"


def following_file() -> Path:
    return data_dir() / "following.json"


def report_file() -> Path:
    return data_dir() / "report.md"


def report_html_file() -> Path:
    return data_dir() / "report.html"


def ensure_data_dir() -> Path:
    d = data_dir()
    d.mkdir(parents=True, exist_ok=True)
    return d

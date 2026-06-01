import os
from pathlib import Path
import importlib


def test_default_data_dir_is_data_subfolder(monkeypatch, tmp_path):
    monkeypatch.delenv("KUDOSTRACKER_DATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)
    import kudostracker.paths as paths
    importlib.reload(paths)
    assert paths.data_dir() == tmp_path / "data"


def test_data_dir_override_via_env(monkeypatch, tmp_path):
    monkeypatch.setenv("KUDOSTRACKER_DATA_DIR", str(tmp_path / "elsewhere"))
    import kudostracker.paths as paths
    importlib.reload(paths)
    assert paths.data_dir() == tmp_path / "elsewhere"


def test_named_paths(monkeypatch, tmp_path):
    monkeypatch.setenv("KUDOSTRACKER_DATA_DIR", str(tmp_path))
    import kudostracker.paths as paths
    importlib.reload(paths)
    assert paths.tokens_file() == tmp_path / "tokens.json"
    assert paths.db_file() == tmp_path / "cache.db"
    assert paths.followers_file() == tmp_path / "followers.json"
    assert paths.following_file() == tmp_path / "following.json"
    assert paths.report_file() == tmp_path / "report.md"


def test_ensure_data_dir_creates_folder(monkeypatch, tmp_path):
    target = tmp_path / "new"
    monkeypatch.setenv("KUDOSTRACKER_DATA_DIR", str(target))
    import kudostracker.paths as paths
    importlib.reload(paths)
    paths.ensure_data_dir()
    assert target.is_dir()

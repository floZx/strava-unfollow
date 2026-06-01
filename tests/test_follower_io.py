import json
import pytest
from kudostracker import follower_io


VALID_PAYLOAD = [
    {"id": 12345, "name": "Jean Dupont", "url": "https://strava.com/athletes/12345"},
    {"id": 67890, "name": "Marie Martin", "url": "https://strava.com/athletes/67890"},
]


def test_parse_valid_payload():
    parsed = follower_io.parse_payload(json.dumps(VALID_PAYLOAD))
    assert parsed == VALID_PAYLOAD


def test_parse_rejects_non_json():
    with pytest.raises(follower_io.InvalidPayload) as exc:
        follower_io.parse_payload("not json at all")
    assert "JSON" in str(exc.value)


def test_parse_rejects_non_array():
    with pytest.raises(follower_io.InvalidPayload):
        follower_io.parse_payload('{"id": 1}')


def test_parse_rejects_missing_field():
    bad = json.dumps([{"id": 1, "name": "x"}])  # url missing
    with pytest.raises(follower_io.InvalidPayload) as exc:
        follower_io.parse_payload(bad)
    assert "url" in str(exc.value)


def test_parse_rejects_wrong_type():
    bad = json.dumps([{"id": "not_int", "name": "x", "url": "y"}])
    with pytest.raises(follower_io.InvalidPayload):
        follower_io.parse_payload(bad)


def test_parse_empty_array_is_valid():
    assert follower_io.parse_payload("[]") == []


def test_save_followers_writes_file(tmp_path):
    target = tmp_path / "followers.json"
    follower_io.save_athletes(VALID_PAYLOAD, target)
    assert json.loads(target.read_text()) == VALID_PAYLOAD


def test_load_athletes_reads_file(tmp_path):
    target = tmp_path / "followers.json"
    target.write_text(json.dumps(VALID_PAYLOAD))
    assert follower_io.load_athletes(target) == VALID_PAYLOAD


def test_load_athletes_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        follower_io.load_athletes(tmp_path / "absent.json")


def test_read_from_clipboard_uses_pyperclip(mocker):
    mock = mocker.patch("kudostracker.follower_io.pyperclip")
    mock.paste.return_value = json.dumps(VALID_PAYLOAD)
    assert follower_io.read_from_clipboard() == json.dumps(VALID_PAYLOAD)


def test_read_from_clipboard_raises_on_empty(mocker):
    mock = mocker.patch("kudostracker.follower_io.pyperclip")
    mock.paste.return_value = ""
    with pytest.raises(follower_io.ClipboardUnavailable) as exc:
        follower_io.read_from_clipboard()
    assert "vide" in str(exc.value).lower()


def test_read_from_clipboard_raises_on_pyperclip_error(mocker):
    import pyperclip
    mock = mocker.patch("kudostracker.follower_io.pyperclip")
    mock.PyperclipException = pyperclip.PyperclipException
    mock.paste.side_effect = pyperclip.PyperclipException("no xclip")
    with pytest.raises(follower_io.ClipboardUnavailable):
        follower_io.read_from_clipboard()


def test_read_via_editor(mocker, tmp_path):
    target = tmp_path / "scratch.json"

    def fake_run(cmd, check):
        # simulate the editor writing content
        target.write_text(json.dumps(VALID_PAYLOAD), encoding="utf-8")

    mocker.patch("kudostracker.follower_io.subprocess.run", side_effect=fake_run)
    mocker.patch("kudostracker.follower_io.os.environ.get", return_value="vim")
    assert follower_io.read_via_editor(target) == json.dumps(VALID_PAYLOAD)


def test_read_via_editor_handles_editor_with_args(mocker, tmp_path):
    target = tmp_path / "scratch.json"
    target.write_text("[]", encoding="utf-8")

    captured = {}
    def fake_run(cmd, check):
        captured["cmd"] = cmd

    mocker.patch("kudostracker.follower_io.subprocess.run", side_effect=fake_run)
    mocker.patch.dict("os.environ", {"EDITOR": "code --wait"})
    follower_io.read_via_editor(target)
    assert captured["cmd"][:2] == ["code", "--wait"]
    assert captured["cmd"][-1] == str(target)


def test_read_via_editor_raises_on_nonzero_exit(mocker, tmp_path):
    import subprocess
    target = tmp_path / "scratch.json"
    mocker.patch(
        "kudostracker.follower_io.subprocess.run",
        side_effect=subprocess.CalledProcessError(1, ["vim"]),
    )
    mocker.patch.dict("os.environ", {"EDITOR": "vim"})
    with pytest.raises(follower_io.EditorAborted):
        follower_io.read_via_editor(target)


def test_parse_rejects_bool_as_id():
    bad = json.dumps([{"id": True, "name": "x", "url": "y"}])
    with pytest.raises(follower_io.InvalidPayload):
        follower_io.parse_payload(bad)


def test_merge_athletes_creates_file_when_absent(tmp_path):
    target = tmp_path / "followers.json"
    new = [
        {"id": 1, "name": "A", "url": "https://strava.com/athletes/1"},
        {"id": 2, "name": "B", "url": "https://strava.com/athletes/2"},
    ]
    added, total = follower_io.merge_athletes(new, target)
    assert added == 2
    assert total == 2
    assert json.loads(target.read_text(encoding="utf-8")) == new


def test_merge_athletes_dedups_by_id(tmp_path):
    target = tmp_path / "followers.json"
    follower_io.save_athletes(
        [{"id": 1, "name": "A", "url": "u1"}, {"id": 2, "name": "B", "url": "u2"}],
        target,
    )
    new = [
        {"id": 2, "name": "B", "url": "u2"},  # dupe
        {"id": 3, "name": "C", "url": "u3"},  # new
    ]
    added, total = follower_io.merge_athletes(new, target)
    assert added == 1
    assert total == 3
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert {a["id"] for a in loaded} == {1, 2, 3}


def test_merge_athletes_updates_name_on_conflict(tmp_path):
    target = tmp_path / "followers.json"
    follower_io.save_athletes(
        [{"id": 1, "name": "Old", "url": "u1"}],
        target,
    )
    new = [{"id": 1, "name": "New", "url": "u1"}]
    added, total = follower_io.merge_athletes(new, target)
    assert added == 0
    assert total == 1
    loaded = json.loads(target.read_text(encoding="utf-8"))
    assert loaded[0]["name"] == "New"

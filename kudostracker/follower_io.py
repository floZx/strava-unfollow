import json
import os
import shlex
import subprocess
from pathlib import Path
from typing import Any

import pyperclip


class InvalidPayload(ValueError):
    pass


class ClipboardUnavailable(RuntimeError):
    pass


class EditorAborted(RuntimeError):
    pass


REQUIRED_FIELDS = {"id": int, "name": str, "url": str}


def parse_payload(raw: str) -> list[dict[str, Any]]:
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise InvalidPayload(f"Contenu du presse-papier n'est pas du JSON valide : {e}") from e
    if not isinstance(data, list):
        raise InvalidPayload("Attendu : tableau JSON, reçu : " + type(data).__name__)
    for i, item in enumerate(data):
        if not isinstance(item, dict):
            raise InvalidPayload(f"Élément #{i} n'est pas un objet")
        for field, ftype in REQUIRED_FIELDS.items():
            if field not in item:
                raise InvalidPayload(f"Élément #{i} : champ '{field}' manquant")
            if not isinstance(item[field], ftype) or (ftype is int and isinstance(item[field], bool)):
                raise InvalidPayload(
                    f"Élément #{i} : champ '{field}' attendu de type {ftype.__name__}, "
                    f"reçu {type(item[field]).__name__}"
                )
    return data


def save_athletes(athletes: list[dict[str, Any]], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(athletes, ensure_ascii=False, indent=2), encoding="utf-8")


def merge_athletes(new_list: list[dict[str, Any]], target: Path) -> tuple[int, int]:
    """Merge new_list into the JSON at target, dedup by id.

    Returns (added_count, total_count). If target doesn't exist, all of
    new_list is added.
    """
    existing: list[dict[str, Any]] = []
    if target.exists():
        existing = load_athletes(target)
    by_id = {a["id"]: a for a in existing}
    added = 0
    for a in new_list:
        if a["id"] not in by_id:
            added += 1
        by_id[a["id"]] = a  # later wins on dupes (updated name etc.)
    merged = list(by_id.values())
    save_athletes(merged, target)
    return added, len(merged)


def load_athletes(source: Path) -> list[dict[str, Any]]:
    if not source.exists():
        raise FileNotFoundError(source)
    return parse_payload(source.read_text(encoding="utf-8"))


def read_from_clipboard() -> str:
    try:
        content = pyperclip.paste()
    except pyperclip.PyperclipException as e:
        raise ClipboardUnavailable(f"Presse-papier indisponible : {e}") from e
    if not content or not content.strip():
        raise ClipboardUnavailable("Presse-papier vide. As-tu exécuté le snippet JS dans la console ?")
    return content


def read_via_editor(scratch: Path) -> str:
    scratch.parent.mkdir(parents=True, exist_ok=True)
    if not scratch.exists():
        scratch.write_text("[]", encoding="utf-8")
    editor = os.environ.get("EDITOR", "vim")
    try:
        subprocess.run(shlex.split(editor) + [str(scratch)], check=True)
    except subprocess.CalledProcessError as e:
        raise EditorAborted(f"Éditeur '{editor}' a quitté avec le code {e.returncode}") from e
    return scratch.read_text(encoding="utf-8")

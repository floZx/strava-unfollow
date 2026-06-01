import json
import os
import subprocess
from pathlib import Path
from typing import Any

import pyperclip


class InvalidPayload(ValueError):
    pass


class ClipboardUnavailable(RuntimeError):
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
            if not isinstance(item[field], ftype):
                raise InvalidPayload(
                    f"Élément #{i} : champ '{field}' attendu de type {ftype.__name__}, "
                    f"reçu {type(item[field]).__name__}"
                )
    return data


def save_athletes(athletes: list[dict[str, Any]], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(athletes, ensure_ascii=False, indent=2))


def load_athletes(source: Path) -> list[dict[str, Any]]:
    if not source.exists():
        raise FileNotFoundError(source)
    return parse_payload(source.read_text())


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
        scratch.write_text("[]")
    editor = os.environ.get("EDITOR", "vim")
    subprocess.run([editor, str(scratch)], check=True)
    return scratch.read_text()

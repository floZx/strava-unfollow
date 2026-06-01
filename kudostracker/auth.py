import json
import os
import sys
import time
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urlparse, parse_qs

import stravalib


AUTHORIZE_URL = "https://www.strava.com/oauth/authorize"
CALLBACK_HOST = "localhost"
CALLBACK_PORT = 8765
CALLBACK_PATH = "/callback"
EXPIRY_BUFFER_SECONDS = 60
_OAUTH_DENIED_SENTINEL = "__denied__"


def build_authorize_url(client_id: int, redirect_uri: str, scopes: list[str]) -> str:
    params = {
        "client_id": client_id,
        "response_type": "code",
        "redirect_uri": redirect_uri,
        "approval_prompt": "auto",
        "scope": ",".join(scopes),
    }
    return f"{AUTHORIZE_URL}?{urlencode(params)}"


def save_tokens(
    path: Path,
    access_token: str,
    refresh_token: str,
    expires_at: int,
    client_id: int,
    client_secret: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "access_token": access_token,
        "refresh_token": refresh_token,
        "expires_at": expires_at,
        "client_id": client_id,
        "client_secret": client_secret,
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    if sys.platform != "win32":
        os.chmod(path, 0o600)


def load_tokens(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def tokens_are_fresh(tokens: dict[str, Any]) -> bool:
    return tokens["expires_at"] > int(time.time()) + EXPIRY_BUFFER_SECONDS


def refresh_tokens(path: Path) -> dict[str, Any]:
    tokens = load_tokens(path)
    client = stravalib.Client()
    refreshed = client.refresh_access_token(
        client_id=tokens["client_id"],
        client_secret=tokens["client_secret"],
        refresh_token=tokens["refresh_token"],
    )
    save_tokens(
        path,
        access_token=refreshed["access_token"],
        refresh_token=refreshed["refresh_token"],
        expires_at=refreshed["expires_at"],
        client_id=tokens["client_id"],
        client_secret=tokens["client_secret"],
    )
    return load_tokens(path)


class _CallbackHandler(BaseHTTPRequestHandler):
    code: str | None = None

    def do_GET(self):
        parsed = urlparse(self.path)
        if parsed.path == CALLBACK_PATH:
            qs = parse_qs(parsed.query)
            if "error" in qs:
                _CallbackHandler.code = _OAUTH_DENIED_SENTINEL
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h1>Autorisation refus\xc3\xa9e</h1><p>Tu peux fermer cet onglet.</p>")
            else:
                _CallbackHandler.code = qs.get("code", [None])[0]
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.end_headers()
                self.wfile.write(b"<h1>OK</h1><p>Tu peux fermer cet onglet.</p>")
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        pass  # silence


def run_oauth_flow(client_id: int, client_secret: str, tokens_path: Path) -> dict[str, Any]:
    redirect_uri = f"http://{CALLBACK_HOST}:{CALLBACK_PORT}{CALLBACK_PATH}"
    url = build_authorize_url(client_id, redirect_uri, ["read", "activity:read"])
    print(f"Ouverture du navigateur sur :\n  {url}")
    webbrowser.open(url)

    _CallbackHandler.code = None
    server = HTTPServer((CALLBACK_HOST, CALLBACK_PORT), _CallbackHandler)
    try:
        while _CallbackHandler.code is None:
            server.handle_request()
        code = _CallbackHandler.code
    finally:
        server.server_close()

    if code == _OAUTH_DENIED_SENTINEL:
        raise RuntimeError("Autorisation OAuth refusée par l'utilisateur ou Strava.")

    client = stravalib.Client()
    token_response = client.exchange_code_for_token(
        client_id=client_id, client_secret=client_secret, code=code
    )
    save_tokens(
        tokens_path,
        access_token=token_response["access_token"],
        refresh_token=token_response["refresh_token"],
        expires_at=token_response["expires_at"],
        client_id=client_id,
        client_secret=client_secret,
    )
    return load_tokens(tokens_path)

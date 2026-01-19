#!/usr/bin/env python3
import json
from pathlib import Path
from urllib.parse import urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/chat.messages.readonly",
    "https://www.googleapis.com/auth/chat.spaces.readonly",
    "https://www.googleapis.com/auth/chat.memberships.readonly",
]


def default_client_secret_path() -> Path:
    primary = Path.home() / ".config/skills/client_secret.json"
    if primary.exists():
        return primary
    fallback = Path(__file__).resolve().parents[1] / "assets" / "client_secret.json"
    if fallback.exists():
        return fallback
    return primary


def default_token_path() -> Path:
    return Path.home() / ".config/google-chat/token.json"


def load_credentials(
    token_path: Path | None = None,
    client_secret_path: Path | None = None,
    scopes: list[str] | None = None,
    no_browser: bool = False,
) -> Credentials:
    scopes = scopes or SCOPES
    token_path = (token_path or default_token_path()).expanduser()
    client_secret_path = (client_secret_path or default_client_secret_path()).expanduser()

    creds = None
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(token_path, scopes=scopes)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())

    if not creds or not creds.valid or not set(scopes).issubset(set(creds.scopes or [])):
        if not client_secret_path.exists():
            raise FileNotFoundError(
                f"OAuth client secret not found: {client_secret_path}"
            )
        flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, scopes)
        if no_browser:
            flow.redirect_uri = "urn:ietf:wg:oauth:2.0:oob"
            auth_url, _ = flow.authorization_url(prompt="consent")
            print("Open this URL in your browser:\n" + auth_url)
            code = input("Enter authorization code: ").strip()
            flow.fetch_token(code=code)
            creds = flow.credentials
        else:
            creds = flow.run_local_server(port=0)

        token_path.parent.mkdir(parents=True, exist_ok=True)
        token_path.write_text(creds.to_json())

    return creds


def parse_space_thread(value: str) -> tuple[str | None, str | None]:
    if not value:
        return None, None

    if value.startswith("http"):
        frag = urlparse(value).fragment
        parts = [p for p in frag.split("/") if p]
        if len(parts) >= 3 and parts[0] == "chat" and parts[1] == "space":
            space = parts[2]
            thread = parts[3] if len(parts) >= 4 else None
            return space, thread
        return None, None

    if value.startswith("spaces/"):
        parts = [p for p in value.split("/") if p]
        space = parts[1] if len(parts) > 1 else None
        thread = None
        if "threads" in parts:
            idx = parts.index("threads")
            if len(parts) > idx + 1:
                thread = parts[idx + 1]
        return space, thread

    return value, None

#!/usr/bin/env python3
import argparse
import os
import sys
from pathlib import Path

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

DEFAULT_CLIENT_SECRET_PATH = os.path.expanduser("~/.config/youtube-publish/client_secret.json")
DEFAULT_TOKEN_PATH = os.path.expanduser("~/.config/youtube-publish/token.json")


def get_authenticated_service(client_secret_path: str, token_path: str):
    creds = None
    token_file = Path(token_path)
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            auth_url, _ = flow.authorization_url(
                access_type="offline",
                prompt="consent",
            )
            print("Open this URL in your browser, approve access, then paste the final URL:")
            print(auth_url)
            redirect_response = input("Paste full redirect URL: ").strip()
            flow.fetch_token(authorization_response=redirect_response)
            creds = flow.credentials
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(creds.to_json(), encoding="utf-8")

    return build("youtube", "v3", credentials=creds)

def parse_duration(value: str) -> int | None:
    if not value:
        return None
    if not value.startswith("P"):
        return None
    # Basic ISO 8601 duration parsing for PT#H#M#S
    hours = minutes = seconds = 0
    time_part = value.split("T")[-1] if "T" in value else ""
    number = ""
    for ch in time_part:
        if ch.isdigit():
            number += ch
            continue
        if ch == "H":
            hours = int(number or 0)
        elif ch == "M":
            minutes = int(number or 0)
        elif ch == "S":
            seconds = int(number or 0)
        else:
            return None
        number = ""
    return hours * 3600 + minutes * 60 + seconds


def format_duration(value: int | None) -> str:
    if value is None:
        return "n/a"
    minutes, seconds = divmod(value, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:d}:{seconds:02d}"


def main() -> int:
    parser = argparse.ArgumentParser(description="List recent YouTube uploads")
    parser.add_argument("--limit", type=int, default=10, help="Number of videos to list (default: 10)")
    parser.add_argument(
        "--min-seconds",
        type=int,
        default=0,
        help="Minimum duration in seconds (default: 0)",
    )
    parser.add_argument(
        "--client-secret",
        default=DEFAULT_CLIENT_SECRET_PATH,
        help="OAuth client secret JSON (default: ~/.config/youtube-publish/client_secret.json)",
    )
    parser.add_argument(
        "--token",
        default=DEFAULT_TOKEN_PATH,
        help="Token cache path (default: ~/.config/youtube-publish/token.json)",
    )
    parser.add_argument("--json", action="store_true", help="Output JSON")
    args = parser.parse_args()

    if args.limit <= 0:
        print("--limit must be a positive number", file=sys.stderr)
        return 2
    if args.min_seconds < 0:
        print("--min-seconds must be >= 0", file=sys.stderr)
        return 2

    if not Path(args.client_secret).exists():
        print(f"Missing client secret: {args.client_secret}", file=sys.stderr)
        return 1

    youtube = get_authenticated_service(args.client_secret, args.token)

    channel_resp = youtube.channels().list(part="contentDetails", mine=True).execute()
    items = channel_resp.get("items", [])
    if not items:
        print("No channel found for the authenticated user.", file=sys.stderr)
        return 1

    uploads_id = (
        items[0]
        .get("contentDetails", {})
        .get("relatedPlaylists", {})
        .get("uploads")
    )
    if not uploads_id:
        print("Could not resolve uploads playlist id.", file=sys.stderr)
        return 1

    playlist_resp = youtube.playlistItems().list(
        part="snippet,contentDetails,status",
        playlistId=uploads_id,
        maxResults=args.limit,
    ).execute()

    playlist_items = playlist_resp.get("items", [])
    video_ids = [
        item.get("contentDetails", {}).get("videoId")
        for item in playlist_items
        if item.get("contentDetails", {}).get("videoId")
    ]

    details_by_id = {}
    if video_ids:
        details_resp = youtube.videos().list(
            part="snippet,status,contentDetails",
            id=",".join(video_ids),
        ).execute()
        for item in details_resp.get("items", []):
            details_by_id[item.get("id")] = item

    results = []
    for item in playlist_items:
        video_id = item.get("contentDetails", {}).get("videoId")
        details = details_by_id.get(video_id, {}) if video_id else {}
        snippet = details.get("snippet", {})
        status = details.get("status", {})
        duration_raw = details.get("contentDetails", {}).get("duration")
        duration_seconds = parse_duration(duration_raw) if duration_raw else None
        results.append(
            {
                "video_id": video_id,
                "title": snippet.get("title") or item.get("snippet", {}).get("title"),
                "published_at": snippet.get("publishedAt") or item.get("snippet", {}).get("publishedAt"),
                "privacy_status": status.get("privacyStatus"),
                "duration_seconds": duration_seconds,
                "url": f"https://www.youtube.com/watch?v={video_id}" if video_id else None,
            }
        )

    if args.min_seconds:
        results = [
            entry
            for entry in results
            if entry.get("duration_seconds") is not None
            and entry.get("duration_seconds") >= args.min_seconds
        ]

    if args.json:
        import json

        print(json.dumps(results, indent=2, ensure_ascii=False))
        return 0

    for idx, entry in enumerate(results, start=1):
        published = entry.get("published_at") or ""
        status = entry.get("privacy_status") or ""
        duration = format_duration(entry.get("duration_seconds"))
        title = entry.get("title") or ""
        url = entry.get("url") or ""
        print(f"{idx:>2}. {published} | {status:<9} | {duration:<7} | {title}\n    {url}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

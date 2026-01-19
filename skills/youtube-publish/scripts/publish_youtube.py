#!/usr/bin/env python3
import argparse
import os
import re
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None

import yaml
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
]

DEFAULT_CONFIG_PATH = os.path.expanduser("~/.config/youtube-publish/config.yaml")
DEFAULT_TOKEN_PATH = os.path.expanduser("~/.config/youtube-publish/token.json")


def load_config(path: str) -> dict:
    p = Path(path)
    if not p.exists():
        return {}
    data = yaml.safe_load(p.read_text(encoding="utf-8"))
    return data or {}


def detect_system_timezone() -> str | None:
    env_tz = os.environ.get("TZ")
    if env_tz:
        return env_tz

    try:
        localtime = Path("/etc/localtime")
        if localtime.exists():
            target = os.path.realpath(localtime)
            match = re.search(r"/zoneinfo/(.+)$", target)
            if match:
                return match.group(1)
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["/usr/sbin/systemsetup", "-gettimezone"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            match = re.search(r"Time Zone:\\s*(\\S+)", result.stdout)
            if match:
                return match.group(1)
    except Exception:
        pass

    return None


def parse_publish_at(value: str, tz_name: str) -> str:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value)
    except ValueError:
        raise ValueError("publish-at must be ISO format: YYYY-MM-DD HH:MM")
    if dt.tzinfo is None:
        if ZoneInfo is None:
            raise ValueError("ZoneInfo not available; use Python 3.9+ or provide timezone offset")
        dt = dt.replace(tzinfo=ZoneInfo(tz_name))
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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


def upload_video(youtube, video_path: str, body: dict, thumbnail_path: str = None, notify_subscribers: bool = False):
    media = MediaFileUpload(video_path, chunksize=8 * 1024 * 1024, resumable=True)
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
        notifySubscribers=notify_subscribers,
    )

    response = None
    while response is None:
        status, response = request.next_chunk()
        if status:
            percent = int(status.progress() * 100)
            print(f"Upload {percent}%")

    video_id = response.get("id")
    if not video_id:
        raise RuntimeError("Upload failed: missing video id")

    if thumbnail_path:
        youtube.thumbnails().set(
            videoId=video_id,
            media_body=MediaFileUpload(thumbnail_path),
        ).execute()

    return video_id


def main():
    parser = argparse.ArgumentParser(description="Upload and schedule a YouTube video")
    parser.add_argument("--video", help="Path to video file")
    parser.add_argument("--title", required=True, help="Video title")
    parser.add_argument("--description", help="Video description")
    parser.add_argument("--description-file", help="Path to description text file")
    parser.add_argument("--tags", help="Comma-separated tags")
    parser.add_argument("--category-id", help="YouTube category id")
    parser.add_argument("--privacy-status", help="private|unlisted|public")
    parser.add_argument("--publish-at", help="Local time: YYYY-MM-DD HH:MM")
    parser.add_argument("--timezone", help="IANA timezone, default from config")
    parser.add_argument("--thumbnail", help="Path to thumbnail image")
    parser.add_argument("--update-video-id", help="Update an existing video id instead of uploading")
    parser.add_argument("--output-video-id", help="Write uploaded video id to this file")
    parser.add_argument("--notify-subscribers", action="store_true", help="Notify subscribers on publish")
    parser.add_argument("--no-notify-subscribers", action="store_true", help="Do not notify subscribers")
    parser.add_argument("--config", default=DEFAULT_CONFIG_PATH, help="Config path")
    parser.add_argument("--client-secret", required=True, help="OAuth client secret JSON")
    parser.add_argument("--token", default=DEFAULT_TOKEN_PATH, help="Token cache path")
    args = parser.parse_args()

    config = load_config(args.config)

    if not args.update_video_id:
        if not args.video:
            print("Video is required for upload", file=sys.stderr)
            sys.exit(1)
        video_path = Path(args.video)
        if not video_path.exists():
            print(f"Video not found: {video_path}", file=sys.stderr)
            sys.exit(1)
    else:
        video_path = Path(args.video) if args.video else None

    description = args.description
    if args.description_file:
        description = Path(args.description_file).read_text(encoding="utf-8").strip()
    if not description:
        print("Description is required (use --description or --description-file)", file=sys.stderr)
        sys.exit(1)

    tags = None
    if args.tags:
        tags = [t.strip() for t in args.tags.split(",") if t.strip()]
    elif isinstance(config.get("tags"), list):
        tags = config.get("tags")
    elif isinstance(config.get("tags"), str):
        tags = [t.strip() for t in config.get("tags").split(",") if t.strip()]

    publish_at = None
    if args.publish_at:
        timezone_name = args.timezone or config.get("timezone") or detect_system_timezone()
        if not timezone_name:
            raise ValueError("Timezone is required for publish-at (pass --timezone or set config)")
        publish_at = parse_publish_at(args.publish_at, timezone_name)

    privacy_status = args.privacy_status or config.get("privacy_status", "private")
    if publish_at:
        privacy_status = "private"

    category_id = args.category_id or config.get("category_id") or "27"
    made_for_kids = bool(config.get("made_for_kids", False))
    notify_subscribers = bool(config.get("notify_subscribers", False))
    if args.notify_subscribers:
        notify_subscribers = True
    if args.no_notify_subscribers:
        notify_subscribers = False
    default_language = config.get("default_language")
    default_audio_language = config.get("default_audio_language")

    snippet = {
        "title": args.title,
        "description": description,
    }
    if tags:
        snippet["tags"] = tags
    if category_id:
        snippet["categoryId"] = str(category_id)
    if default_language:
        snippet["defaultLanguage"] = default_language
    if default_audio_language:
        snippet["defaultAudioLanguage"] = default_audio_language

    status = {
        "privacyStatus": privacy_status,
        "selfDeclaredMadeForKids": made_for_kids,
    }
    if publish_at:
        status["publishAt"] = publish_at

    body = {
        "snippet": snippet,
        "status": status,
    }

    if not Path(args.client_secret).exists():
        print(f"Missing client secret: {args.client_secret}", file=sys.stderr)
        sys.exit(1)

    youtube = get_authenticated_service(args.client_secret, args.token)

    if args.update_video_id:
        update_body = {
            "id": args.update_video_id,
            "snippet": snippet,
            "status": status,
        }
        youtube.videos().update(part="snippet,status", body=update_body).execute()
        if args.thumbnail:
            youtube.thumbnails().set(
                videoId=args.update_video_id,
                media_body=MediaFileUpload(args.thumbnail),
            ).execute()
        print(f"Updated video id: {args.update_video_id}")
        if publish_at:
            print(f"Scheduled for: {publish_at} (UTC)")
    else:
        video_id = upload_video(
            youtube=youtube,
            video_path=str(video_path),
            body=body,
            thumbnail_path=args.thumbnail,
            notify_subscribers=notify_subscribers,
        )

        print(f"Uploaded video id: {video_id}")
        if args.output_video_id:
            Path(args.output_video_id).write_text(video_id, encoding="utf-8")
        if publish_at:
            print(f"Scheduled for: {publish_at} (UTC)")
        print(f"Notify subscribers: {notify_subscribers}")


if __name__ == "__main__":
    main()

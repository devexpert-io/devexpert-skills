#!/usr/bin/env python3
import argparse
import json
from pathlib import Path

from googleapiclient.discovery import build

from chat_common import (
    SCOPES,
    default_client_secret_path,
    default_token_path,
    load_credentials,
    parse_space_thread,
)


def format_message(msg: dict) -> str:
    timestamp = msg.get("createTime", "")
    sender = msg.get("sender", {}).get("displayName") or msg.get("sender", {}).get(
        "name", ""
    )
    text = msg.get("text") or msg.get("formattedText") or ""
    name = msg.get("name", "")
    return f"{timestamp} | {sender} | {text} | {name}".strip()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Google Chat messages.")
    parser.add_argument(
        "--space",
        required=True,
        help="Space ID, spaces/<id>, or Gmail Chat URL.",
    )
    parser.add_argument(
        "--thread",
        help="Thread ID (optional). If provided, filters messages by thread.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Number of messages to request (pageSize).",
    )
    parser.add_argument(
        "--page-token",
        dest="page_token",
        help="Page token for pagination.",
    )
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format.",
    )
    parser.add_argument(
        "--filter",
        help="Raw API filter string (optional).",
    )
    parser.add_argument(
        "--client-secret",
        type=Path,
        default=default_client_secret_path(),
        help="Path to OAuth client_secret.json",
    )
    parser.add_argument(
        "--token",
        type=Path,
        default=default_token_path(),
        help="Path to token.json",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Use console-based OAuth if token is missing/expired.",
    )
    args = parser.parse_args()

    space_id, thread_from_url = parse_space_thread(args.space)
    if not space_id:
        raise SystemExit("Could not parse space from --space.")

    thread_id = args.thread or thread_from_url

    creds = load_credentials(
        token_path=args.token,
        client_secret_path=args.client_secret,
        scopes=SCOPES,
        no_browser=args.no_browser,
    )

    service = build("chat", "v1", credentials=creds, cache_discovery=False)

    request_kwargs = {
        "parent": f"spaces/{space_id}",
        "pageSize": args.limit,
    }
    if args.page_token:
        request_kwargs["pageToken"] = args.page_token
    if args.filter:
        request_kwargs["filter"] = args.filter

    resp = service.spaces().messages().list(**request_kwargs).execute()
    messages = resp.get("messages", [])

    if thread_id:
        thread_name = f"spaces/{space_id}/threads/{thread_id}"
        messages = [
            msg for msg in messages if msg.get("thread", {}).get("name") == thread_name
        ]

    if args.format == "json":
        payload = {
            "space": f"spaces/{space_id}",
            "thread": thread_id,
            "nextPageToken": resp.get("nextPageToken"),
            "messages": messages,
        }
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    for msg in messages:
        print(format_message(msg))


if __name__ == "__main__":
    main()

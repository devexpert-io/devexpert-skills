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
)


def main() -> None:
    parser = argparse.ArgumentParser(description="List Google Chat spaces.")
    parser.add_argument("--limit", type=int, default=50, help="pageSize")
    parser.add_argument("--page-token", dest="page_token", help="Page token")
    parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
        help="Output format.",
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

    creds = load_credentials(
        token_path=args.token,
        client_secret_path=args.client_secret,
        scopes=SCOPES,
        no_browser=args.no_browser,
    )

    service = build("chat", "v1", credentials=creds, cache_discovery=False)

    request_kwargs = {"pageSize": args.limit}
    if args.page_token:
        request_kwargs["pageToken"] = args.page_token

    resp = service.spaces().list(**request_kwargs).execute()
    spaces = resp.get("spaces", [])

    if args.format == "json":
        print(json.dumps(resp, ensure_ascii=False, indent=2))
        return

    for space in spaces:
        name = space.get("name", "")
        display = space.get("displayName", "")
        space_type = space.get("spaceType", "")
        print(f"{name} | {display} | {space_type}")


if __name__ == "__main__":
    main()

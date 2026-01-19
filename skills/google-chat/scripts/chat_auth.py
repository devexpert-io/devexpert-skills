#!/usr/bin/env python3
import argparse
from pathlib import Path

from chat_common import SCOPES, default_client_secret_path, default_token_path, load_credentials


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create or refresh Google Chat OAuth token."
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
        help="Path to output token.json",
    )
    parser.add_argument(
        "--no-browser",
        action="store_true",
        help="Use console-based OAuth (prints URL instead of opening browser).",
    )
    args = parser.parse_args()

    load_credentials(
        token_path=args.token,
        client_secret_path=args.client_secret,
        scopes=SCOPES,
        no_browser=args.no_browser,
    )

    print(f"OK: token saved to {args.token}")


if __name__ == "__main__":
    main()

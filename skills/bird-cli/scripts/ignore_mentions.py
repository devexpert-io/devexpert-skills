#!/usr/bin/env python3
"""Mark X mentions as ignored for future listings."""

import argparse
import json
import os
import sys

DEFAULT_IGNORE_PATH = os.path.expanduser("~/.config/bird/ignored_mentions.json")


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


def load_json(path):
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def save_json(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main():
    parser = argparse.ArgumentParser(description="Ignore mentions by id")
    parser.add_argument("--username", required=True, help="Account username")
    parser.add_argument("--ignore-file", default=DEFAULT_IGNORE_PATH)
    parser.add_argument("--id", action="append", dest="ids", required=True, help="Mention id (repeatable)")
    args = parser.parse_args()

    data = load_json(args.ignore_file)
    if not isinstance(data, dict):
        data = {}

    username = args.username.lower()
    existing = data.get(username, {})
    if isinstance(existing, list):
        existing = {str(item): True for item in existing}
    if not isinstance(existing, dict):
        existing = {}

    for mid in args.ids:
        existing[str(mid)] = True

    data[username] = existing
    save_json(args.ignore_file, data)

    print(f"Ignored {len(args.ids)} mention(s) for @{username}")


if __name__ == "__main__":
    main()

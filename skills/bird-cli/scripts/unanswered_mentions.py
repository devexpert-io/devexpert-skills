#!/usr/bin/env python3
"""List unanswered mentions for a given X account via bird CLI."""

import argparse
import json
import os
import re
import subprocess
from datetime import datetime
from typing import List, Dict, Any

DATE_FORMAT = "%a %b %d %H:%M:%S %z %Y"
DEFAULT_IGNORE_PATH = os.path.expanduser("~/.config/bird/ignored_mentions.json")
SKILLS_CONFIG_PATH = os.path.expanduser("~/.config/skills/config.json")


def run_bird(args: List[str]) -> str:
    proc = subprocess.run(["bird", *args], text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "bird command failed")
    return proc.stdout


def base_args(opts: argparse.Namespace) -> List[str]:
    args: List[str] = []
    if opts.auth_token:
        args += ["--auth-token", opts.auth_token]
    if opts.ct0:
        args += ["--ct0", opts.ct0]
    if opts.cookie_source:
        args += ["--cookie-source", opts.cookie_source]
    if opts.chrome_profile:
        args += ["--chrome-profile", opts.chrome_profile]
    if opts.firefox_profile:
        args += ["--firefox-profile", opts.firefox_profile]
    return args


def load_skills_config() -> Dict[str, Any]:
    try:
        with open(SKILLS_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def parse_username_from_whoami(output: str) -> str:
    match = re.search(r"@([A-Za-z0-9_]+)", output)
    if not match:
        raise ValueError("Unable to parse username from bird whoami output")
    return match.group(1)


def load_mentions(opts: argparse.Namespace) -> List[Dict[str, Any]]:
    args = base_args(opts) + ["mentions", "--json"]
    return json.loads(run_bird(args))


def load_replies(opts: argparse.Namespace, tweet_id: str) -> List[Dict[str, Any]]:
    args = base_args(opts) + ["replies", tweet_id, "--json"]
    return json.loads(run_bird(args))


def parse_date(value: str) -> datetime:
    return datetime.strptime(value, DATE_FORMAT)


def load_ignored_ids(path: str, username: str) -> set:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        return set()
    except json.JSONDecodeError:
        return set()

    if not isinstance(data, dict):
        return set()

    entries = data.get(username, [])
    if isinstance(entries, dict):
        return set(entries.keys())
    if isinstance(entries, list):
        return set(str(item) for item in entries)
    return set()


def main() -> int:
    parser = argparse.ArgumentParser(description="List unanswered mentions via bird CLI")
    parser.add_argument("--cookie-source", default="chrome", help="Cookie source for bird (default: chrome)")
    parser.add_argument("--chrome-profile", help="Chrome profile name (e.g., Default, Profile 1)")
    parser.add_argument("--firefox-profile", help="Firefox profile name")
    parser.add_argument("--auth-token", help="X auth_token cookie")
    parser.add_argument("--ct0", help="X ct0 cookie")
    parser.add_argument("--username", help="Account username (auto-detected if omitted)")
    parser.add_argument("--limit", type=int, default=0, help="Limit results (0 = no limit)")
    parser.add_argument("--show-text", action="store_true", help="Include mention text")
    parser.add_argument("--include-unknown", action="store_true", help="Include items with reply check errors")
    parser.add_argument("--json-out", help="Write results to JSON file")
    parser.add_argument("--ignore-file", default=DEFAULT_IGNORE_PATH, help="Path to ignored mentions JSON")
    parser.add_argument("--no-ignore", action="store_true", help="Do not filter ignored mentions")
    parser.add_argument("--numbered", action="store_true", help="Prefix output with index")

    opts = parser.parse_args()

    config = load_skills_config().get("bird", {})
    if not opts.chrome_profile and not opts.firefox_profile and not opts.auth_token:
        opts.chrome_profile = config.get("chrome_profile")
        opts.firefox_profile = config.get("firefox_profile")
    if not opts.username:
        cfg_user = config.get("username")
        if cfg_user:
            opts.username = cfg_user

    if not (opts.chrome_profile or opts.firefox_profile or opts.auth_token):
        raise SystemExit("Provide a browser profile or auth tokens for bird")

    username = opts.username
    if not username:
        whoami = run_bird(base_args(opts) + ["whoami", "--plain"])
        username = parse_username_from_whoami(whoami).lower()
    else:
        username = username.lower()

    mentions = load_mentions(opts)
    results = []

    ignored_ids = set()
    if not opts.no_ignore:
        ignored_ids = load_ignored_ids(opts.ignore_file, username)

    for mention in mentions:
        mid = mention.get("id")
        if not mid:
            continue
        status = "unknown"
        try:
            replies = load_replies(opts, mid)
            replied = any(
                (r.get("author", {}) or {}).get("username", "").lower() == username
                for r in replies
            )
            status = "respondida" if replied else "sin_responder"
        except Exception:
            status = "unknown"

        if status == "sin_responder" or (opts.include_unknown and status == "unknown"):
            if str(mid) in ignored_ids:
                continue
            results.append({
                "createdAt": mention.get("createdAt"),
                "author": (mention.get("author", {}) or {}).get("username"),
                "text": mention.get("text", ""),
                "id": mid,
                "status": status,
            })

    results.sort(key=lambda r: parse_date(r["createdAt"]) if r["createdAt"] else datetime.min, reverse=True)

    if opts.limit and opts.limit > 0:
        results = results[: opts.limit]

    indexed = []
    for idx, item in enumerate(results, start=1):
        author = item.get("author", "")
        url = f"https://x.com/{author}/status/{item.get('id')}" if author else ""
        indexed.append({**item, "index": idx, "url": url})

    if opts.json_out:
        os.makedirs(os.path.dirname(opts.json_out), exist_ok=True)
        with open(opts.json_out, "w", encoding="utf-8") as f:
            json.dump(indexed, f, ensure_ascii=False, indent=2)

    def format_label(created: str | None) -> str:
        if not created:
            return "Unknown date"
        try:
            return parse_date(created).strftime("%d/%m/%Y")
        except ValueError:
            return "Unknown date"

    current_label: str | None = None

    for r in indexed:
        label = format_label(r.get("createdAt"))
        if label != current_label:
            if current_label is not None:
                print()
            print(f"**{label}**:")
            print()
            current_label = label

        author = r.get("author", "")
        url = r.get("url", "")
        prefix = f"{r.get('index')}) " if opts.numbered else ""
        line = f"- {prefix}@{author} | {url}"
        print(line)
        if opts.show_text and r.get("text"):
            print(f"  {r['text']}")
            print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

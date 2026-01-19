#!/usr/bin/env python3
import argparse
import json
import os
import subprocess
from pathlib import Path

SKILLS_CONFIG_PATH = os.path.expanduser("~/.config/skills/config.json")


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout


def load_skills_config() -> dict:
    try:
        with open(SKILLS_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def main():
    parser = argparse.ArgumentParser(description="Schedule newsletter via Listmonk CLI")
    parser.add_argument("--subject", required=True, help="Email subject")
    parser.add_argument("--preheader", required=False, help="Email preheader")
    parser.add_argument("--body-file", required=True, help="Markdown body file")
    parser.add_argument("--send-at", required=True, help="ISO 8601 datetime with offset")
    parser.add_argument("--name", required=True, help="Campaign name")
    parser.add_argument("--list-id", type=int, help="Listmonk list ID")
    args = parser.parse_args()

    config = load_skills_config().get("youtube_publish", {})
    list_id = args.list_id or config.get("listmonk_list_id")
    if not list_id:
        raise SystemExit(
            "Missing list id (pass --list-id or set youtube_publish.listmonk_list_id in "
            "~/.config/skills/config.json)"
        )

    body_path = Path(args.body_file)
    body = body_path.read_text(encoding="utf-8").strip()
    preheader = (args.preheader or "").strip()
    if preheader:
        body = f"<!-- preheader: {preheader} -->\n\n" + body
    tmp_path = body_path.parent / "newsletter.scheduled.md"
    tmp_path.write_text(body, encoding="utf-8")

    cmd = [
        "listmonk",
        "campaigns",
        "create",
        "--name",
        args.name,
        "--subject",
        args.subject,
        "--lists",
        str(list_id),
        "--body-file",
        str(tmp_path),
        "--content-type",
        "markdown",
        "--send-at",
        args.send_at,
    ]
    run(cmd)
    print("Scheduled newsletter.")


if __name__ == "__main__":
    main()

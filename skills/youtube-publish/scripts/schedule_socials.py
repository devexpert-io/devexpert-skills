#!/usr/bin/env python3
import argparse
import json
import os
import subprocess

SKILLS_CONFIG_PATH = os.path.expanduser("~/.config/skills/config.json")


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout.strip()


def upload_image(path):
    if not path:
        return None
    raw = run(["postiz", "upload", "--file-path", path])
    data = json.loads(raw)
    for key in ["url", "public_url", "publicUrl"]:
        if key in data:
            return data[key]
    if "file" in data:
        file_obj = data["file"]
        for key in ["url", "public_url", "publicUrl"]:
            if key in file_obj:
                return file_obj[key]
    return None


def load_skills_config() -> dict:
    try:
        with open(SKILLS_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def parse_integrations(raw: str) -> list[str]:
    if not raw:
        return []
    parts = [p.strip() for p in raw.split(",")]
    return [p for p in parts if p]


def resolve_integration_id(key: str, integrations: dict) -> str | None:
    if key in integrations:
        value = integrations.get(key)
        if isinstance(value, dict):
            return value.get("id") or None
        if isinstance(value, str):
            return value
    return key or None


def resolve_group_integrations(group_name: str, postiz: dict) -> list[str]:
    groups = postiz.get("groups", {})
    if not isinstance(groups, dict):
        return []
    group = groups.get(group_name, [])
    if not isinstance(group, list):
        return []
    integrations = postiz.get("integrations", {})
    resolved = []
    for item in group:
        if not isinstance(item, str):
            continue
        integration_id = resolve_integration_id(item, integrations)
        if integration_id:
            resolved.append(integration_id)
    return resolved


def main():
    parser = argparse.ArgumentParser(description="Schedule socials via Postiz CLI")
    parser.add_argument("--text-file", required=True, help="Path to post text")
    parser.add_argument("--scheduled-date", required=True, help="ISO 8601 datetime with offset")
    parser.add_argument("--comment-url", required=True, help="URL for first comment")
    parser.add_argument("--image", help="Thumbnail image path")
    parser.add_argument("--integrations", help="Comma-separated Postiz integration IDs")
    parser.add_argument("--group", help="Postiz group name from config (default: youtube_publish)")
    args = parser.parse_args()

    skills_cfg = load_skills_config()
    postiz_cfg = skills_cfg.get("postiz", {})
    yt_cfg = skills_cfg.get("youtube_publish", {})
    group_name = args.group or yt_cfg.get("postiz_group") or "youtube_publish"

    integrations = parse_integrations(args.integrations)
    if not integrations:
        integrations = resolve_group_integrations(group_name, postiz_cfg)
    if not integrations:
        integrations = yt_cfg.get("postiz_integrations", [])
    if not integrations:
        raise SystemExit(
            "Missing Postiz integrations (pass --integrations or set postiz.groups/postiz.integrations "
            "in ~/.config/skills/config.json)"
        )

    text = open(args.text_file, "r", encoding="utf-8").read().strip()
    if "#" in text:
        text = text.replace("#", "")
    if not text.endswith("Link en el primer comentario."):
        if not text.endswith("."):
            text += "."
        text += "\n\nLink en el primer comentario."

    image_url = upload_image(args.image) if args.image else None

    content_json = json.dumps([text, args.comment_url])

    for integration_id in integrations:
        cmd = [
            "postiz",
            "posts",
            "create",
            "--content",
            content_json,
            "--integrations",
            integration_id,
            "--status",
            "scheduled",
            "--scheduled-date",
            args.scheduled_date,
        ]
        if image_url:
            cmd += ["--images", json.dumps([image_url])]
        run(cmd)

    print("Scheduled socials.")


if __name__ == "__main__":
    main()

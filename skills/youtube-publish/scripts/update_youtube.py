#!/usr/bin/env python3
import argparse
from pathlib import Path
import subprocess


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description="Update YouTube video metadata")
    parser.add_argument("--video-id", required=True, help="YouTube video id")
    parser.add_argument("--title", required=True, help="Final title")
    parser.add_argument("--description-file", required=True, help="Final description file")
    parser.add_argument("--client-secret", required=True, help="OAuth client secret JSON")
    parser.add_argument("--thumbnail", help="Thumbnail path")
    parser.add_argument("--publish-at", help="Local time: YYYY-MM-DD HH:MM")
    parser.add_argument("--timezone", help="IANA timezone, required if publish-at")
    parser.add_argument("--privacy-status", help="private|unlisted|public")
    parser.add_argument("--category-id", help="YouTube category id")
    args = parser.parse_args()

    cmd = [
        "python",
        str(Path(__file__).parent / "publish_youtube.py"),
        "--update-video-id",
        args.video_id,
        "--title",
        args.title,
        "--description-file",
        args.description_file,
        "--client-secret",
        args.client_secret,
    ]
    if args.thumbnail:
        cmd += ["--thumbnail", args.thumbnail]
    if args.publish_at:
        if not args.timezone:
            raise RuntimeError("--timezone is required with --publish-at")
        cmd += ["--publish-at", args.publish_at, "--timezone", args.timezone]
    if args.privacy_status:
        cmd += ["--privacy-status", args.privacy_status]
    if args.category_id:
        cmd += ["--category-id", args.category_id]

    run(cmd)


if __name__ == "__main__":
    main()

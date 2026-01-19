#!/usr/bin/env python3
import argparse
from datetime import datetime
from pathlib import Path
import subprocess


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description="Upload draft YouTube video")
    parser.add_argument("--video", required=True, help="Video path")
    parser.add_argument("--output-video-id", required=True, help="File to store video id")
    parser.add_argument("--client-secret", required=True, help="OAuth client secret JSON")
    args = parser.parse_args()

    title = f"Draft {datetime.now().strftime('%Y-%m-%d %H:%M')}"
    desc_path = Path(args.output_video_id).parent / "description.draft.txt"
    desc_path.write_text("Draft upload. Metadata will be updated.", encoding="utf-8")

    cmd = [
        "python",
        str(Path(__file__).parent / "publish_youtube.py"),
        "--video",
        args.video,
        "--title",
        title,
        "--description-file",
        str(desc_path),
        "--privacy-status",
        "private",
        "--output-video-id",
        args.output_video_id,
        "--client-secret",
        args.client_secret,
    ]
    run(cmd)

    # Read video id and write URL file
    vid = Path(args.output_video_id).read_text(encoding='utf-8').strip()
    if vid:
        url_path = Path(args.output_video_id).parent / "video_url.txt"
        url_path.write_text(f"https://www.youtube.com/watch?v={vid}", encoding="utf-8")


if __name__ == "__main__":
    main()

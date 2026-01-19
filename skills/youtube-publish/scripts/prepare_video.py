#!/usr/bin/env python3
import argparse
import json
import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout


def safe_slug(text):
    text = re.sub(r"[^a-zA-Z0-9\-\s]", "", text).strip().lower()
    text = re.sub(r"\s+", "-", text)
    return text or "video"


def ensure_dir(path: Path):
    path.mkdir(parents=True, exist_ok=True)


def move_inputs(videos, inputs_dir):
    moved = []
    for video in videos:
        src = Path(video)
        if not src.exists():
            raise FileNotFoundError(f"Missing video: {src}")
        dst = inputs_dir / src.name
        shutil.move(src, dst)
        moved.append(dst)
    return moved


def concat_videos(videos, out_path: Path):
    list_file = out_path.parent / "concat_list.txt"
    with list_file.open("w", encoding="utf-8") as f:
        for v in videos:
            f.write(f"file '{v.as_posix()}'\n")
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "concat",
        "-safe",
        "0",
        "-i",
        str(list_file),
        "-c",
        "copy",
        str(out_path),
    ]
    run(cmd)
    return out_path


def main():
    parser = argparse.ArgumentParser(description="Prepare YouTube workdir and video")
    parser.add_argument("--videos", nargs="+", required=True, help="Input video file(s)")
    parser.add_argument("--title-hint", help="Optional title hint for folder naming")
    parser.add_argument("--workdir", help="Output folder")
    args = parser.parse_args()

    now = datetime.now().strftime("%Y-%m-%d_%H%M")
    slug = safe_slug(args.title_hint or Path(args.videos[0]).stem)
    workdir = Path(args.workdir) if args.workdir else Path(args.videos[0]).parent / f"{now}_{slug}"
    ensure_dir(workdir)

    inputs_dir = workdir / "inputs"
    ensure_dir(inputs_dir)
    moved = move_inputs(args.videos, inputs_dir)

    if len(moved) == 1:
        original = moved[0]
        video_out = workdir / f"{slug}.mp4"
        if original.resolve() != video_out.resolve():
            shutil.move(original, video_out)
    else:
        video_out = workdir / f"{slug}.mp4"
        concat_videos(moved, video_out)

    result = {
        "workdir": str(workdir),
        "video": str(video_out),
        "slug": slug,
    }
    print(json.dumps(result))


if __name__ == "__main__":
    main()

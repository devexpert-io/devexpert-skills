#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path


def get_assets_dir() -> Path:
    return Path(__file__).resolve().parent.parent / "assets"


def word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def normalize_thumb_text(text: str) -> str:
    cleaned = (text or "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    banned = {"facil", "fácil", "rapido", "rápido", "secreto"}
    words = [w for w in cleaned.split(" ") if w.lower() not in banned]
    return " ".join(words[:4]).strip()


def build_image_prompt(thumb: dict) -> str:
    thumb_text = normalize_thumb_text(str(thumb.get("text", "") or ""))
    if word_count(thumb_text) > 4:
        thumb_text = " ".join(thumb_text.split(" ")[:4]).strip()

    artifact = str(thumb.get("artifact", "") or "")
    concept = str(thumb.get("concept", "") or "")

    return (
        "Create a YouTube thumbnail (16:9). "
        "Use the provided photo as Antonio's portrait (keep identity, face sharp, no distortions). "
        "Background: dark mode gradient cyan/purple, cinematic lighting, minimalist. "
        f"Include a technical artifact: {artifact}. "
        f"Concept: {concept}. "
        f'Add large bold text (<=4 words): \"{thumb_text}\". '
        "High contrast, clean typography, no extra text, no watermark."
    )


def run_generate_image(
    image_script: Path,
    prompt: str,
    output_path: Path,
    input_image: Path,
    timeout_s: int,
) -> None:
    cmd = [
        sys.executable,
        str(image_script),
        "--prompt",
        prompt,
        "--filename",
        str(output_path),
        "--input-image",
        str(input_image),
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout_s,
    )

    if result.returncode != 0:
        stderr = (result.stderr or "").strip()
        stdout = (result.stdout or "").strip()
        raise RuntimeError(stderr or stdout or f"Command failed: {' '.join(cmd)}")

    if not output_path.exists():
        raise RuntimeError("Image generation succeeded but output file was not created")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Generate missing thumb-*.png files from existing ideas.json"
    )
    parser.add_argument(
        "--out-dir",
        default=os.path.expanduser("~/Downloads/youtube-videos"),
        help="Directory containing per-video folders",
    )
    parser.add_argument(
        "--timeout-s",
        type=int,
        default=90,
        help="Per-image generation timeout in seconds (default: 90)",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=1,
        help="Retries per image on failure (default: 1)",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Regenerate thumbs even if files already exist",
    )
    args = parser.parse_args()

    if args.timeout_s <= 0:
        print("--timeout-s must be > 0", file=sys.stderr)
        return 2
    if args.retries < 0:
        print("--retries must be >= 0", file=sys.stderr)
        return 2

    out_dir = Path(os.path.expanduser(args.out_dir))
    if not out_dir.exists():
        print(f"Missing out dir: {out_dir}", file=sys.stderr)
        return 1

    assets_dir = get_assets_dir()
    photo_map = {
        "assets/antonio-1.png": assets_dir / "antonio-1.png",
        "assets/antonio-2.png": assets_dir / "antonio-2.png",
        "assets/antonio-3.png": assets_dir / "antonio-3.png",
    }

    image_script = (
        Path(__file__).resolve().parents[2]
        / "3rd-nano-banana-pro"
        / "scripts"
        / "generate_image.py"
    )
    if not image_script.exists():
        print(f"Missing image generator script: {image_script}", file=sys.stderr)
        return 1

    ok = 0
    failed = 0
    skipped = 0

    for video_dir in sorted([p for p in out_dir.iterdir() if p.is_dir()]):
        ideas_path = video_dir / "ideas.json"
        if not ideas_path.exists():
            continue

        try:
            payload = json.loads(ideas_path.read_text(encoding="utf-8"))
        except Exception as exc:
            (video_dir / "error.thumbs.txt").write_text(
                f"Failed to read ideas.json: {exc}\n",
                encoding="utf-8",
            )
            failed += 1
            continue

        thumbnails = payload.get("thumbnails")
        if not isinstance(thumbnails, list) or not thumbnails:
            (video_dir / "error.thumbs.txt").write_text(
                "Invalid ideas.json: missing thumbnails\n",
                encoding="utf-8",
            )
            failed += 1
            continue

        for idx, thumb in enumerate(thumbnails, start=1):
            if not isinstance(thumb, dict):
                continue

            out_img = video_dir / f"thumb-{idx}.png"
            if out_img.exists() and not args.force:
                skipped += 1
                continue

            photo_key = str(thumb.get("photo", "") or "")
            input_photo = photo_map.get(photo_key)
            if input_photo is None:
                basename = Path(photo_key).name
                input_photo = next(
                    (p for k, p in photo_map.items() if Path(k).name == basename),
                    None,
                )

            if input_photo is None or not input_photo.exists():
                (video_dir / "error.thumbs.txt").write_text(
                    f"Missing input photo for thumb-{idx}: {photo_key}\n",
                    encoding="utf-8",
                )
                failed += 1
                continue

            prompt = build_image_prompt(thumb)
            (video_dir / f"thumb-{idx}.prompt.txt").write_text(
                prompt,
                encoding="utf-8",
            )

            attempt = 0
            while True:
                try:
                    run_generate_image(
                        image_script=image_script,
                        prompt=prompt,
                        output_path=out_img,
                        input_image=input_photo,
                        timeout_s=args.timeout_s,
                    )
                    ok += 1
                    break
                except Exception as exc:
                    attempt += 1
                    if attempt > args.retries:
                        (video_dir / "error.thumbs.txt").write_text(
                            f"Failed to generate thumb-{idx}: {exc}\n",
                            encoding="utf-8",
                        )
                        failed += 1
                        break

    print(f"Generated: {ok} | Skipped: {skipped} | Failed: {failed} | Out: {out_dir}")
    return 0 if failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())

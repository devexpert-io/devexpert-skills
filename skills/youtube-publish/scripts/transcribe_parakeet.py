#!/usr/bin/env python3
import argparse
import re
import subprocess
from pathlib import Path


def run(cmd):
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout


def apply_replacements(text):
    replacements = [
        (r"\bcloudbot\b", "ClawdBot"),
        (r"\bclawdbot\b", "ClawdBot"),
        (r"\bcloudboat\b", "ClawdBot"),
        (r"\bjust\s*do\s*it\b", "justdoit"),
        (r"\bcloud\s+opus\b", "Claude Opus"),
        (r"\bwhatsapp\b", "WhatsApp"),
        (r"\btelegram\b", "Telegram"),
        (r"\bgemini\b", "Gemini"),
        (r"\bgoogle\s+places\b", "Google Places"),
        (r"\bgmail\b", "Gmail"),
        (r"\bgoogle\s+sheets\b", "Google Sheets"),
        (r"\bgoogle\s+drive\b", "Google Drive"),
    ]
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    text = re.sub(r"\b[xX]\b", "X", text)
    return text


def main():
    parser = argparse.ArgumentParser(description="Transcribe with Parakeet MLX and clean text")
    parser.add_argument("--video", required=True, help="Video path")
    parser.add_argument("--out-dir", required=True, help="Output directory")
    args = parser.parse_args()

    video_path = Path(args.video)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        "parakeet-mlx",
        str(video_path),
        "--output-dir",
        str(out_dir),
        "--output-format",
        "srt",
    ]
    run(cmd)

    srt_path = out_dir / f"{video_path.stem}.srt"
    if not srt_path.exists():
        raise FileNotFoundError("Parakeet SRT not found")

    text = srt_path.read_text(encoding="utf-8")
    cleaned = apply_replacements(text)

    cleaned_path = out_dir / "transcript.es.cleaned.srt"
    cleaned_path.write_text(cleaned, encoding="utf-8")

    print(str(cleaned_path))


if __name__ == "__main__":
    main()

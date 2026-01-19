#!/usr/bin/env python3
import argparse
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

try:
    from zoneinfo import ZoneInfo
except Exception:
    ZoneInfo = None


def run(cmd, input_text=None):
    result = subprocess.run(
        cmd,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"Command failed: {' '.join(cmd)}\n{result.stderr}")
    return result.stdout


def parse_local_datetime(value: str, tz_name: str) -> datetime:
    dt = datetime.fromisoformat(value)
    if dt.tzinfo is None:
        if ZoneInfo is None:
            raise RuntimeError("ZoneInfo not available; use Python 3.9+ or provide timezone offset")
        dt = dt.replace(tzinfo=ZoneInfo(tz_name))
    return dt


def detect_system_timezone() -> str | None:
    env_tz = os.environ.get("TZ")
    if env_tz:
        return env_tz

    try:
        localtime = Path("/etc/localtime")
        if localtime.exists():
            target = os.path.realpath(localtime)
            match = re.search(r"/zoneinfo/(.+)$", target)
            if match:
                return match.group(1)
    except Exception:
        pass

    try:
        result = subprocess.run(
            ["/usr/sbin/systemsetup", "-gettimezone"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0:
            match = re.search(r"Time Zone:\\s*(\\S+)", result.stdout)
            if match:
                return match.group(1)
    except Exception:
        pass

    return None

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


def transcribe_parakeet(video_path: Path, workdir: Path):
    cmd = [
        "parakeet-mlx",
        str(video_path),
        "--output-dir",
        str(workdir),
        "--output-format",
        "srt",
    ]
    run(cmd)
    # parakeet outputs {filename}.srt
    srt_path = workdir / f"{video_path.stem}.srt"
    if not srt_path.exists():
        raise FileNotFoundError("Parakeet SRT not found")
    return srt_path


def apply_replacements(text, replacements):
    for pattern, repl in replacements:
        text = re.sub(pattern, repl, text, flags=re.IGNORECASE)
    text = re.sub(r"\b[xX]\b", "X", text)
    return text


def generate_content_md(srt_text, workdir: Path, title_hint: str, video_url: str | None):
    prompt = (
        "Eres editor de YouTube. Con el SRT que recibes por stdin, genera en español:\n"
        "- 3 títulos\n"
        "- 3 ideas de thumbnails (texto corto)\n"
        "- Descripción (1-2 párrafos)\n"
        "- Capítulos con timestamps reales (formato MM:SS Título). 10-12 capítulos. No redondees.\n"
        "- Post LinkedIn (optimizado para LinkedIn, conversacional)\n"
        "- Newsletter (tono cercano, 220-320 palabras, CTA a comentar en el vídeo)\n\n"
        "Newsletter estructura:\n"
        "1) Saludo + contexto personal breve (1-2 frases)\n"
        "2) Desarrollo con 2-3 párrafos (qué probé, qué aprendí, por qué importa)\n"
        "3) 'En el vídeo verás:' + 2-4 bullets\n"
        "4) Línea con el enlace exacto al vídeo\n"
        "5) Cierre cercano + CTA: deja tu opinión en los comentarios del vídeo\n"
        "6) P.D. opcional (1 frase)\n"
        "Incluye al inicio de la newsletter:\n"
        "- Asunto: ...\n"
        "- Preheader: ...\n"
        "Varía la apertura y el ritmo; evita plantillas repetitivas.\n"
        "Incluye el enlace del vídeo en la newsletter.\n"
        "Post LinkedIn reglas:\n"
        "- 600–900 caracteres, 3–6 párrafos cortos, 1–2 emojis\n"
        "- 1 idea central, sin desviarse\n"
        "- Línea final: “Link en el primer comentario.”\n"
        "- Cierre con pregunta breve o CTA a comentar\n"
        "- Sin hashtags\n"
        "En redes, indica que el enlace estará en el primer comentario (no pongas la URL ahí).\n"
        "Reglas: no inventes; usa tokens exactos: ClawdBot, justdoit, MCP, Gemini, Google Places, WhatsApp, Telegram, Gmail, Google Sheets, Google Drive, X.\n"
        "Salida: Markdown con encabezados exactamente: \n"
        "## Títulos\n## Ideas de thumbnails\n## Descripción\n## Capítulos\n## LinkedIn\n## Newsletter\n"
    )
    if video_url:
        prompt = f"Enlace del vídeo: {video_url}\n\n" + prompt

    output = run(["gemini", prompt], input_text=srt_text)

    template = f"""# Pack YouTube — {title_hint or 'Sin título'}

## Enlace del vídeo
{video_url or ''}

## Título (final)

## Descripción (final)

## Capítulos (final)

## Post LinkedIn (final)

## Newsletter (final)

## Asunto newsletter (final)

## Preheader newsletter (final)

## Thumbnail (final)

## Programación (final)
(YYYY-MM-DD HH:MM o "private")

# Candidatos (generado)
{output.strip()}
"""

    out_path = workdir / "content.md"
    out_path.write_text(template, encoding="utf-8")
    return out_path


def extract_section(md_text, heading):
    pattern = rf"^## {re.escape(heading)}\s*$"
    lines = md_text.splitlines()
    out = []
    capture = False
    for line in lines:
        if re.match(pattern, line.strip()):
            capture = True
            continue
        if capture and line.startswith("## "):
            break
        if capture:
            out.append(line)
    return "\n".join(out).strip()


def main():
    parser = argparse.ArgumentParser(description="End-to-end YouTube prep workflow")
    parser.add_argument("--videos", nargs="+", required=True, help="Input video file(s)")
    parser.add_argument("--title-hint", help="Optional title hint for folder naming")
    parser.add_argument("--workdir", help="Output folder")
    parser.add_argument("--skip-transcribe", action="store_true")
    parser.add_argument("--skip-gemini", action="store_true")
    parser.add_argument("--skip-draft-upload", action="store_true")
    parser.add_argument("--upload", action="store_true", help="Upload via publish_youtube.py after validation")
    parser.add_argument("--client-secret", required=True, help="OAuth client secret JSON")
    parser.add_argument("--publish-at", help="Schedule time: YYYY-MM-DD HH:MM")
    parser.add_argument("--timezone")
    parser.add_argument("--thumbnail", help="Thumbnail path (optional, final)")
    parser.add_argument("--privacy-status", help="private|unlisted|public")
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

    video_id = None
    video_url = None
    if not args.skip_draft_upload:
        draft_title = args.title_hint or video_out.stem.replace("-", " ").title()
        draft_desc = workdir / "description.draft.txt"
        draft_desc.write_text("Draft upload. Metadata will be updated.", encoding="utf-8")
        video_id_path = workdir / "video_id.txt"
        cmd = [
            sys.executable,
            str(Path(__file__).parent / "publish_youtube.py"),
            "--video",
            str(video_out),
            "--title",
            draft_title,
            "--description-file",
            str(draft_desc),
            "--privacy-status",
            "private",
            "--output-video-id",
            str(video_id_path),
            "--client-secret",
            args.client_secret,
        ]
        run(cmd)
        if video_id_path.exists():
            video_id = video_id_path.read_text(encoding="utf-8").strip()
            if video_id:
                video_url = f"https://www.youtube.com/watch?v={video_id}"
                (workdir / "video_url.txt").write_text(video_url, encoding="utf-8")

    srt_path = None
    cleaned_srt_path = None

    if not args.skip_transcribe:
        srt_path = transcribe_parakeet(video_out, workdir)
        srt_text = srt_path.read_text(encoding="utf-8")

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
        cleaned = apply_replacements(srt_text, replacements)
        cleaned_srt_path = workdir / "transcript.es.cleaned.srt"
        cleaned_srt_path.write_text(cleaned, encoding="utf-8")
    else:
        cleaned_srt_path = None

    content_path = None
    if not args.skip_gemini:
        if not cleaned_srt_path:
            raise RuntimeError("No transcript available for gemini generation")
        content_path = generate_content_md(
            cleaned_srt_path.read_text(encoding="utf-8"),
            workdir,
            args.title_hint or "",
            video_url,
        )

    if content_path:
        print(f"Content created: {content_path}")
        print("Edit the FINAL sections, then press Enter to continue (or Ctrl+C to stop).")
        input()

    if args.upload:
        if not content_path:
            raise RuntimeError("content.md required for upload")
        md = content_path.read_text(encoding="utf-8")
        title = extract_section(md, "Título (final)")
        description = extract_section(md, "Descripción (final)")
        thumbnail = extract_section(md, "Thumbnail (final)") or args.thumbnail
        publish_at = extract_section(md, "Programación (final)") or args.publish_at
        schedule_input = (publish_at or "").strip()
        force_private = False
        explicit_private = schedule_input.lower() in {"private", "privado"}
        if explicit_private:
            schedule_input = ""
            force_private = True

        if not title or not description:
            raise RuntimeError("Missing final title or description in content.md")

        desc_file = workdir / "description.final.txt"
        desc_file.write_text(description, encoding="utf-8")

        cmd = [
            sys.executable,
            str(Path(__file__).parent / "publish_youtube.py"),
            "--title",
            title.strip(),
            "--description-file",
            str(desc_file),
            "--client-secret",
            args.client_secret,
        ]
        if video_id:
            cmd += ["--update-video-id", video_id]
        else:
            cmd += ["--video", str(video_out)]
        if thumbnail:
            cmd += ["--thumbnail", thumbnail.strip()]
        scheduled_iso = None
        if schedule_input:
            timezone_name = args.timezone or detect_system_timezone()
            if not timezone_name:
                raise RuntimeError("Timezone is required for publish-at (pass --timezone)")
            publish_dt = parse_local_datetime(schedule_input.strip(), timezone_name)
            scheduled_dt = publish_dt + timedelta(minutes=15)
            scheduled_iso = scheduled_dt.isoformat()
            cmd += ["--timezone", timezone_name]
            cmd += ["--publish-at", schedule_input.strip()]
        if force_private:
            cmd += ["--privacy-status", "private"]
        if args.privacy_status:
            cmd += ["--privacy-status", args.privacy_status]

        run(cmd)

        if scheduled_iso:
            linkedin_text = extract_section(md, "Post LinkedIn (final)")
            subject = extract_section(md, "Asunto newsletter (final)")
            preheader = extract_section(md, "Preheader newsletter (final)")
            newsletter = extract_section(md, "Newsletter (final)")

            if not linkedin_text or not subject or not newsletter:
                raise RuntimeError("Missing LinkedIn/Newsletter sections for scheduling")

            linkedin_path = workdir / "linkedin.final.txt"
            linkedin_path.write_text(linkedin_text.strip(), encoding="utf-8")

            newsletter_path = workdir / "newsletter.final.md"
            newsletter_path.write_text(newsletter.strip(), encoding="utf-8")

            social_cmd = [
                sys.executable,
                str(Path(__file__).parent / "schedule_socials.py"),
                "--text-file",
                str(linkedin_path),
                "--scheduled-date",
                scheduled_iso,
            ]
            run(social_cmd)

            campaign_name = f"YouTube: {title.strip()}"
            news_cmd = [
                sys.executable,
                str(Path(__file__).parent / "schedule_newsletter.py"),
                "--name",
                campaign_name,
                "--subject",
                subject.strip(),
                "--preheader",
                preheader.strip(),
                "--body-file",
                str(newsletter_path),
                "--send-at",
                scheduled_iso,
            ]
            run(news_cmd)

    print(f"Workdir: {workdir}")
    print(f"Final video: {video_out}")
    if cleaned_srt_path:
        print(f"Transcript (clean): {cleaned_srt_path}")
    if content_path:
        print(f"Content: {content_path}")


if __name__ == "__main__":
    main()

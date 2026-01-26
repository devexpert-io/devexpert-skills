#!/usr/bin/env python3
import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

from google import genai
from google.genai import types as genai_types
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from PIL import Image as PILImage

SCOPES = [
    "https://www.googleapis.com/auth/youtube.upload",
    "https://www.googleapis.com/auth/youtube",
    "https://www.googleapis.com/auth/youtube.force-ssl",
]

DEFAULT_CLIENT_SECRET_PATH = os.path.expanduser("~/.config/youtube-publish/client_secret.json")
DEFAULT_TOKEN_PATH = os.path.expanduser("~/.config/youtube-publish/token.json")
DEFAULT_OUTPUT_DIR = os.path.expanduser("~/Downloads/youtube-videos")

DEFAULT_TEXT_MODEL = "models/gemini-2.0-flash"
DEFAULT_IMAGE_MODEL = "models/gemini-3-pro-image-preview"

PROMPT_TEMPLATE = """Eres un experto en títulos y thumbnails para YouTube (audiencia técnica).\n\nReglas obligatorias:\n- Evita clickbait: no uses 'Fácil', 'Rápido', 'Secreto'.\n- Enfócate en ingeniería, arquitectura y resolver fricción de desarrolladores.\n- Usa español.\n- Genera exactamente 3 títulos.\n- Genera exactamente 3 ideas de thumbnails.\n\nReglas de thumbnails:\n- Estilo: dark mode, minimalista, luz cinematográfica (cyan/purple).\n- Debe aparecer un artefacto técnico (logo, snippet de código o nodos).\n- Usa el contexto de foto de Antonio: assets/antonio-1.png, assets/antonio-2.png, assets/antonio-3.png.\n- Cada thumbnail debe usar una foto distinta.\n- Texto en thumbnail: <= 4 palabras.\n\nDevuelve SOLO JSON con esta forma exacta:\n{{\n  \"titles\": [\"...\", \"...\", \"...\"],\n  \"thumbnails\": [\n    {{\"photo\": \"assets/antonio-1.png\", \"text\": \"...\", \"artifact\": \"...\", \"concept\": \"...\"}},\n    {{\"photo\": \"assets/antonio-2.png\", \"text\": \"...\", \"artifact\": \"...\", \"concept\": \"...\"}},\n    {{\"photo\": \"assets/antonio-3.png\", \"text\": \"...\", \"artifact\": \"...\", \"concept\": \"...\"}}\n  ]\n}}\n\nEntrada:\nTITULO ACTUAL: {title}\nDESCRIPCION:\n{description}\n"""


def get_authenticated_service(client_secret_path: str, token_path: str):
    creds = None
    token_file = Path(token_path)
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
            auth_url, _ = flow.authorization_url(
                access_type="offline",
                prompt="consent",
            )
            print("Open this URL in your browser, approve access, then paste the final URL:")
            print(auth_url)
            redirect_response = input("Paste full redirect URL: ").strip()
            flow.fetch_token(authorization_response=redirect_response)
            creds = flow.credentials
        token_file.parent.mkdir(parents=True, exist_ok=True)
        token_file.write_text(creds.to_json(), encoding="utf-8")

    return build("youtube", "v3", credentials=creds)


def parse_duration(value: str) -> int | None:
    if not value:
        return None
    if not value.startswith("P"):
        return None
    hours = minutes = seconds = 0
    time_part = value.split("T")[-1] if "T" in value else ""
    number = ""
    for ch in time_part:
        if ch.isdigit():
            number += ch
            continue
        if ch == "H":
            hours = int(number or 0)
        elif ch == "M":
            minutes = int(number or 0)
        elif ch == "S":
            seconds = int(number or 0)
        else:
            return None
        number = ""
    return hours * 3600 + minutes * 60 + seconds


def format_duration(value: int | None) -> str:
    if value is None:
        return "n/a"
    minutes, seconds = divmod(value, 60)
    hours, minutes = divmod(minutes, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:d}:{seconds:02d}"


def safe_slug(text: str) -> str:
    text = re.sub(r"[^a-zA-Z0-9\-\s]", "", text).strip().lower()
    text = re.sub(r"\s+", "-", text)
    return text or "video"


def get_api_key() -> str | None:
    # Prefer GOOGLE_API_KEY if present, otherwise fall back to GEMINI_API_KEY.
    return os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY")


def get_assets_dir() -> Path:
    # .../skills/youtube-publish/scripts -> .../skills/youtube-publish/assets
    return Path(__file__).resolve().parent.parent / "assets"


def parse_titles_and_thumbs_payload(payload: dict) -> tuple[list[str], list[dict]]:
    titles = payload.get("titles")
    thumbs = payload.get("thumbnails")
    if not isinstance(titles, list) or not all(isinstance(t, str) for t in titles):
        raise ValueError("Invalid payload: 'titles' must be a list of strings")
    if not isinstance(thumbs, list) or not all(isinstance(t, dict) for t in thumbs):
        raise ValueError("Invalid payload: 'thumbnails' must be a list of objects")
    return titles, thumbs


def word_count(text: str) -> int:
    return len([w for w in re.split(r"\s+", text.strip()) if w])


def normalize_thumb_text(text: str) -> str:
    # Keep it short and avoid obvious clickbait terms.
    cleaned = (text or "").strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    banned = {"facil", "fácil", "rapido", "rápido", "secreto"}
    words = [w for w in cleaned.split(" ") if w.lower() not in banned]
    return " ".join(words[:4]).strip()


def generate_ideas(
    client: genai.Client,
    model: str,
    title: str,
    description: str,
) -> dict:
    prompt = PROMPT_TEMPLATE.format(title=title, description=description)
    resp = client.models.generate_content(
        model=model,
        contents=prompt,
        config=genai_types.GenerateContentConfig(
            response_mime_type="application/json",
        ),
    )

    text = None
    parts = getattr(resp, "parts", None)
    if parts:
        for p in parts:
            if getattr(p, "text", None):
                text = p.text
                break
    if not text and getattr(resp, "candidates", None):
        for c in resp.candidates:
            content = getattr(c, "content", None)
            if content and getattr(content, "parts", None):
                for p in content.parts:
                    if getattr(p, "text", None):
                        text = p.text
                        break
            if text:
                break

    if not text:
        raise RuntimeError("No text returned from Gemini")

    try:
        payload = json.loads(text)
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Failed to parse Gemini JSON: {exc}") from exc

    return payload


def generate_thumbnail_image(
    client: genai.Client,
    model: str,
    input_photo_path: Path,
    prompt: str,
    output_path: Path,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    photo = PILImage.open(str(input_photo_path))

    last_error: Exception | None = None
    for attempt in range(2):
        try:
            resp = client.models.generate_content(
                model=model,
                contents=[photo, prompt],
                config=genai_types.GenerateContentConfig(
                    response_modalities=["TEXT", "IMAGE"],
                ),
            )

            parts = getattr(resp, "parts", None)
            if not parts and getattr(resp, "candidates", None):
                for candidate in resp.candidates:
                    content = getattr(candidate, "content", None)
                    if content and getattr(content, "parts", None):
                        parts = content.parts
                        break

            if not parts:
                raise RuntimeError("No response parts found in image model output")

            for part in parts:
                inline = getattr(part, "inline_data", None)
                if inline is None or getattr(inline, "data", None) is None:
                    continue
                image_data = inline.data
                if isinstance(image_data, str):
                    import base64

                    image_data = base64.b64decode(image_data)
                from io import BytesIO

                image = PILImage.open(BytesIO(image_data))
                if image.mode == "RGBA":
                    rgb_image = PILImage.new("RGB", image.size, (255, 255, 255))
                    rgb_image.paste(image, mask=image.split()[3])
                    rgb_image.save(str(output_path), "PNG")
                elif image.mode == "RGB":
                    image.save(str(output_path), "PNG")
                else:
                    image.convert("RGB").save(str(output_path), "PNG")
                return

            raise RuntimeError("No image was generated in the response")
        except Exception as exc:
            last_error = exc
            # Retry once for transient/empty responses.
            continue

    raise RuntimeError(f"Thumbnail generation failed after retries: {last_error}")


def write_text(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate titles and thumbnail ideas for recent videos")
    parser.add_argument("--limit", type=int, default=20, help="Number of recent videos to inspect")
    parser.add_argument("--min-seconds", type=int, default=120, help="Minimum duration in seconds")
    parser.add_argument(
        "--client-secret",
        default=DEFAULT_CLIENT_SECRET_PATH,
        help="OAuth client secret JSON",
    )
    parser.add_argument(
        "--token",
        default=DEFAULT_TOKEN_PATH,
        help="Token cache path",
    )
    parser.add_argument(
        "--out-dir",
        default=DEFAULT_OUTPUT_DIR,
        help="Output directory",
    )
    parser.add_argument("--skip-text", action="store_true", help="Skip title/thumbnail idea generation")
    parser.add_argument("--skip-images", action="store_true", help="Skip thumbnail image generation")
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Reuse existing ideas.json when present (and only generate what's missing)",
    )
    parser.add_argument(
        "--only-missing-images",
        action="store_true",
        help="Only generate thumb-*.png files that do not exist yet",
    )
    parser.add_argument("--text-model", default=DEFAULT_TEXT_MODEL, help="Gemini text model")
    parser.add_argument("--image-model", default=DEFAULT_IMAGE_MODEL, help="Gemini image model")
    parser.add_argument(
        "--http-timeout-ms",
        type=int,
        default=60_000,
        help="HTTP timeout for Gemini requests in milliseconds (default: 60000)",
    )
    parser.add_argument(
        "--http-retry-attempts",
        type=int,
        default=3,
        help="Gemini HTTP retry attempts (default: 3)",
    )
    args = parser.parse_args()

    if args.limit <= 0:
        print("--limit must be a positive number", file=sys.stderr)
        return 2
    if args.min_seconds < 0:
        print("--min-seconds must be >= 0", file=sys.stderr)
        return 2

    if not Path(args.client_secret).exists():
        print(f"Missing client secret: {args.client_secret}", file=sys.stderr)
        return 1

    out_dir = Path(os.path.expanduser(args.out_dir))
    out_dir.mkdir(parents=True, exist_ok=True)

    api_key = get_api_key()
    if not api_key:
        print("Missing GEMINI_API_KEY/GOOGLE_API_KEY in environment (needed for title/thumbnail generation).", file=sys.stderr)
        return 1
    if args.http_timeout_ms <= 0:
        print("--http-timeout-ms must be > 0", file=sys.stderr)
        return 2
    if args.http_retry_attempts < 0:
        print("--http-retry-attempts must be >= 0", file=sys.stderr)
        return 2
    ai_client = genai.Client(
        api_key=api_key,
        http_options=genai_types.HttpOptions(
            timeout=args.http_timeout_ms,
            retry_options=genai_types.HttpRetryOptions(
                attempts=args.http_retry_attempts,
                initial_delay=0.5,
                max_delay=6.0,
                exp_base=2.0,
                jitter=0.2,
                http_status_codes=[429, 500, 502, 503, 504],
            ),
        ),
    )

    youtube = get_authenticated_service(args.client_secret, args.token)

    channel_resp = youtube.channels().list(part="contentDetails", mine=True).execute()
    channel_items = channel_resp.get("items", [])
    if not channel_items:
        print("No channel found for the authenticated user.", file=sys.stderr)
        return 1

    uploads_id = (
        channel_items[0]
        .get("contentDetails", {})
        .get("relatedPlaylists", {})
        .get("uploads")
    )
    if not uploads_id:
        print("Could not resolve uploads playlist id.", file=sys.stderr)
        return 1

    playlist_resp = youtube.playlistItems().list(
        part="snippet,contentDetails",
        playlistId=uploads_id,
        maxResults=args.limit,
    ).execute()

    playlist_items = playlist_resp.get("items", [])
    video_ids = [
        item.get("contentDetails", {}).get("videoId")
        for item in playlist_items
        if item.get("contentDetails", {}).get("videoId")
    ]

    details_by_id: dict[str, dict] = {}
    if video_ids:
        details_resp = youtube.videos().list(
            part="snippet,contentDetails,status",
            id=",".join(video_ids),
        ).execute()
        for item in details_resp.get("items", []):
            if "id" in item:
                details_by_id[item["id"]] = item

    processed = 0
    skipped = 0

    assets_dir = get_assets_dir()
    photo_map = {
        "assets/antonio-1.png": assets_dir / "antonio-1.png",
        "assets/antonio-2.png": assets_dir / "antonio-2.png",
        "assets/antonio-3.png": assets_dir / "antonio-3.png",
    }

    for item in playlist_items:
        video_id = item.get("contentDetails", {}).get("videoId")
        if not video_id:
            continue
        details = details_by_id.get(video_id, {})
        snippet = details.get("snippet", {})
        content_details = details.get("contentDetails", {})

        duration_raw = content_details.get("duration")
        duration_seconds = parse_duration(duration_raw) if duration_raw else None
        if duration_seconds is None or duration_seconds < args.min_seconds:
            skipped += 1
            continue

        title = snippet.get("title") or item.get("snippet", {}).get("title") or ""
        description = snippet.get("description") or ""
        published_at = snippet.get("publishedAt") or item.get("snippet", {}).get("publishedAt") or ""

        date_prefix = ""
        if published_at:
            try:
                dt = datetime.fromisoformat(published_at.replace("Z", "+00:00"))
                date_prefix = dt.strftime("%Y%m%d")
            except ValueError:
                date_prefix = ""

        slug = safe_slug(title)[:60]
        folder_name = f"{date_prefix}_{slug}_{video_id}" if date_prefix else f"{slug}_{video_id}"
        video_dir = out_dir / folder_name
        video_dir.mkdir(parents=True, exist_ok=True)

        write_text(video_dir / "title.txt", title)
        write_text(video_dir / "description.txt", description)

        meta = {
            "video_id": video_id,
            "title": title,
            "published_at": published_at,
            "duration": format_duration(duration_seconds),
            "duration_seconds": duration_seconds,
            "url": f"https://www.youtube.com/watch?v={video_id}",
        }
        (video_dir / "meta.json").write_text(
            json.dumps(meta, indent=2, ensure_ascii=False),
            encoding="utf-8",
        )

        ideas_path = video_dir / "ideas.json"
        payload = None

        if args.resume and ideas_path.exists():
            try:
                payload = json.loads(ideas_path.read_text(encoding="utf-8"))
            except Exception as exc:
                write_text(video_dir / "error.txt", f"Failed to read ideas.json: {exc}\n")
                payload = None

        if payload is None and not args.skip_text:
            try:
                payload = generate_ideas(
                    ai_client,
                    model=args.text_model,
                    title=title,
                    description=description,
                )
            except Exception as exc:
                write_text(video_dir / "error.txt", f"Failed to generate ideas: {exc}\n")
                processed += 1
                continue

            ideas_path.write_text(
                json.dumps(payload, indent=2, ensure_ascii=False),
                encoding="utf-8",
            )

        if payload is None and args.skip_text and ideas_path.exists():
            try:
                payload = json.loads(ideas_path.read_text(encoding="utf-8"))
            except Exception:
                payload = None

        if payload is not None:
            try:
                titles, thumbnails = parse_titles_and_thumbs_payload(payload)
                titles_text = "\n".join([f"{idx + 1}. {t}" for idx, t in enumerate(titles)])
                write_text(video_dir / "titles.txt", titles_text)

                lines = []
                for idx, thumb in enumerate(thumbnails, start=1):
                    photo = str(thumb.get("photo", "") or "")
                    text = normalize_thumb_text(str(thumb.get("text", "") or ""))
                    artifact = str(thumb.get("artifact", "") or "")
                    concept = str(thumb.get("concept", "") or "")
                    lines.append(f"{idx}. {text} | {photo} | {artifact} | {concept}")
                write_text(video_dir / "thumbnails.txt", "\n".join(lines))
            except Exception as exc:
                write_text(video_dir / "error.txt", f"Invalid ideas payload: {exc}\n")

        if not args.skip_images:
            # If we skipped text generation, still generate 3 images based on a fallback prompt.
            if payload is None:
                payload = {
                    "thumbnails": [
                        {"photo": "assets/antonio-1.png", "text": "Arquitectura IA", "artifact": "diagram", "concept": "technical nodes/diagram"},
                        {"photo": "assets/antonio-2.png", "text": "MCP Toolkit", "artifact": "docker+mcp", "concept": "docker + MCP icons"},
                        {"photo": "assets/antonio-3.png", "text": "Dev Workflow", "artifact": "code", "concept": "code snippet + terminal"},
                    ]
                }

            thumbs = payload.get("thumbnails") or []
            for idx, thumb in enumerate(thumbs, start=1):
                out_path = video_dir / f"thumb-{idx}.png"
                if args.only_missing_images and out_path.exists():
                    continue

                photo_key = str(thumb.get("photo", "") or "")
                input_photo = photo_map.get(photo_key)
                if input_photo is None:
                    # Try to map by basename.
                    basename = Path(photo_key).name
                    input_photo = next(
                        (p for k, p in photo_map.items() if Path(k).name == basename),
                        None,
                    )
                if input_photo is None or not input_photo.exists():
                    write_text(
                        video_dir / "error.txt",
                        f"Missing input photo for thumbnail {idx}: {photo_key}\n",
                    )
                    continue

                thumb_text = normalize_thumb_text(str(thumb.get("text", "") or ""))
                if word_count(thumb_text) > 4:
                    thumb_text = " ".join(thumb_text.split(" ")[:4]).strip()

                artifact = str(thumb.get("artifact", "") or "")
                concept = str(thumb.get("concept", "") or "")

                image_prompt = (
                    "Create a YouTube thumbnail (16:9). "
                    "Use the provided photo as Antonio's portrait (keep identity, face sharp, no distortions). "
                    "Background: dark mode gradient cyan/purple, cinematic lighting, minimalist. "
                    f"Include a technical artifact: {artifact}. "
                    f"Concept: {concept}. "
                    f'Add large bold text (<=4 words): \"{thumb_text}\". '
                    "High contrast, clean typography, no extra text, no watermark."
                )

                write_text(video_dir / f"thumb-{idx}.prompt.txt", image_prompt)
                try:
                    generate_thumbnail_image(
                        ai_client,
                        model=args.image_model,
                        input_photo_path=input_photo,
                        prompt=image_prompt,
                        output_path=out_path,
                    )
                except Exception as exc:
                    write_text(video_dir / "error.txt", f"Failed to generate thumb-{idx}: {exc}\n")
                    continue

        processed += 1

    print(
        f"Processed: {processed} | Skipped (<{args.min_seconds}s): {skipped} | Output: {out_dir}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

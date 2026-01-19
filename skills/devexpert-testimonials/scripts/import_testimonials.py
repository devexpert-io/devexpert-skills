#!/usr/bin/env python3
"""Import testimonials, process images, and optionally update AI Expert section."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import re
import sys
import unicodedata
from pathlib import Path

try:
    import cv2  # type: ignore
except Exception as exc:  # pragma: no cover - runtime dependency
    cv2 = None
    _cv2_import_error = exc
else:
    _cv2_import_error = None

DEFAULT_TESTIMONIALS_JSON = "src/data/testimonials.json"
DEFAULT_IMAGES_DIR = "src/assets/testimonials"
DEFAULT_AI_ASTRO = "src/pages/cursos/expert/ai.astro"

AI_TITLE_PATTERNS = (
    "ai expert",
    "ai-expert",
    "ia expert",
    "ia-expert",
)


class SkillError(Exception):
    pass


def _log(msg: str) -> None:
    print(msg)


def _warn(msg: str) -> None:
    print(f"[warn] {msg}", file=sys.stderr)


def slugify(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = ascii_text.lower()
    ascii_text = re.sub(r"[^a-z0-9]+", "-", ascii_text).strip("-")
    return ascii_text or "item"


def normalize_title_for_match(title: str) -> str:
    return re.sub(r"\s+", " ", title.strip().lower())


def is_ai_expert(title: str) -> bool:
    normalized = normalize_title_for_match(title)
    return any(pat in normalized for pat in AI_TITLE_PATTERNS)


def parse_date(raw: str) -> str:
    raw = raw.strip()
    if not raw:
        return ""
    candidates = [
        "%d/%m/%Y %H:%M:%S",
        "%d/%m/%Y %H:%M",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
    ]
    for fmt in candidates:
        try:
            parsed = dt.datetime.strptime(raw, fmt)
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            continue
    return raw


def autoparagraph(text: str) -> str:
    text = text.replace("\r\n", "\n").strip()
    if not text:
        return text
    if "\n" in text:
        # Normalize to double newlines between paragraphs
        parts = [p.strip() for p in text.split("\n") if p.strip()]
        return "\n\n".join(parts)
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", text) if s.strip()]
    if len(sentences) <= 1:
        return text
    return "\n\n".join(sentences)


def parse_rows(raw_text: str) -> list[list[str]]:
    lines = [line for line in raw_text.splitlines() if line.strip()]
    if not lines:
        return []

    delimiter = "\t" if any("\t" in line for line in lines) else None
    if delimiter:
        reader = csv.reader(lines, delimiter=delimiter)
        return [row for row in reader]

    # Fallback: split on 2+ spaces or pipes
    rows: list[list[str]] = []
    for line in lines:
        if "|" in line:
            row = [part.strip() for part in line.split("|")]
        else:
            row = [part.strip() for part in re.split(r"\s{2,}", line)]
        rows.append(row)
    return rows


def load_testimonials(path: Path) -> list[dict]:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def save_testimonials(path: Path, data: list[dict]) -> None:
    with path.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def next_ids(existing: list[dict], count: int) -> list[str]:
    numeric = [int(item["id"]) for item in existing if str(item.get("id", "")).isdigit()]
    start = max(numeric) + 1 if numeric else 1
    return [str(start + idx) for idx in range(count)]


def read_ai_ids(ai_path: Path) -> list[str]:
    text = ai_path.read_text(encoding="utf-8")
    match = re.search(r"testimonialIds=\{\[(.*?)\]\}", text, re.S)
    if not match:
        raise SkillError("No se encontro testimonialIds en ai.astro")
    raw = match.group(1)
    return re.findall(r"\"(\d+)\"", raw)


def write_ai_ids(ai_path: Path, ids: list[str]) -> None:
    text = ai_path.read_text(encoding="utf-8")
    new_list = ", ".join(f"\"{id_}\"" for id_ in ids)
    new_text = re.sub(
        r"testimonialIds=\{\[(.*?)\]\}",
        f"testimonialIds={{[{new_list}]}}",
        text,
        flags=re.S,
    )
    ai_path.write_text(new_text, encoding="utf-8")


def build_image_filename(name: str, title: str) -> str:
    name_slug = slugify(name)
    title_slug = slugify(title) if title.strip() else ""
    if title_slug:
        return f"{name_slug}-{title_slug}.jpg"
    return f"{name_slug}.jpg"


def ensure_face_crop(
    image_path: Path,
    output_path: Path,
    size: int = 400,
    overwrite: bool = False,
) -> bool:
    if not image_path.exists():
        _warn(f"Imagen no encontrada: {image_path}")
        return False
    if output_path.exists() and not overwrite:
        _warn(f"Imagen ya existe (omite): {output_path}")
        return True

    if cv2 is None:
        raise SkillError(
            "opencv-python no esta instalado. Ejecuta: python -m pip install -r scripts/requirements.txt"
        )

    image = cv2.imread(str(image_path))
    if image is None:
        _warn(f"No se pudo leer la imagen: {image_path}")
        return False

    height, width = image.shape[:2]
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    cascade = cv2.CascadeClassifier(
        str(Path(cv2.data.haarcascades) / "haarcascade_frontalface_default.xml")
    )
    faces = cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(60, 60))

    if len(faces) > 0:
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        cx = x + w / 2
        cy = y + h / 2
        side = int(max(w, h) * 2.2)
        side = min(side, width, height)
        x1 = int(cx - side / 2)
        y1 = int(cy - side / 2)
        x2 = x1 + side
        y2 = y1 + side
        if x1 < 0:
            x2 -= x1
            x1 = 0
        if y1 < 0:
            y2 -= y1
            y1 = 0
        if x2 > width:
            x1 -= x2 - width
            x2 = width
        if y2 > height:
            y1 -= y2 - height
            y2 = height
        x1 = max(0, x1)
        y1 = max(0, y1)
        crop = image[y1:y2, x1:x2]
    else:
        side = min(width, height)
        x1 = (width - side) // 2
        y1 = (height - side) // 2
        crop = image[y1 : y1 + side, x1 : x1 + side]

    resized = cv2.resize(crop, (size, size), interpolation=cv2.INTER_AREA)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(output_path), resized)
    return True


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        help="Ruta de fichero con testimonios (si no, usa stdin)",
    )
    parser.add_argument(
        "--testimonials-json",
        default=DEFAULT_TESTIMONIALS_JSON,
        help="Ruta a testimonials.json",
    )
    parser.add_argument(
        "--images-dir",
        default=DEFAULT_IMAGES_DIR,
        help="Directorio destino para imagenes",
    )
    parser.add_argument(
        "--ai-astro",
        default=DEFAULT_AI_ASTRO,
        help="Ruta al archivo ai.astro",
    )
    parser.add_argument(
        "--image-size",
        type=int,
        default=400,
        help="Tamano cuadrado en pixeles",
    )
    parser.add_argument(
        "--overwrite-images",
        action="store_true",
        help="Sobrescribir imagenes si existen",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="No escribe cambios",
    )
    parser.add_argument(
        "--ai-ids",
        help="Lista de ids para ai.astro (comma-separated)",
    )
    parser.add_argument(
        "--ai-auto",
        action="store_true",
        help="Anadir automaticamente nuevos IDs AI Expert a ai.astro",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    input_text: str

    if args.input:
        input_text = Path(args.input).read_text(encoding="utf-8")
    else:
        input_text = sys.stdin.read()

    rows = parse_rows(input_text)
    if not rows:
        _warn("No se encontraron filas de testimonios.")
        return 1

    testimonials_path = Path(args.testimonials_json)
    images_dir = Path(args.images_dir)
    ai_path = Path(args.ai_astro)

    testimonials = load_testimonials(testimonials_path)

    new_rows: list[dict] = []
    new_image_paths: list[str] = []
    existing_keys = {
        (str(item.get("name", "")).strip().lower(), str(item.get("date", "")).strip())
        for item in testimonials
    }
    for row in rows:
        while len(row) < 7:
            row.append("")
        raw_date, name, position, title, text, rating, image_path = row[:7]
        name = name.strip()
        if not name:
            _warn(f"Fila sin nombre, se omite: {row}")
            continue
        entry: dict = {
            "name": name,
            "text": autoparagraph(text),
            "rating": int(rating) if str(rating).strip().isdigit() else 5,
            "date": parse_date(raw_date),
        }
        title = title.strip()
        if title:
            entry["title"] = title
        if position.strip():
            entry["position"] = position.strip()
        image_path = image_path.strip()
        if image_path:
            image_source = Path(image_path)
            if image_source.exists():
                filename = build_image_filename(name, entry.get("title", ""))
                entry["imageFilename"] = filename
            else:
                _warn(f"Ruta de imagen no valida: {image_path}")
        key = (entry["name"].strip().lower(), entry.get("date", ""))
        if key in existing_keys:
            _warn(
                f"Posible duplicado por nombre/fecha: {entry['name']} {entry.get('date', '')}"
            )
        new_rows.append(entry)
        new_image_paths.append(image_path)

    if not new_rows:
        _warn("No hay testimonios validos para agregar.")
        return 1

    new_ids = next_ids(testimonials, len(new_rows))
    for entry, id_ in zip(new_rows, new_ids):
        entry["id"] = id_

    _log(f"Se agregaran {len(new_rows)} testimonios.")

    if not args.dry_run:
        testimonials.extend(new_rows)
        save_testimonials(testimonials_path, testimonials)
    else:
        _log("Dry run: no se escribio testimonials.json")

    # Process images
    for entry, image_path in zip(new_rows, new_image_paths):
        image_filename = entry.get("imageFilename")
        if not image_filename or not image_path:
            continue
        image_source = Path(image_path)
        if not image_source.exists():
            continue
        output_path = images_dir / image_filename
        if args.dry_run:
            _log(f"Dry run: recorte imagen {image_source} -> {output_path}")
            continue
        ensure_face_crop(
            image_source,
            output_path,
            size=args.image_size,
            overwrite=args.overwrite_images,
        )

    # AI Expert suggestions
    ai_new = [entry for entry in new_rows if is_ai_expert(entry.get("title", ""))]
    if ai_new:
        try:
            current_ids = read_ai_ids(ai_path)
        except SkillError as exc:
            _warn(str(exc))
            current_ids = []

        by_id = {item["id"]: item for item in testimonials + new_rows}
        if current_ids:
            _log("\nAI Expert actuales:")
            for id_ in current_ids:
                name = by_id.get(id_, {}).get("name", "?")
                _log(f"  - {id_}: {name}")

        _log("\nNuevos AI Expert:")
        for entry in ai_new:
            _log(f"  - {entry['id']}: {entry['name']}")
        suggested = current_ids + [
            entry["id"] for entry in ai_new if entry["id"] not in current_ids
        ]
        if suggested:
            _log(f"\nSugerencia (actual + nuevos): {', '.join(suggested)}")

        if args.ai_ids:
            selected = [item.strip() for item in args.ai_ids.split(",") if item.strip()]
            if not args.dry_run:
                write_ai_ids(ai_path, selected)
                _log("ai.astro actualizado con ids indicados.")
            else:
                _log("Dry run: no se actualizo ai.astro")
        elif args.ai_auto:
            if suggested:
                if not args.dry_run:
                    write_ai_ids(ai_path, suggested)
                    _log("ai.astro actualizado automaticamente con ids nuevos.")
                else:
                    _log("Dry run: no se actualizo ai.astro")
        elif sys.stdin.isatty():
            prompt = "\nEscribe los ids para ai.astro (comma-separated) o Enter para omitir: "
            try:
                response = input(prompt)
            except EOFError:
                response = ""
            if response.strip():
                selected = [item.strip() for item in response.split(",") if item.strip()]
                if not args.dry_run:
                    write_ai_ids(ai_path, selected)
                    _log("ai.astro actualizado con ids seleccionados.")
                else:
                    _log("Dry run: no se actualizo ai.astro")
        else:
            _log("\nSugerencia: pasa --ai-ids \"id1,id2\" para actualizar ai.astro.")

    _log("\nResumen:")
    for entry in new_rows:
        _log(f"  - {entry['id']}: {entry['name']} ({entry.get('title', '')})")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

#!/usr/bin/env python3
"""Sync testimonials from Google Sheets using gog CLI."""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import subprocess
import sys
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

import import_testimonials as importer

DEFAULT_SHEET_RANGE = "A1:Z"
DEFAULT_MARK_VALUE = "x"
SKILLS_CONFIG_PATH = os.path.expanduser("~/.config/skills/config.json")


class SyncError(Exception):
    pass


@dataclass
class GogConfig:
    account: str | None = None


@dataclass
class SheetInfo:
    sheet_title: str


@dataclass
class ColumnMap:
    date: int | None
    name: int
    company: int | None
    position: int | None
    title: int | None
    text: int
    rating: int | None
    image: int | None
    published: int


def _log(msg: str) -> None:
    print(msg)


def _warn(msg: str) -> None:
    print(f"[warn] {msg}", file=sys.stderr)


def run_gog(args: list[str], config: GogConfig, json_output: bool = False) -> str:
    cmd = ["gog"]
    if json_output:
        cmd.append("--json")
    if config.account:
        cmd.extend(["--account", config.account])
    cmd.extend(args)
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise SyncError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def load_skills_config() -> dict[str, Any]:
    try:
        with open(SKILLS_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def normalize_header(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text)
    ascii_text = normalized.encode("ascii", "ignore").decode("ascii")
    ascii_text = re.sub(r"\s+", " ", ascii_text.strip().lower())
    return ascii_text


def resolve_sheet_title(sheet_id: str, gid: int | None, config: GogConfig) -> SheetInfo:
    raw = run_gog(["sheets", "metadata", sheet_id], config, json_output=True)
    payload = json.loads(raw)
    sheets = payload.get("sheets", [])
    if not sheets:
        raise SyncError("No se encontraron pestañas en el Sheet.")
    if gid is not None:
        for sheet in sheets:
            props = sheet.get("properties", {})
            if props.get("sheetId") == gid:
                title = props.get("title")
                if title:
                    return SheetInfo(sheet_title=title)
    if len(sheets) == 1:
        title = sheets[0].get("properties", {}).get("title")
        if title:
            return SheetInfo(sheet_title=title)
    raise SyncError("No se pudo resolver el nombre de la pestaña.")


def resolve_columns(headers: list[str]) -> ColumnMap:
    aliases = {
        "marca temporal": "date",
        "timestamp": "date",
        "fecha": "date",
        "nombre completo": "name",
        "nombre": "name",
        "empresa": "company",
        "puesto en la empresa": "position",
        "formacion devexpert": "title",
        "formacion": "title",
        "curso": "title",
        "testimonio": "text",
        "puntuacion": "rating",
        "puntuacion (1-5)": "rating",
        "foto": "image",
        "imagen": "image",
        "publicado en web": "published",
        "publicado": "published",
    }

    matches: dict[str, int] = {}
    for idx, header in enumerate(headers):
        normalized = normalize_header(header)
        for alias, canonical in aliases.items():
            if alias in normalized:
                matches.setdefault(canonical, idx)
                break

    if "name" not in matches or "text" not in matches or "published" not in matches:
        missing = [key for key in ("name", "text", "published") if key not in matches]
        raise SyncError(f"Faltan columnas requeridas: {', '.join(missing)}")

    return ColumnMap(
        date=matches.get("date"),
        name=matches["name"],
        company=matches.get("company"),
        position=matches.get("position"),
        title=matches.get("title"),
        text=matches["text"],
        rating=matches.get("rating"),
        image=matches.get("image"),
        published=matches["published"],
    )


def column_letter(index: int) -> str:
    result = ""
    idx = index + 1
    while idx:
        idx, rem = divmod(idx - 1, 26)
        result = chr(65 + rem) + result
    return result


def extract_drive_id(url: str) -> str | None:
    patterns = [
        r"/d/([a-zA-Z0-9_-]+)",
        r"id=([a-zA-Z0-9_-]+)",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def drive_file_extension(file_id: str, config: GogConfig) -> str:
    raw = run_gog(["drive", "get", file_id], config, json_output=True)
    payload = json.loads(raw)
    name = payload.get("name", "")
    if name and "." in name:
        return Path(name).suffix
    mime = payload.get("mimeType", "")
    if mime.startswith("image/"):
        return f".{mime.split('/', 1)[1]}"
    return ""


def download_drive_file(
    file_id: str,
    target_dir: Path,
    base_name: str,
    config: GogConfig,
) -> Path:
    target_dir.mkdir(parents=True, exist_ok=True)
    ext = drive_file_extension(file_id, config)
    filename = f"{base_name}{ext or '.jpg'}"
    output_path = target_dir / filename
    run_gog([
        "drive",
        "download",
        file_id,
        "--out",
        str(output_path),
    ], config)
    return output_path


def get_cell(row: list[str], index: int | None) -> str:
    if index is None or index >= len(row):
        return ""
    return row[index].strip()


def build_rows(
    values: list[list[str]],
    columns: ColumnMap,
    existing_keys: set[tuple[str, str]],
    downloads_dir: Path,
    config: GogConfig,
    download_images: bool,
) -> tuple[list[list[str]], list[int], list[int]]:
    rows: list[list[str]] = []
    rows_to_mark: list[int] = []
    rows_skipped_duplicates: list[int] = []

    for row_index, row in enumerate(values[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue
        published = get_cell(row, columns.published)
        if published:
            continue

        name = get_cell(row, columns.name)
        text = get_cell(row, columns.text)
        if not name or not text:
            _warn(f"Fila {row_index} sin nombre o texto, se omite.")
            continue

        raw_date = get_cell(row, columns.date)
        normalized_date = importer.parse_date(raw_date) if raw_date else ""
        key = (name.strip().lower(), normalized_date)
        if key in existing_keys:
            rows_to_mark.append(row_index)
            rows_skipped_duplicates.append(row_index)
            _warn(f"Fila {row_index} ya existe en testimonials.json, se marca igual.")
            continue

        title = get_cell(row, columns.title)
        rating = get_cell(row, columns.rating)
        company = get_cell(row, columns.company)
        position = get_cell(row, columns.position)
        display_position = position or company

        image_url = get_cell(row, columns.image)
        image_path = ""
        if image_url and download_images:
            if image_url.startswith("http") and "drive.google" in image_url:
                file_id = extract_drive_id(image_url)
                if file_id:
                    base_name = importer.slugify(name) + "-" + file_id[:6]
                    try:
                        image_path = str(
                            download_drive_file(file_id, downloads_dir, base_name, config)
                        )
                    except SyncError as exc:
                        _warn(f"No se pudo descargar imagen fila {row_index}: {exc}")
                else:
                    _warn(f"URL de Drive invalida fila {row_index}: {image_url}")
            elif Path(image_url).exists():
                image_path = image_url
            else:
                _warn(f"Imagen no soportada fila {row_index}: {image_url}")

        rows.append([
            raw_date,
            name,
            display_position,
            title,
            text,
            rating,
            image_path,
        ])
        rows_to_mark.append(row_index)

    return rows, rows_to_mark, rows_skipped_duplicates


def write_tsv(path: Path, rows: Iterable[list[str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle, delimiter="\t")
        for row in rows:
            writer.writerow(row)


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sheet-id")
    parser.add_argument("--gid", type=int)
    parser.add_argument("--sheet-name", help="Nombre de la pestaña si quieres forzarlo")
    parser.add_argument("--range", dest="sheet_range", default=DEFAULT_SHEET_RANGE)
    parser.add_argument("--account", help="Cuenta para gog (email)")
    parser.add_argument("--downloads-dir", default="tmp/testimonials-sync")
    parser.add_argument("--mark-value", default=DEFAULT_MARK_VALUE)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--skip-mark", action="store_true")

    parser.add_argument(
        "--testimonials-json",
        default=importer.DEFAULT_TESTIMONIALS_JSON,
    )
    parser.add_argument(
        "--images-dir",
        default=importer.DEFAULT_IMAGES_DIR,
    )
    parser.add_argument(
        "--ai-astro",
        default=importer.DEFAULT_AI_ASTRO,
    )
    parser.add_argument(
        "--image-size",
        type=int,
        default=400,
    )
    parser.add_argument(
        "--overwrite-images",
        action="store_true",
    )
    parser.add_argument(
        "--ai-auto",
        action="store_true",
        help="Actualizar ai.astro automaticamente con nuevos IDs AI Expert",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)
    skills_cfg = load_skills_config().get("devexpert_testimonials", {})
    account = args.account or skills_cfg.get("account") or os.getenv("GOG_ACCOUNT")
    sheet_id = args.sheet_id or skills_cfg.get("sheet_id")
    gid = args.gid if args.gid is not None else skills_cfg.get("gid")
    config = GogConfig(account=account)

    if not sheet_id:
        raise SyncError(
            "Missing sheet id (pass --sheet-id or set devexpert_testimonials.sheet_id in ~/.config/skills/config.json)"
        )

    if args.sheet_name:
        sheet_title = args.sheet_name
    else:
        sheet_info = resolve_sheet_title(sheet_id, gid, config)
        sheet_title = sheet_info.sheet_title

    sheet_range = f"'{sheet_title}'!{args.sheet_range}"
    raw = run_gog([
        "sheets",
        "get",
        sheet_id,
        sheet_range,
    ], config, json_output=True)
    payload = json.loads(raw)
    values = payload.get("values", [])
    if not values:
        _warn("No hay filas en el Sheet.")
        return 1

    headers = values[0]
    columns = resolve_columns(headers)

    testimonials_path = Path(args.testimonials_json)
    testimonials = importer.load_testimonials(testimonials_path)
    existing_keys = {
        (str(item.get("name", "")).strip().lower(), str(item.get("date", "")).strip())
        for item in testimonials
    }

    downloads_dir = Path(args.downloads_dir)
    rows, rows_to_mark, duplicate_rows = build_rows(
        values, columns, existing_keys, downloads_dir, config, not args.dry_run
    )

    if not rows and not duplicate_rows:
        _log("No hay testimonios nuevos para importar.")
        return 0

    if rows:
        _log(f"Se importaran {len(rows)} testimonios nuevos.")
        downloads_dir.mkdir(parents=True, exist_ok=True)
        tsv_path = downloads_dir / "pending-testimonials.tsv"
        write_tsv(tsv_path, rows)

        import_args = [
            "--input",
            str(tsv_path),
            "--testimonials-json",
            args.testimonials_json,
            "--images-dir",
            args.images_dir,
            "--ai-astro",
            args.ai_astro,
            "--image-size",
            str(args.image_size),
        ]
        if args.overwrite_images:
            import_args.append("--overwrite-images")
        if args.dry_run:
            import_args.append("--dry-run")
        if args.ai_auto:
            import_args.append("--ai-auto")

        result = importer.main(import_args)
        if result != 0:
            _warn("Fallo al importar testimonios. No se actualiza el Sheet.")
            return result
    else:
        _log("No hay filas nuevas para importar, solo duplicados sin marcar.")

    if args.dry_run or args.skip_mark:
        _log("Dry run o --skip-mark: no se actualiza el Sheet.")
        return 0

    published_col_letter = column_letter(columns.published)
    for row_number in rows_to_mark:
        cell_range = f"'{sheet_title}'!{published_col_letter}{row_number}"
        run_gog(
            ["sheets", "update", sheet_id, cell_range, args.mark_value],
            config,
        )

    _log(f"Marcadas {len(rows_to_mark)} filas como publicadas.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

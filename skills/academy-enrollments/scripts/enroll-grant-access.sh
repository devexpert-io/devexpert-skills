#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Add a "Dar acceso" row to the "Integración N8N - Zapier" Google Sheet.

Usage:
  enroll-grant-access.sh --email <email> --nombre <nombre> --apellidos <apellidos> (--formacion <name> | --producto <id>) [--precio <precio>] [--account <google-account>] [--sheet-id <id>]

Examples:
  enroll-grant-access.sh --email a@b.com --nombre "Ana" --apellidos "Pérez" --formacion "AI Expert" --precio 997
  enroll-grant-access.sh --email a@b.com --nombre "Ana" --apellidos "Pérez" --producto ai-expert

Notes:
- This does not call LearnWorlds directly. It appends a row to the sheet that Zapier/n8n processes.
- Product IDs are typically the training name lowercased with dashes (e.g. "AI Expert" -> "ai-expert").
- If omitted, --account and --sheet-id can be loaded from ~/.config/skills/config.json under academy_enrollments.
EOF
}

slugify() {
  # Basic, predictable slugifier for course names.
  # - lowercases
  # - replaces common accented vowels
  # - replaces non-alnum with dashes
  # - collapses multiple dashes
  local s="$1"
  s=$(printf "%s" "$s" | tr '[:upper:]' '[:lower:]')
  s=$(printf "%s" "$s" | sed -E \
    -e 's/[áàäâ]/a/g' \
    -e 's/[éèëê]/e/g' \
    -e 's/[íìïî]/i/g' \
    -e 's/[óòöô]/o/g' \
    -e 's/[úùüû]/u/g' \
    -e 's/ñ/n/g')
  s=$(printf "%s" "$s" | sed -E 's/[^a-z0-9]+/-/g; s/^-+//; s/-+$//; s/-+/-/g')
  printf "%s" "$s"
}

EMAIL=""
NOMBRE=""
APELLIDOS=""
FORMACION=""
PRODUCTO=""
PRECIO=""
ACCOUNT=""
SHEET_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --email) EMAIL="$2"; shift 2;;
    --nombre) NOMBRE="$2"; shift 2;;
    --apellidos) APELLIDOS="$2"; shift 2;;
    --formacion) FORMACION="$2"; shift 2;;
    --producto) PRODUCTO="$2"; shift 2;;
    --precio) PRECIO="$2"; shift 2;;
    --account) ACCOUNT="$2"; shift 2;;
    --sheet-id) SHEET_ID="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

skills_config_value() {
  local key="$1"
  python3 - "$key" <<'PY'
import json
import os
import sys

path = os.path.expanduser("~/.config/skills/config.json")
key = sys.argv[1]
try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception:
    sys.exit(0)

val = data
for part in key.split("."):
    if isinstance(val, dict) and part in val:
        val = val[part]
    else:
        sys.exit(0)

if isinstance(val, (str, int, float)):
    print(val)
PY
}

if [[ -z "$ACCOUNT" ]]; then
  ACCOUNT="$(skills_config_value academy_enrollments.account)"
fi
if [[ -z "$SHEET_ID" ]]; then
  SHEET_ID="$(skills_config_value academy_enrollments.sheet_id)"
fi

if [[ -z "$EMAIL" || -z "$NOMBRE" || -z "$APELLIDOS" ]]; then
  echo "Missing required args" >&2
  usage
  exit 2
fi

if [[ ! "$EMAIL" =~ ^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$ ]]; then
  echo "Invalid email: $EMAIL" >&2
  exit 2
fi

if [[ -z "$PRODUCTO" ]]; then
  if [[ -z "$FORMACION" ]]; then
    echo "Missing course identifier: provide --formacion or --producto" >&2
    usage
    exit 2
  fi
  PRODUCTO=$(slugify "$FORMACION")
fi

if [[ -n "$PRECIO" && ! "$PRECIO" =~ ^[0-9]+$ ]]; then
  echo "Invalid precio (expected numeric): $PRECIO" >&2
  exit 2
fi

RANGE="'Dar acceso'!A:E"

# Require account + sheet id after config/flags resolution
if [[ -z "$ACCOUNT" || -z "$SHEET_ID" ]]; then
  echo "Missing --account or --sheet-id (or set academy_enrollments.account / academy_enrollments.sheet_id in ~/.config/skills/config.json)" >&2
  exit 2
fi

# Order must match header: email, nombre, apellidos, producto, precio
row="$EMAIL|$NOMBRE|$APELLIDOS|$PRODUCTO|$PRECIO"
# gog sheets append expects: comma-separated rows, pipe-separated cells
# so we send a single row string.
gog sheets append "$SHEET_ID" "$RANGE" "$row" --account "$ACCOUNT" --json >/dev/null

echo "OK: appended access row for $EMAIL ($PRODUCTO)"

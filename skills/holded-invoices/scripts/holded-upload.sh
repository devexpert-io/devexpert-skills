#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'EOF'
Upload a PDF invoice to Holded inbox via n8n webhook.

The n8n workflow expects the PDF as the raw request body with:
- Content-Type: application/pdf
- Header "email": holded inbox email
- Header "nombre": base filename (without extension)

Usage:
  holded-upload.sh --pdf /path/to/file.pdf --email <holdedbox> --nombre <filename-or-base> [--webhook <url>]

Example:
  holded-upload.sh --pdf invoice.pdf --email empresa@holdedbox.com --nombre google-2026-01.pdf
EOF
}

PDF=""
EMAIL=""
NOMBRE=""
WEBHOOK=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --pdf) PDF="$2"; shift 2;;
    --email) EMAIL="$2"; shift 2;;
    --nombre) NOMBRE="$2"; shift 2;;
    --webhook) WEBHOOK="$2"; shift 2;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 2;;
  esac
done

if [[ -z "$PDF" || -z "$EMAIL" || -z "$NOMBRE" ]]; then
  usage
  exit 2
fi

if [[ ! -f "$PDF" ]]; then
  echo "PDF not found: $PDF" >&2
  exit 1
fi

# n8n workflow historically expects the base name without extension.
BASE_NAME="$NOMBRE"
BASE_NAME="${BASE_NAME%.pdf}"
BASE_NAME="${BASE_NAME%.PDF}"

if [[ -z "$WEBHOOK" ]]; then
  WEBHOOK=$(python3 - <<'PY'
import json
import os
path = os.path.expanduser("~/.config/skills/config.json")
try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception:
    data = {}
print((data.get("holded_invoices") or {}).get("webhook", "") or "")
PY
  )
fi

if [[ -z "$WEBHOOK" ]]; then
  echo "Missing webhook (pass --webhook or set holded_invoices.webhook in ~/.config/skills/config.json)" >&2
  exit 2
fi

curl -sS -X POST "$WEBHOOK" \
  -H "Content-Type: application/pdf" \
  -H "email: $EMAIL" \
  -H "nombre: $BASE_NAME" \
  --data-binary "@$PDF" \
  >/dev/null

echo "OK: uploaded $BASE_NAME to $EMAIL"

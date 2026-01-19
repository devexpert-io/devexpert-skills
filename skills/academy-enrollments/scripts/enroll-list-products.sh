#!/usr/bin/env bash
set -euo pipefail

ACCOUNT=""
SHEET_ID=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --account) ACCOUNT="$2"; shift 2;;
    --sheet-id) SHEET_ID="$2"; shift 2;;
    -h|--help)
      echo "List known product IDs from the 'Dar acceso' tab (unique, sorted)."
      echo "Usage: enroll-list-products.sh [--account <google-account>] [--sheet-id <id>]"
      exit 0
      ;;
    *) echo "Unknown arg: $1" >&2; exit 2;;
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

if [[ -z "$ACCOUNT" || -z "$SHEET_ID" ]]; then
  echo "Missing --account or --sheet-id (or set academy_enrollments.account / academy_enrollments.sheet_id in ~/.config/skills/config.json)" >&2
  exit 2
fi

RANGE="'Dar acceso'!D2:D"

gog sheets get "$SHEET_ID" "$RANGE" --account "$ACCOUNT" --plain \
  | tr -d '\r' \
  | awk 'NF{print}' \
  | sort \
  | uniq

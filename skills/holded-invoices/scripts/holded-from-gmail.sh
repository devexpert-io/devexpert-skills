#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
  cat <<'EOF'
Process an invoice email (Gmail) and upload the first PDF attachment to Holded.

Usage:
  holded-from-gmail.sh --account <gmail-account> --message-id <id> --type empresa|autonomo [--yes]

Notes:
- Downloads the first PDF attachment found in the message.
- Extracts vendor + year/month (best effort) to suggest filename.
- If --yes is not set, prints the suggested filename and exits.
EOF
}

ACCOUNT=""
MESSAGE_ID=""
TYPE=""
YES="false"
WEBHOOK=""
EMAIL_EMPRESA=""
EMAIL_AUTONOMO=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --account) ACCOUNT="$2"; shift 2;;
    --message-id) MESSAGE_ID="$2"; shift 2;;
    --type) TYPE="$2"; shift 2;;
    --email-empresa) EMAIL_EMPRESA="$2"; shift 2;;
    --email-autonomo) EMAIL_AUTONOMO="$2"; shift 2;;
    --webhook) WEBHOOK="$2"; shift 2;;
    --yes) YES="true"; shift 1;;
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

if [[ -z "$ACCOUNT" || -z "$MESSAGE_ID" || -z "$TYPE" ]]; then
  usage
  exit 2
fi

if [[ "$TYPE" != "empresa" && "$TYPE" != "autonomo" ]]; then
  echo "Invalid --type (use empresa|autonomo)" >&2
  exit 2
fi

if [[ -z "$EMAIL_EMPRESA" ]]; then
  EMAIL_EMPRESA="$(skills_config_value holded_invoices.company_email)"
fi
if [[ -z "$EMAIL_AUTONOMO" ]]; then
  EMAIL_AUTONOMO="$(skills_config_value holded_invoices.freelancer_email)"
fi

DEST_EMAIL=""
if [[ "$TYPE" == "empresa" ]]; then
  DEST_EMAIL="$EMAIL_EMPRESA"
else
  DEST_EMAIL="$EMAIL_AUTONOMO"
fi

if [[ -z "$DEST_EMAIL" ]]; then
  echo "Missing destination email (set holded_invoices.company_email/freelancer_email in ~/.config/skills/config.json or pass --email-empresa/--email-autonomo)" >&2
  exit 2
fi

TMPDIR=$(mktemp -d)
cleanup() { rm -rf "$TMPDIR"; }
trap cleanup EXIT

# Get message JSON and find first PDF attachmentId
MSG_JSON=$(gog gmail get "$MESSAGE_ID" --account "$ACCOUNT" --format full --json)
ATTACHMENT_ID=$(printf "%s" "$MSG_JSON" | node -e "
let d='';
process.stdin.on('data',c=>d+=c);
process.stdin.on('end',()=>{
  const msg=JSON.parse(d);
  function walk(parts,out=[]){
    if(!parts) return out;
    for(const p of parts){
      out.push(p);
      if(p.parts) walk(p.parts,out);
    }
    return out;
  }
  const parts=walk(msg.message?.payload?.parts||[]);
  const pdf=parts.find(p=>p.filename && p.filename.toLowerCase().endsWith('.pdf') && p.body && p.body.attachmentId);
  if(!pdf){process.stdout.write(''); return;}
  process.stdout.write(pdf.body.attachmentId);
});
")

if [[ -z "$ATTACHMENT_ID" ]]; then
  echo "No PDF attachment found in message $MESSAGE_ID" >&2
  exit 1
fi

OUT_PDF="$TMPDIR/invoice.pdf"
gog gmail attachment "$MESSAGE_ID" "$ATTACHMENT_ID" --account "$ACCOUNT" --out "$OUT_PDF" >/dev/null

META=$(node "$SCRIPT_DIR/invoice-extract.js" --pdf "$OUT_PDF")
VENDOR_SLUG=$(M="$META" node -e "const j=JSON.parse(process.env.M);process.stdout.write(j.vendorSlug||'empresa');")
YEAR=$(M="$META" node -e "const j=JSON.parse(process.env.M);process.stdout.write(j.year||'');")
MONTH=$(M="$META" node -e "const j=JSON.parse(process.env.M);process.stdout.write(j.month||'');")

if [[ -z "$YEAR" || -z "$MONTH" ]]; then
  echo "Could not infer invoice date (year/month)." >&2
  echo "META: $META" >&2
  exit 1
fi

FILENAME="${VENDOR_SLUG}-${YEAR}-${MONTH}.pdf"

echo "Suggested:"
echo "- email: $DEST_EMAIL"
echo "- nombre: $FILENAME"
echo "- pdf: $OUT_PDF"

echo ""

echo "META: $META"

if [[ "$YES" != "true" ]]; then
  echo "(dry-run) Pass --yes to upload."
  exit 0
fi

"$SCRIPT_DIR/holded-upload.sh" --pdf "$OUT_PDF" --email "$DEST_EMAIL" --nombre "$FILENAME" ${WEBHOOK:+--webhook "$WEBHOOK"}

# Archive thread after successful upload
THREAD_ID=$(printf "%s" "$MSG_JSON" | node -e "let d='';process.stdin.on('data',c=>d+=c);process.stdin.on('end',()=>{const j=JSON.parse(d);process.stdout.write(j.message?.threadId||j.threadId||'');});")
if [[ -n "$THREAD_ID" ]]; then
  gog gmail thread modify "$THREAD_ID" --account "$ACCOUNT" --remove INBOX,UNREAD >/dev/null || true
  echo "OK: archived thread $THREAD_ID"
fi

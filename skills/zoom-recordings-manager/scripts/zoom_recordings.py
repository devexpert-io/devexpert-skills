#!/usr/bin/env python3
"""Zoom recordings manager (list/download/delete).

Requires env:
- ZOOM_ACCOUNT_ID
- ZOOM_CLIENT_ID
- ZOOM_CLIENT_SECRET
"""

import argparse
import base64
import json
import os
import sys
import unicodedata
import urllib.parse
import urllib.request
from datetime import datetime, timedelta

API_BASE = "https://api.zoom.us/v2"
TOKEN_URL = "https://zoom.us/oauth/token"


def die(msg):
    print(msg, file=sys.stderr)
    sys.exit(1)


def get_env(name):
    val = os.environ.get(name)
    if not val:
        die(f"Missing env {name}")
    return val


def get_token():
    account_id = get_env("ZOOM_ACCOUNT_ID")
    client_id = get_env("ZOOM_CLIENT_ID")
    client_secret = get_env("ZOOM_CLIENT_SECRET")

    basic = base64.b64encode(f"{client_id}:{client_secret}".encode()).decode()
    params = urllib.parse.urlencode({
        "grant_type": "account_credentials",
        "account_id": account_id,
    })
    req = urllib.request.Request(
        f"{TOKEN_URL}?{params}",
        method="POST",
        headers={"Authorization": f"Basic {basic}"},
    )
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
    return data.get("access_token")


def api_request(method, path, token, params=None, body=None):
    url = f"{API_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, method=method, headers=headers, data=data)
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode()


def list_recordings_page(path, token, params):
    out = api_request("GET", path, token, params=params)
    return json.loads(out)


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d")


def format_date(d):
    return d.strftime("%Y-%m-%d")




def iter_ranges(from_date, to_date, max_days=30):
    start = parse_date(from_date)
    end = parse_date(to_date)
    cur = start
    while cur <= end:
        chunk_end = min(cur + timedelta(days=max_days - 1), end)
        yield format_date(cur), format_date(chunk_end)
        cur = chunk_end + timedelta(days=1)


def sanitize_filename(name):
    name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    name = name.replace("/", "-").replace(":", "-")
    name = " ".join(name.split())
    out = []
    for ch in name:
        if ch.isalnum() or ch in (" ", "-", "_", ".", "(", ")"):
            out.append(ch)
        else:
            out.append("_")
    return "".join(out).strip()


def match_filter(text, pattern):
    parts = [p.strip() for p in pattern.split("|") if p.strip()]
    return any(p in text for p in parts)


def download_url(url, out_path, token):
    if "access_token=" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}access_token={token}"
    urllib.request.urlretrieve(url, out_path)


def capture_list_json(args, token):
    account_id = get_env("ZOOM_ACCOUNT_ID")
    if args.user:
        path = f"/users/{urllib.parse.quote(args.user, safe='')}/recordings"
    else:
        path = f"/accounts/{account_id}/recordings"

    if not args.from_date or not args.to_date:
        die("list requires --from and --to (YYYY-MM-DD)")

    all_meetings = []
    for start, end in iter_ranges(args.from_date, args.to_date, max_days=30):
        params = {"from": start, "to": end, "page_size": args.page_size}
        if args.page_number:
            params["page_number"] = args.page_number

        page = list_recordings_page(path, token, params)
        all_meetings.extend(page.get("meetings", []))
        next_token = page.get("next_page_token") or ""
        while next_token:
            params = {"from": start, "to": end, "page_size": args.page_size, "next_page_token": next_token}
            page = list_recordings_page(path, token, params)
            all_meetings.extend(page.get("meetings", []))
            next_token = page.get("next_page_token") or ""

    dedup = {}
    for m in all_meetings:
        dedup[m.get("uuid")] = m
    out = {"from": args.from_date, "to": args.to_date, "total_records": len(dedup), "meetings": list(dedup.values())}
    return json.dumps(out)


def list_recordings(args, token):
    out = capture_list_json(args, token)
    print(out)


def download_recording(args, token):
    if not args.url or not args.out:
        die("download requires --url and --out")
    download_url(args.url, args.out, token)
    print(f"Downloaded to {args.out}")


def delete_recording(args, token):
    if not args.meeting_id:
        die("delete requires --meeting-id (or meeting UUID)")
    meeting_id = urllib.parse.quote(args.meeting_id, safe='')
    params = {"action": args.action}
    if args.recording_id:
        path = f"/meetings/{meeting_id}/recordings/{urllib.parse.quote(args.recording_id, safe='')}"
    else:
        path = f"/meetings/{meeting_id}/recordings"
    out = api_request("DELETE", path, token, params=params)
    print(out)


def download_mp4_filtered(args, token):
    if not args.from_date or not args.to_date or not args.out_dir:
        die("download-mp4 requires --from, --to, --out-dir")
    match = args.match or "DIRECTO LUNES|Q&A JUEVES"

    class TempArgs:
        pass
    t = TempArgs()
    t.from_date = args.from_date
    t.to_date = args.to_date
    t.page_size = args.page_size
    t.page_number = args.page_number
    t.user = args.user

    data = json.loads(capture_list_json(t, token))
    meetings = data.get("meetings", [])
    os.makedirs(args.out_dir, exist_ok=True)

    for m in meetings:
        topic = m.get("topic", "")
        if not topic:
            continue
        if not match_filter(topic, match):
            continue
        start = m.get("start_time", "")
        date_part = start[:10] if start else "unknown-date"
        base = sanitize_filename(f"{topic} - {date_part}")
        files = m.get("recording_files", [])
        for f in files:
            if f.get("file_type") != "MP4":
                continue
            url = f.get("download_url")
            if not url:
                continue
            out_path = os.path.join(args.out_dir, f"{base}.mp4")
            download_url(url, out_path, token)
            print(f"Downloaded: {out_path}")




def main():
    parser = argparse.ArgumentParser(description="Zoom recordings manager")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_list = sub.add_parser("list", help="List recordings")
    p_list.add_argument("--from", dest="from_date")
    p_list.add_argument("--to", dest="to_date")
    p_list.add_argument("--page-size", type=int, default=300)
    p_list.add_argument("--page-number", type=int, default=1)
    p_list.add_argument("--user", help="Zoom user id/email (optional)")

    p_dl = sub.add_parser("download", help="Download recording file")
    p_dl.add_argument("--url", required=True)
    p_dl.add_argument("--out", required=True)

    p_del = sub.add_parser("delete", help="Delete recordings")
    p_del.add_argument("--meeting-id", required=True)
    p_del.add_argument("--recording-id")
    p_del.add_argument("--action", choices=["trash", "delete"], default="trash")

    p_dlf = sub.add_parser("download-mp4", help="Download MP4 for matched meetings")
    p_dlf.add_argument("--from", dest="from_date")
    p_dlf.add_argument("--to", dest="to_date")
    p_dlf.add_argument("--user")
    p_dlf.add_argument("--match", help="Pipe-separated substring match (default DIRECTO LUNES|Q&A JUEVES)")
    p_dlf.add_argument("--out-dir", required=True)
    p_dlf.add_argument("--page-size", type=int, default=300)
    p_dlf.add_argument("--page-number", type=int, default=1)


    args = parser.parse_args()
    token = get_token()
    if not token:
        die("Failed to obtain access token")

    if args.cmd == "list":
        list_recordings(args, token)
    elif args.cmd == "download":
        download_recording(args, token)
    elif args.cmd == "delete":
        delete_recording(args, token)
    elif args.cmd == "download-mp4":
        download_mp4_filtered(args, token)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""Zoom meetings lister (scheduled/upcoming) with join_url.

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
import urllib.parse
import urllib.request
from datetime import datetime

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


def api_request(method, path, token, params=None):
    url = f"{API_BASE}{path}"
    if params:
        url += "?" + urllib.parse.urlencode(params)
    headers = {"Authorization": f"Bearer {token}"}
    req = urllib.request.Request(url, method=method, headers=headers)
    with urllib.request.urlopen(req) as resp:
        return resp.read().decode()


def parse_date(s):
    return datetime.strptime(s, "%Y-%m-%d")


def parse_zoom_time(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def list_meetings(args, token):
    user = args.user or "me"
    path = f"/users/{urllib.parse.quote(user, safe='')}/meetings"
    params = {
        "type": args.type,
        "page_size": args.page_size,
    }

    from_dt = parse_date(args.from_date) if args.from_date else None
    to_dt = parse_date(args.to_date) if args.to_date else None

    meetings = []
    while True:
        payload = json.loads(api_request("GET", path, token, params=params))
        meetings.extend(payload.get("meetings", []))
        next_token = payload.get("next_page_token") or ""
        if not next_token:
            break
        params = {**params, "next_page_token": next_token}

    if from_dt or to_dt:
        filtered = []
        for m in meetings:
            start_time = parse_zoom_time(m.get("start_time"))
            if not start_time:
                continue
            start_date = start_time.date()
            if from_dt and start_date < from_dt.date():
                continue
            if to_dt and start_date > to_dt.date():
                continue
            filtered.append(m)
        meetings = filtered

    for m in meetings[: args.max]:
        start = m.get("start_time", "")
        topic = m.get("topic", "")
        join_url = m.get("join_url", "")
        print(f"{start} | {topic} | {join_url}")


def main():
    parser = argparse.ArgumentParser(description="Zoom meetings lister")
    parser.add_argument("--user", help="Zoom user id/email (default: me)")
    parser.add_argument("--type", default="upcoming", choices=["scheduled", "live", "upcoming"])
    parser.add_argument("--from", dest="from_date", help="Filter by date (YYYY-MM-DD)")
    parser.add_argument("--to", dest="to_date", help="Filter by date (YYYY-MM-DD)")
    parser.add_argument("--page-size", type=int, default=300)
    parser.add_argument("--max", type=int, default=200)

    args = parser.parse_args()
    token = get_token()
    if not token:
        die("Failed to obtain access token")

    list_meetings(args, token)


if __name__ == "__main__":
    main()

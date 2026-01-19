#!/usr/bin/env python3
import json
import os
import urllib.parse
import urllib.request
from typing import Optional
DEFAULT_TIMEOUT_SECONDS = 20.0


def get_token(env_key: str = "SLACK_USER_TOKEN") -> str:
    token = os.getenv(env_key, "").strip()
    if not token:
        raise SystemExit(f"Missing {env_key}. Set it in your environment.")
    return token


def get_timeout() -> float:
    return DEFAULT_TIMEOUT_SECONDS


def api_call(method: str, token: str, params=None, timeout: Optional[float] = None) -> dict:
    url = f"https://slack.com/api/{method}"
    data = urllib.parse.urlencode(params or {}).encode("utf-8")
    req = urllib.request.Request(url, data=data)
    req.add_header("Authorization", f"Bearer {token}")
    req.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(req, timeout=timeout or get_timeout()) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as exc:
        raise SystemExit(f"Slack API request failed: {exc}")

    try:
        payload = json.loads(raw)
    except Exception:
        raise SystemExit("Slack API returned invalid JSON")

    if not payload.get("ok"):
        err = payload.get("error") or "unknown_error"
        raise SystemExit(f"Slack API error: {err}")
    return payload


def paginate(method: str, token: str, params: dict, list_key: str) -> list:
    items = []
    cursor = None
    while True:
        if cursor:
            params = {**params, "cursor": cursor}
        payload = api_call(method, token, params)
        items.extend(payload.get(list_key, []))
        cursor = payload.get("response_metadata", {}).get("next_cursor")
        if not cursor:
            break
    return items


def user_display_name(user: dict) -> str:
    profile = user.get("profile", {})
    return (
        profile.get("display_name")
        or profile.get("real_name")
        or user.get("real_name")
        or user.get("name")
        or user.get("id")
        or ""
    )


def resolve_user_name(token: str, user_id: str, cache: dict) -> str:
    if not user_id:
        return ""
    if user_id in cache:
        return cache[user_id]
    payload = api_call("users.info", token, {"user": user_id})
    name = user_display_name(payload.get("user", {}))
    cache[user_id] = name
    return name


def conversation_display_name(conv: dict, token: str, user_cache: dict) -> str:
    if conv.get("is_im"):
        user_id = conv.get("user")
        name = resolve_user_name(token, user_id, user_cache) if user_id else "(DM)"
        return f"@{name}" if name else "(DM)"
    if conv.get("is_mpim"):
        name = conv.get("name") or "(group DM)"
        return f"{name}"
    if conv.get("is_group"):
        name = conv.get("name") or "(private)"
        return f"🔒 {name}"
    name = conv.get("name") or "(channel)"
    return f"#{name}"

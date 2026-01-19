#!/usr/bin/env python3
import json
import os
import urllib.request

STATE_PATH = os.path.expanduser("~/.cache/whatsapp-evo/inbox-state.json")
DEFAULT_TIMEOUT_SECONDS = 20.0
SKILLS_CONFIG_PATH = os.path.expanduser("~/.config/skills/config.json")


def get_env(key: str) -> str:
    return os.getenv(key, "").strip()


def load_skills_config() -> dict:
    try:
        with open(SKILLS_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def get_config_value(key: str) -> str:
    data = load_skills_config().get("whatsapp_evo", {})
    value = data.get(key, "")
    return value.strip() if isinstance(value, str) else ""


def get_state_path(env_key: str = "WHATSAPP_EVO_STATE_PATH") -> str:
    return get_env(env_key) or STATE_PATH


def load_state(path: str) -> dict:
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def save_state(path: str, data: dict) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_token(env_key: str = "EVOLUTION_API_TOKEN") -> str:
    token = get_env(env_key)
    if not token:
        raise SystemExit(f"Missing {env_key}. Set it in your environment.")
    return token


def get_base_url(env_key: str = "EVOLUTION_API_URL") -> str:
    url = get_env(env_key) or get_config_value("api_url")
    if not url:
        raise SystemExit(f"Missing {env_key}. Set it in your environment or config.")
    return url.rstrip("/")


def get_instance(env_key: str = "EVOLUTION_INSTANCE") -> str:
    instance = get_env(env_key) or get_env("EVOLUTION_INSTANCE_NAME") or get_config_value("instance")
    if not instance:
        raise SystemExit(f"Missing {env_key}. Set it in your environment or config.")
    return instance


def get_timeout(env_key: str = "WHATSAPP_EVO_TIMEOUT", fallback_key: str = "EVOLUTION_API_TIMEOUT") -> float:
    value = get_env(env_key) or get_env(fallback_key)
    if not value:
        return DEFAULT_TIMEOUT_SECONDS
    try:
        return float(value)
    except ValueError:
        return DEFAULT_TIMEOUT_SECONDS


def api_call(method: str, base_url: str, path: str, token: str, payload=None) -> dict:
    url = f"{base_url}{path}"
    data = None
    headers = {
        "apikey": token,
        "Content-Type": "application/json",
    }

    if payload is not None:
        data = json.dumps(payload).encode("utf-8")

    req = urllib.request.Request(url, data=data, method=method.upper())
    for key, value in headers.items():
        req.add_header(key, value)

    try:
        with urllib.request.urlopen(req, timeout=get_timeout()) as resp:
            raw = resp.read().decode("utf-8")
    except Exception as exc:
        raise SystemExit(f"Evolution API request failed: {exc}")

    if not raw:
        return {}

    try:
        return json.loads(raw)
    except Exception:
        raise SystemExit("Evolution API returned invalid JSON")


def extract_text_from_message(message: dict) -> str:
    if not isinstance(message, dict):
        return ""
    if "conversation" in message:
        return str(message.get("conversation", ""))
    if "extendedTextMessage" in message:
        return str(message.get("extendedTextMessage", {}).get("text", ""))
    if "imageMessage" in message:
        return str(message.get("imageMessage", {}).get("caption", ""))
    if "videoMessage" in message:
        return str(message.get("videoMessage", {}).get("caption", ""))
    if "documentMessage" in message:
        return str(message.get("documentMessage", {}).get("caption", ""))
    if "message" in message:
        return extract_text_from_message(message.get("message", {}))
    return ""


def pick_first(items, keys):
    for key in keys:
        if key in items and items[key] is not None:
            return items[key]
    return None


def normalize_number_from_jid(remote_jid: str) -> str:
    if not remote_jid:
        return ""
    if remote_jid.endswith("@s.whatsapp.net"):
        return remote_jid.split("@", 1)[0]
    return remote_jid

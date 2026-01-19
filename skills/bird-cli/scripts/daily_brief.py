#!/usr/bin/env python3
"""Daily brief for X using bird CLI."""

import argparse
import json
import os
import subprocess
import urllib.parse
import tempfile
from datetime import datetime
from typing import List, Dict, Any

DATE_FORMAT = "%a %b %d %H:%M:%S %z %Y"
SKILLS_CONFIG_PATH = os.path.expanduser("~/.config/skills/config.json")


def run_bird(args: List[str]) -> str:
    proc = subprocess.run(["bird", *args], text=True, capture_output=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or proc.stdout.strip() or "bird command failed")
    return proc.stdout


def run_bird_json(args: List[str]) -> Any:
    with tempfile.NamedTemporaryFile(mode="w+", encoding="utf-8", suffix=".json", delete=False) as tmp:
        tmp_path = tmp.name
        proc = subprocess.run(["bird", *args], stdout=tmp, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or "bird command failed")
    with open(tmp_path, "r", encoding="utf-8") as f:
        raw = f.read()
    os.unlink(tmp_path)
    return json.loads(raw)


def base_args(opts: argparse.Namespace) -> List[str]:
    args: List[str] = []
    if opts.auth_token:
        args += ["--auth-token", opts.auth_token]
    if opts.ct0:
        args += ["--ct0", opts.ct0]
    if opts.cookie_source:
        args += ["--cookie-source", opts.cookie_source]
    if opts.chrome_profile:
        args += ["--chrome-profile", opts.chrome_profile]
    if opts.firefox_profile:
        args += ["--firefox-profile", opts.firefox_profile]
    return args


def load_skills_config() -> Dict[str, Any]:
    try:
        with open(SKILLS_CONFIG_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, dict) else {}
    except FileNotFoundError:
        return {}
    except json.JSONDecodeError:
        return {}


def parse_date(value: str | None) -> datetime:
    if not value:
        return datetime.min
    try:
        return datetime.strptime(value, DATE_FORMAT)
    except ValueError:
        return datetime.min


def is_retweet(text: str) -> bool:
    return text.strip().startswith("RT @")


def engagement_score(item: Dict[str, Any]) -> int:
    likes = int(item.get("likeCount", 0) or 0)
    rts = int(item.get("retweetCount", 0) or 0)
    replies = int(item.get("replyCount", 0) or 0)
    return likes + (2 * rts) + (3 * replies)


def pick_top(items: List[Dict[str, Any]], limit: int) -> List[Dict[str, Any]]:
    return items[:limit] if limit and limit > 0 else items


def format_url(author: str | None, tid: str | None) -> str:
    if not author or not tid:
        return ""
    return f"https://x.com/{author}/status/{tid}"


def headline_key(headline: str) -> str:
    words = [w for w in headline.lower().replace("'", "").split() if w.isalnum()]
    if not words:
        return ""
    return " ".join(words[:6])


def search_url(headline: str) -> str:
    if not headline:
        return ""
    return f"https://x.com/search?q={urllib.parse.quote(headline)}"


def extract_headline(item: Dict[str, Any]) -> str:
    return item.get("headline") or item.get("title") or item.get("name") or ""


def load_news(opts: argparse.Namespace) -> List[Dict[str, Any]]:
    args = base_args(opts) + [
        "news",
        "--ai-only",
        "--with-tweets",
        "--tweets-per-item",
        str(opts.news_tweets),
        "--json",
    ]
    return run_bird_json(args)


def load_home(opts: argparse.Namespace) -> List[Dict[str, Any]]:
    args = base_args(opts) + ["home", "-n", str(opts.home_count), "--json"]
    if opts.following_only:
        args.insert(len(args) - 1, "--following")
    return run_bird_json(args)


def build_search_query(headline: str, min_faves: int) -> str:
    safe = headline.replace("\"", " ").replace("“", " ").replace("”", " ").strip()
    return f"{safe} min_faves:{min_faves} -filter:retweets"


def search_news_links(opts: argparse.Namespace, headline: str, limit: int) -> List[str]:
    if not headline:
        return []
    query = build_search_query(headline, opts.news_search_min_faves)
    args = base_args(opts) + ["search", query, "-n", str(limit), "--json"]
    results = run_bird_json(args)
    links = []
    for t in results[:limit]:
        author = (t.get("author", {}) or {}).get("username")
        url = format_url(author, t.get("id"))
        if url:
            links.append(url)
    return links


def main() -> int:
    parser = argparse.ArgumentParser(description="Daily brief using bird CLI")
    parser.add_argument("--cookie-source", default="chrome")
    parser.add_argument("--chrome-profile")
    parser.add_argument("--firefox-profile")
    parser.add_argument("--auth-token")
    parser.add_argument("--ct0")
    parser.add_argument("--home-count", type=int, default=120)
    parser.add_argument("--news-count", type=int, default=5)
    parser.add_argument("--home-results", type=int, default=10)
    parser.add_argument("--news-tweets", type=int, default=3)
    parser.add_argument("--news-search-min-faves", type=int, default=10)
    parser.add_argument("--following-only", action="store_true", default=True)
    parser.add_argument("--allow-for-you", action="store_true")
    parser.add_argument("--json-out")
    parser.add_argument("--debug", action="store_true")
    opts = parser.parse_args()

    if opts.allow_for_you:
        opts.following_only = False

    config = load_skills_config().get("bird", {})
    if not opts.chrome_profile and not opts.firefox_profile and not opts.auth_token:
        opts.chrome_profile = config.get("chrome_profile")
        opts.firefox_profile = config.get("firefox_profile")

    news = load_news(opts)
    home = load_home(opts)

    news_items = []
    seen_news_keys = set()
    for item in news:
        headline = extract_headline(item)
        tweets = item.get("tweets", [])
        best_score = 0
        for t in tweets:
            score = engagement_score(t)
            if score > best_score:
                best_score = score
        key = headline_key(headline)
        if key and key in seen_news_keys:
            continue
        if key:
            seen_news_keys.add(key)
        category = item.get("category", "")
        if best_score == 0 and category.startswith("AI ·"):
            best_score = int(item.get("postCount", 0) or 0)
        search = search_url(headline)
        news_items.append({
            **item,
            "headline": headline,
            "searchUrl": search,
            "_score": best_score,
        })

    news_items.sort(key=lambda r: r.get("_score", 0), reverse=True)
    news_items = pick_top(news_items, opts.news_count)

    home_items = []
    for t in home:
        text = t.get("text", "")
        if not text:
            continue
        if is_retweet(text):
            continue
        score = engagement_score(t)
        home_items.append({
            "id": t.get("id"),
            "text": text.replace("\n", " "),
            "createdAt": t.get("createdAt"),
            "score": score,
            "relevance": score,
            "author": (t.get("author", {}) or {}).get("username"),
        })

    home_items.sort(key=lambda r: (r["relevance"], parse_date(r.get("createdAt"))), reverse=True)
    home_items = pick_top(home_items, opts.home_results)

    if opts.json_out:
        payload = {
            "news": news_items,
            "home": home_items,
        }
        os.makedirs(os.path.dirname(opts.json_out), exist_ok=True)
        with open(opts.json_out, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=2)

    print("== AI dev news ==\n")
    for item in news_items:
        headline = extract_headline(item)
        category = item.get("category")
        time_ago = item.get("timeAgo")
        topic_url = item.get("url") or ""
        print(f"- {headline} ({category}) {time_ago or ''}".rstrip())
        if topic_url:
            print(f"  topic: {topic_url}")
        search = item.get("searchUrl") or search_url(headline)
        if search:
            print(f"  search: {search}")
        tweet_links = []
        for t in item.get("tweets", [])[: opts.news_tweets]:
            author = (t.get("author", {}) or {}).get("username")
            url = format_url(author, t.get("id"))
            if url:
                tweet_links.append(url)
        if not tweet_links:
            tweet_links = search_news_links(opts, headline, opts.news_tweets)
        for url in tweet_links:
            print(f"  {url}")
        print()

    print("== Home candidates ==\n")
    for idx, item in enumerate(home_items, start=1):
        url = format_url(item.get("author"), item.get("id"))
        print(f"{idx}) {url}")
        print(f"   {item.get('text')[:220]}")
        print()

    if opts.debug:
        print(f"News items: {len(news_items)}")
        print(f"Home candidates: {len(home_items)}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())

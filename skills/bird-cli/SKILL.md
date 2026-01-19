---
name: bird-cli
description: Use the bird CLI to access X/Twitter accounts, including reading timelines/mentions and listing unanswered mentions by date. Trigger when asked to use bird for whoami, home/mentions, or to detect replies.
---

# Bird CLI

## Quick Start

- Prefer explicit cookie source and browser profile to avoid Safari auto-detection.
- If multiple accounts exist, pass `--chrome-profile` and `--username` explicitly.
- Defaults can be set in `~/.config/skills/config.json` under `bird` (`chrome_profile`, `username`).

## Task: List unanswered mentions (most recent first)

- Run `scripts/unanswered_mentions.py` with the target profile.
- If auto-detection fails, pass `--username`.
- The script checks `bird replies <tweet>` for a reply authored by the target username (heuristic).

Examples:

```bash
python scripts/unanswered_mentions.py --cookie-source chrome --chrome-profile "<Profile>" --json-out /tmp/bird-unanswered.json --numbered
```

```bash
python scripts/unanswered_mentions.py --cookie-source chrome --chrome-profile "<Profile>" --show-text --limit 10
```

Output format:

```
<createdAt> | @author | https://x.com/<author>/status/<id>
```

## Resources

- `scripts/unanswered_mentions.py`: lists unanswered mentions in descending date order.
- `scripts/daily_brief.py`: daily brief of AI/dev news + home candidates.

## Task: Daily brief (AI + dev)

Run:

```bash
python scripts/daily_brief.py
```

Defaults: AI news + Home following, prints 5 news items and 10 home candidates.

Optional flags:

```bash
python scripts/daily_brief.py --news-count 5 --home-results 10
python scripts/daily_brief.py --allow-for-you   # use For You instead of Following
python scripts/daily_brief.py --json-out /tmp/bird-daily.json
```
- `scripts/ignore_mentions.py`: mark mention IDs as ignored so they stop appearing.

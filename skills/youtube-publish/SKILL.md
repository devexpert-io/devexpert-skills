---
name: youtube-publish
description: "End-to-end YouTube publishing workflow using ordered scripts: prepare/concat video, upload draft, transcribe with Parakeet, generate copy+thumbnails with Gemini, update YouTube metadata, then schedule socials (Postiz) and newsletter (Listmonk) 15 minutes after publish."
---

# YouTube Publish (Scripted Flow)

Use scripts in order. No interactive pauses. The agent decides final values and passes them to scripts.

## One-time setup

1) OAuth Desktop credentials
- Enable YouTube Data API v3 in Google Cloud.
- Create OAuth client ID type "Desktop app".
- Save JSON to: `~/.config/youtube-publish/client_secret.json`.
  - If it is stored elsewhere, pass `--client-secret` explicitly and document the path in `AGENTS.md` or `CLAUDE.md`.

2) Python deps
- `python -m pip install google-api-python-client google-auth google-auth-oauthlib google-auth-httplib2 pyyaml`

3) Config
- Copy `config.example.yaml` to `~/.config/youtube-publish/config.yaml` and edit defaults.

4) Tools
- `pip install parakeet-mlx -U`
- Ensure `gemini` CLI is installed for headless text generation
- Ensure `postiz` and `listmonk` CLIs are in PATH

Auth note:
On first run, the script prints a URL. Open it, approve access, then paste the final redirect URL back into the terminal. Tokens are stored in:
`~/.config/youtube-publish/token.json`

## Behavior rules for the agent
- Do not ask for a title hint; derive it from the video stem.
- If the user provides a publish time (even relative like “next Tuesday 17h”), resolve to exact `YYYY-MM-DD HH:MM` using system time and pass `--publish-at` + `--timezone`.
- If no publish time is provided, ask: schedule date/time, or leave as private, or unlisted.
- Determine timezone from the system; if you cannot infer it, ask the user. Always pass `--timezone`.
- Generate thumbnails by default unless the user explicitly provides them.
- Upload a private draft before generating copy so the video URL can be used in newsletter/social text.
- In the newsletter include the video URL. In social posts, say “Link en el primer comentario.”
- Schedule social posts + newsletter 15 minutes after the YouTube publish time (if provided).

LinkedIn post style (YouTube videos only):
- 600–900 characters, 3–6 short paragraphs, 1–2 emojis
- 1 central idea, no digressions
- Final line: “Link en el primer comentario.”
- Close with a short question or CTA to comment
- No hashtags

Newsletter style:
- Long-form (220–320 words), conversational, same tone as DevExpert.
- Structure: greeting + context, 2–3 development paragraphs, “En el vídeo verás:” + 2–4 bullets, line with link, closing + CTA to comment, optional P.S.
- Vary the opening and pacing; avoid repetitive templates.

## Scripted flow (order)

1) Prepare video (move inputs + concat if needed)
`python scripts/prepare_video.py --videos /path/v1.mp4 [/path/v2.mp4 ...]`
- Output JSON with `workdir`, `video`, `slug`.

2) Upload draft (private) to get URL
`python scripts/upload_draft.py --video <video> --output-video-id <workdir>/video_id.txt --client-secret <path>`
- Write `video_id.txt` and create `video_url.txt` (by the agent from id).

3) Transcribe + clean
`python scripts/transcribe_parakeet.py --video <video> --out-dir <workdir>`
- Outputs `transcript.es.cleaned.srt`.

4) Generate copy (Gemini headless)
Use `gemini` CLI on the cleaned SRT. Generate:
- 3 titles
- 3 thumbnail ideas
- Description
- Chapters (MM:SS)
- LinkedIn post (rules above)
- Newsletter (rules above) including:
  - Asunto
  - Preheader
- Ensure LinkedIn has no hashtags.
- Save all into `<workdir>/content.md` (agent decides final versions).

5) Generate 3 thumbnails (Gemini image)
Always include Antonio’s photo context (all three):
- `assets/antonio-1.png`
- `assets/antonio-2.png`
- `assets/antonio-3.png`
Create 3 images into `<workdir>/thumb-1.png`, `thumb-2.png`, `thumb-3.png`.

6) Update YouTube (title/description/thumbnail/publish)
`python scripts/update_youtube.py --video-id <id> --title "..." --description-file <desc.txt> --thumbnail <thumb.png> --publish-at "YYYY-MM-DD HH:MM" --timezone <IANA> --client-secret <path>`
- If no publish time, omit `--publish-at` and set `--privacy-status private|unlisted`.

7) Schedule socials (Postiz)
`python scripts/schedule_socials.py --text-file <linkedin.txt> --scheduled-date <ISO8601+offset> --comment-url <video_url> --image <thumb.png>`
- Schedules to Postiz integrations configured in `~/.config/skills/config.json` (`postiz.groups.youtube_publish`).
- Use `x-es` by default for X unless the user explicitly asks for `x-en`.
- Posts include first comment with the video URL and attach the thumbnail.

8) Schedule newsletter (Listmonk)
`python scripts/schedule_newsletter.py --name "YouTube: <title>" --subject "..." --preheader "..." --body-file <newsletter.md> --send-at <ISO8601+offset>`
- List ID comes from `youtube_publish.listmonk_list_id` in `~/.config/skills/config.json` (or pass `--list-id`).

Note: If no publish time, skip steps 7–8 unless the user asks to schedule anyway.

## Assets
Antonio photo context:
- `assets/antonio-1.png`
- `assets/antonio-2.png`
- `assets/antonio-3.png`

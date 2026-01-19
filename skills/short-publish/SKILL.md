---
name: short-publish
description: End-to-end workflow for turning a local video into transcripts, burned subtitles, and scheduled multi-network posts via Postiz MCP tools. Use when given a video path and publication date/time to transcribe, create copy for LinkedIn/X/IG/YouTube, upload the subtitled MP4, and schedule the content with `postiz_mcp`.
---

# Short Publish

## Overview

This skill automates the complete "video → subtitles → Postiz" pipeline: run Whisper-based transcription, burn subtitles with the bundled Python script, turn the transcript into a multi-platform copy block, and program four social channels (YouTube, LinkedIn, X, Instagram) through the Postiz MCP integration.

## Inputs & Prerequisites

- **Arguments:**
  - `PATH` – absolute path to the source video (MOV/MP4/etc.).
  - `DATETIME` – publication date/time (accepts natural language like "tomorrow 09:00"). Use `date` to confirm the current timestamp if needed.
- **Tooling:** always use the MCP tools (`postiz-upload-file`, `postiz-create-post`) exposed by `postiz_mcp`. Never fall back to the Postiz CLI.
- **Script dependency:** `scripts/transcribe_burn.py` wraps Whisper, ffmpeg, and auto-gain. Requires Python 3.8+, ffmpeg, and `openai-whisper` installed for the user; no extra configuration is needed inside this skill.
- **Timezone:** default to Europe/Madrid. In winter assume UTC+01:00 (CET) when presenting final schedules if the `date` command does not provide the offset.

## Workflow

1. **Collect inputs**
   - Confirm the provided `PATH` exists; stop with a descriptive error if not.
   - Resolve `DATETIME` to an ISO timestamp. Use `date -j -f` or another deterministic macOS command when the input is natural language so Postiz receives an unambiguous value.

2. **Transcribe and burn subtitles**
   - Run the bundled helper: `python3 scripts/transcribe_burn.py "$PATH"`.
   - Outputs (all written next to the original video):
     - `<stem>.srt`, `<stem>.ass`, `<stem>.txt`, `<stem>_caption.txt`, `<stem>_subtitled.mp4`.
   - The `_subtitled.mp4` is the media you will upload; everything else is transient reference material. Remove the generated artifacts (srt/ass/txt/caption/mp4_subtitled/normalized wav) once they have been read and the upload succeeds—never delete the original video.

3. **Generate the social copy**
   - Read `<stem>.txt` for the full transcript.
   - Apply the exact copywriting prompt below to the transcript; do not improvise structure or tone beyond the template.

     ```
     Act as an expert LinkedIn copywriter building authority content.
     Transform the TRANSCRIPT into a case-study or practical-lesson post with this structure:
     1. Hook headline with a leading emoji.
     2. 2-3 sentence context introducing the situation.
     3. Structured core (use 1️⃣/2️⃣/3️⃣ or ✅ and bold keywords per line).
     4. Closing takeaway line.
     5. Optional P.S. only when the transcript mentions an offer/event.

     Style rules: short paragraphs (1-2 lines), intentional emoji usage, no invented facts, stay faithful to the transcript.
     ```

   - Reuse the single output block verbatim for LinkedIn, X, and Instagram, and as the YouTube description (light line breaks allowed). Craft a YouTube title ≤100 characters from the same content.

4. **Upload the subtitled video**
   - Use `postiz-upload-file` with the `_subtitled.mp4` path. Capture the returned public URL; Postiz expects this URL inside the `images` array for all channel posts.

5. **Schedule the four posts via `postiz-create-post`**
   - Integrations come from `~/.config/skills/config.json` under `postiz.groups.short_publish`.
   - Use `x-es` by default for X unless the user explicitly asks for `x-en`.
   - Payload guidelines:
     - `content`: the copy block described above.
     - `images`: `["<uploaded_mp4_url>"]` so Postiz attaches the video.
     - `scheduledDate`: resolved ISO timestamp based on `DATETIME`.
   - YouTube requires an explicit `title` and defaults to `type=public`; ensure the MCP call includes the generated title field.

6. **Report completion**
   - Confirm each scheduled post by echoing the returned IDs and their scheduled time in CET (UTC+01:00 during winter). Example: `YouTube cm... → 2025-01-11T10:00:00+01:00 (CET)`.

## Resources

- `scripts/transcribe_burn.py`: Whisper + ffmpeg pipeline used in Step 2. Copy-safe to reuse elsewhere but do not edit unless the video workflow changes. Running the script produces all intermediate assets and the burned MP4 referenced throughout the workflow.

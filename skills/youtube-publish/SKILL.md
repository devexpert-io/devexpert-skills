---
name: youtube-publish
description: "End-to-end YouTube publishing workflow using ordered scripts: prepare/concat video, upload draft, transcribe with Parakeet, generate copy+thumbnails with Gemini, update YouTube metadata, then schedule socials (Postiz) and newsletter (Listmonk) 15 minutes after publish."
---

# YouTube Publish (Scripted Flow - AI Expert Edition)

Use scripts in order. No interactive pauses. The agent decides final values and passes them to scripts.

## Behavior rules for the agent

- **Tone & Authority:** Strictly avoid clickbait terms ("Fácil", "Rápido", "Secreto"). Titles and copy must focus on engineering, architecture, and solving developer friction.
- **Title Derivation:** Do not ask for a title hint; derive it from the video stem and the technical density of the SRT.
- **Scheduling:** If the user provides a publish time, resolve to exact `YYYY-MM-DD HH:MM` using system time and pass `--publish-at` + `--timezone`. Always determine and pass `--timezone`.
- **Thumbnail Generation:** Generate 3 thumbnails by default using Antonio’s photo context (`assets/antonio-1.png`, `antonio-2.png`, `antonio-3.png`). Style: Dark mode, minimalist, cinematic lighting (cyan/purple), featuring a "Technical Artifact" (logo, code snippet, or nodes).
- **Workflow:** Upload a private draft before generating copy so the video URL can be used in newsletter/social text.
- **Links:** In the newsletter, include a markdown link to the video with descriptive text. In social posts, say “Link en el primer comentario.”
- **Timing:** Schedule social posts + newsletter 15 minutes after the YouTube publish time.

---

## Content Styles

### LinkedIn Post Style

- **Length/Format**: 600–900 characters, 3–6 short paragraphs, 1–2 emojis.
- **Strategy**: 1 central idea focused on technical authority. No digressions.
- **Closing**: Final line “Link en el primer comentario.” followed by a short question or CTA.
- **Restrictions**: No hashtags.

### Newsletter Style

- **Tone**: Long-form (220–320 words), conversational, same tone as DevExpert.
- **Prefix**: Campaign name and subject must be prefixed with: “🧑‍💻 [DEV]”.
- **Greeting**: Always start with: “¡Hola DevExpert!”.
- **Structure**:
  - Greeting + context.
  - 2–3 development paragraphs (Technical insight/problem solved).
  - “En el vídeo verás:” + 2–4 bullets.
  - Markdown link with descriptive text (e.g., `[Ver la clase de arquitectura](https://...)`).
  - Closing + CTA to comment.
  - Optional P.S.
- **Sign-off**: Must be “Un abrazo,” (blank line) “Antonio.”
- **Variety**: Vary the opening and pacing; avoid repetitive templates.

---

## Scripted flow (order)

1. **Prepare video**
   - Command:
     ```bash
     python scripts/prepare_video.py --videos /path/v1.mp4 [/path/v2.mp4 ...]
     ```
   - Output JSON with `workdir`, `video`, `slug`.

2. **Upload draft (private)**
   - Command:
     ```bash
     python scripts/upload_draft.py --video <video> --output-video-id <workdir>/video_id.txt --client-secret <path>
     ```
   - Write `video_id.txt` and create `video_url.txt`.

3. **Transcribe + clean**
   - Command:
     ```bash
     python scripts/transcribe_parakeet.py --video <video> --out-dir <workdir>
     ```
   - Outputs `transcript.es.cleaned.srt`.

4. **Generate copy (Gemini headless)**
   - Use `gemini` CLI on the cleaned SRT. Generate:
     - 3 Technical Authority Titles.
     - 3 Thumbnail ideas (Artifact-based).
     - Description (remove any self-link to current video).
     - Chapters (MM:SS).
     - LinkedIn post (per rules).
     - Newsletter (per rules, including "🧑‍💻 [DEV]" subject).
     - Save into `<workdir>/content.md`.

5. **Generate 3 thumbnails (Gemini image)**
   - Always include Antonio’s photo context. Create 3 images into `<workdir>/thumb-1.png`, `thumb-2.png`, `thumb-3.png`.

6. **Update YouTube**
   - Command:
     ```bash
     python scripts/update_youtube.py --video-id <id> --title "..." --description-file <desc.txt> --thumbnail <thumb.png> --publish-at "YYYY-MM-DD HH:MM" --timezone <IANA> --client-secret <path>
     ```

7. **Schedule socials (Postiz)**
   - Command:
     ```bash
     python scripts/schedule_socials.py --text-file <linkedin.txt> --scheduled-date <ISO8601+offset> --comment-url <video_url> --image <thumb.png>
     ```
   - Use `x-es` by default for X.

8. **Schedule newsletter (Listmonk)**
   - Command:
     ```bash
     python scripts/schedule_newsletter.py --name "YouTube: <title>" --subject "..." --body-file <newsletter.md> --send-at <ISO8601+offset>
     ```

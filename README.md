# Agent Kit

A curated catalog of Agent Skills plus supporting docs, scripts, and assets.

## Repository layout

- `skills/` — all skills (SKILL.md + resources)
- `skills/3rd-party/` — vendored third‑party skills
- `skills/skill-creator/` — canonical guide + tooling for creating skills
- `AGENTS.md` — local agent operating rules for this repo

## Skills (first‑party)

- **academy-enrollments** — Manage academy enrollments by appending rows to a Google Sheet (used by Zapier/n8n to grant LearnWorlds access).
- **bird-cli** — Use the bird CLI to access X/Twitter accounts, including reading timelines/mentions and listing unanswered mentions by date.
- **devexpert-testimonials** — Import DevExpert testimonials from Google Sheets (gog) or pasted TSV lists, format text with line breaks, crop profile images to 400x400, copy them to src/assets/testimonials, update src/data/testimonials.json, and optionally update AI Expert IDs.
- **email** — Manage inbox email. Uses the inbox script and stores metadata (ids) to open or archive messages later.
- **google-chat** — Read Google Chat spaces/threads via the Chat API, create/refresh OAuth tokens, parse Gmail Chat URLs, and list spaces.
- **holded-invoices** — Process invoice emails: download PDF attachments, extract vendor + date, generate normalized filename, and send to Holded inbox via n8n webhook.
- **justdoit** — Manage tasks via the justdoit CLI (Google Tasks + Calendar): next view, list, search, complete/undo, and common workflows.
- **morning-routine** — Orchestrates a full morning sweep of pending items (email, tasks, Slack, WhatsApp, X).
- **postiz** — Use the Postiz CLI to publish posts (create, schedule, upload images) to any configured integrations.
- **short-publish** — End-to-end workflow for turning a local video into transcripts, burned subtitles, and scheduled multi-network posts via Postiz MCP tools.
- **skill-creator** — Guide for creating or updating Agent Skills using the standardized SKILL.md specification, including naming rules, optional frontmatter fields, validation, packaging, and best practices for structuring scripts, references, and assets.
- **slack** — Manage unread Slack messages across the workspace: list, open, and reply with confirmation. Stores metadata for later actions.
- **whatsapp-evo** — Manage WhatsApp via Evolution API (v2.x): list chats with unread messages and reply.
- **worktree-helper** — Guide for creating and working in Git worktrees with a consistent workflow.
- **youtube-publish** — End-to-end YouTube publishing workflow using ordered scripts: prepare/concat video, upload draft, transcribe with Parakeet, generate copy+thumbnails with Gemini, update YouTube metadata, then schedule socials and newsletter.
- **zoom-recordings-manager** — List, download, and delete Zoom recordings via the API (OAuth).

## Skills (3rd‑party)

Most of these are derived from [Anthropic’s skills repository](https://github.com/anthropics/skills) and adapted as needed:

- **doc-coauthoring** — Guide users through a structured workflow for co-authoring documentation.
- **frontend-design** — Create distinctive, production-grade frontend interfaces with high design quality.
- **mcp-builder** — Guide for creating high-quality MCP servers that integrate external services through well-designed tools.
- **pdf** — Comprehensive PDF manipulation toolkit for extracting text and tables, creating new PDFs, merging/splitting documents, and handling forms.
- **web-artifacts-builder** — Suite of tools for creating elaborate, multi-component claude.ai HTML artifacts using modern frontend web technologies.
- **webapp-testing** — Toolkit for interacting with and testing local web applications using Playwright.

## Create or update a skill

Start with the skill‑creator:

```
./skills/skill-creator/scripts/init_skill.py <skill-name> --path skills
```

Validate:

```
./skills/skill-creator/scripts/quick_validate.py ./skills/<skill-name>
```

Package (optional):

```
./skills/skill-creator/scripts/package_skill.py ./skills/<skill-name> ./output
```

## Conventions

- Skills live at `skills/<name>/SKILL.md` and may include `scripts/`, `references/`, `assets/`.
- `skills/private/` is ignored by git.
- Secrets (OAuth client_secret.json, API keys, etc.) should live under `~/.config/skills/`.

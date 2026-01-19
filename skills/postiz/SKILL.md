---
name: postiz
description: Use the Postiz CLI to publish posts (create, schedule, upload images) to any configured integrations.
---

# Postiz (generic)

This skill is intentionally **generic** and shareable: it documents how to use the Postiz CLI and provides optional helpers.

It should NOT contain user-specific channel IDs, default publication rules, or language policy.

## Postiz CLI

CLI location (required):
- `postiz` binary available in PATH

Auth (required):
- `POSTIZ_API_KEY`
- `POSTIZ_BASE_URL`

### List integrations

- `postiz channels --pretty`

### Upload an image

- `postiz upload-file --file-path /path/img.jpg --pretty`

Use the returned `file.path` (public URL) with `--images` when creating posts.

### Create a post

- `postiz posts create --content "text" --integrations <id> --integrations <id> --status now --pretty`

Schedule:
- add `--scheduled-date "YYYY-MM-DDTHH:mm:ss+01:00"`

Images:
- add `--images <publicUrl>` (repeat for multiple images)

## Optional helper

- `postiz-publish` (python) lives in `scripts/postiz-publish`.
It is a thin helper to:
- upload local images to Postiz first
- then create the post with the returned public URLs

It still requires explicit `--integrations` and does not apply any user defaults.

Example:
`scripts/postiz-publish --content "Hello" --integrations <id> --status now`

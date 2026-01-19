# Google Chat API setup

## Required scopes

- https://www.googleapis.com/auth/chat.messages.readonly
- https://www.googleapis.com/auth/chat.spaces.readonly
- https://www.googleapis.com/auth/chat.memberships.readonly

## Token location

Default: `~/.config/google-chat/token.json`

## Client secret

Default lookup:
1) `~/.config/skills/client_secret.json`

If it is missing, pass `--client-secret` explicitly. Recommended: document the path in
`AGENTS.md` so it is easy to locate later.

## OAuth flow

Use `scripts/chat_auth.py` to generate/refresh the token. If the browser flow is blocked, pass `--no-browser` to print a URL and paste the code back into the terminal.

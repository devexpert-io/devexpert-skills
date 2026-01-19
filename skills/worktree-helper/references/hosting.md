# Hosting and Issue Intake (Agent Reference)

Goal: be host-agnostic, but prefer tooling when available.

## Preferred order

1) GitHub/GitLab MCP tools (if configured)
2) GitHub CLI `gh`
3) GitLab CLI `glab`
4) Manual fallback (user pastes issue details)

## GitHub CLI checks

Detect:
```
command -v gh
```
Auth check:
```
gh auth status
```
Issue view:
```
gh issue view <id> --json title,body,assignees,labels
```

## GitLab CLI checks

Detect:
```
command -v glab
```
Auth check:
```
glab auth status
```
Issue view:
```
glab issue view <id>
```

## Manual fallback (no tools available)

Ask the user to paste:
- Issue/title
- Description
- Acceptance criteria (if any)
- Relevant links or references

If the user provides a URL but no content, ask them to paste the issue text since you cannot fetch it without tools.

## Suggest installations

If CLI tools are missing, suggest installing `gh` or `glab` to make issue flows easier.

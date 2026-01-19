# Agent Kit

A curated catalog of Agent Skills plus supporting docs, scripts, and assets.

## Repository layout

- `skills/` — all skills (SKILL.md + resources)
- `skills/3rd-party/` — vendored third‑party skills
- `skills/skill-creator/` — canonical guide + tooling for creating skills
- `AGENTS.md` — local agent operating rules for this repo

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

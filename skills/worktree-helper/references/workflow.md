# Worktree Workflow (Agent Reference)

Use this when executing a task in a new worktree. Keep the user in control at each potentially destructive step.

## 1) Intake

Determine the request type:
- **Issue-based**: "issue 25" or similar.
- **Task-based**: plain description of work to do.

Ask for any missing context (repo, scope, acceptance criteria).

## 2) Workspace layout check

Preferred layout (container root, not a git repo):
```
workspace/
  main/        (git repo)
  worktrees/
```

If the user is currently inside a repo root (code + .git at top level), recommend migration to the preferred layout and offer to run:
```
worktree-helper/scripts/migrate_to_main_layout.sh <repo-root>
```

If the layout is already in place, continue in `main/`.

## 3) Determine base branch

Default: `main`.
If remote exists, try to detect:
```
git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@'
```
Fallbacks:
- If local `main` exists, use it.
- Else if `master` exists, use it.

## 4) Naming

**Branch names**
- Issue: `issue-<id>-<slug>`
- Task: `task/<slug>`

**Worktree directory**
- `worktrees/issue-<id>-<slug>`
- `worktrees/task-<slug>`

Slug rules: lowercase, replace spaces with `-`, strip non-alphanumerics and extra hyphens.

## 5) Create the worktree

From `main/`:
```
# If branch does not exist yet

git worktree add -b <branch> ../worktrees/<dir> <base>

# If branch already exists

git worktree add ../worktrees/<dir> <branch>
```

If `<base>` is remote-only:
```
git fetch origin <base>
```

## 6) Develop

Work inside the new worktree directory. Follow project conventions and run tests as needed.

## 7) Review checkpoint

Ask the user to review results. Summarize changes and confirm next step.

## 8) Finish options

**Merge into main** (from `main/`):
```
git merge <branch>
```

**Create PR / MR**
Use host tools if available (GitHub: `gh pr create`, GitLab: `glab mr create`).
If none are available, ask the user to create a PR/MR manually.

**Cleanup**
```
git worktree remove ../worktrees/<dir>
git branch -d <branch>
git worktree prune
```

## Safety

Always confirm before:
- Migrating the repo layout
- Deleting branches
- Removing worktrees

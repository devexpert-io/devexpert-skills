# Worktree Workflow

This workflow keeps your repo clean and makes multi-branch work predictable.

## Recommended layout

```
workspace/            (not a git repo)
  main/               (git repo)
  worktrees/
```

Why? Git worktrees cannot be nested inside another worktree. By keeping `main/` and `worktrees/` as siblings, you can add and remove worktrees safely.

## If your repo is already in the root

If your code and `.git` are at the root of the workspace, migrate to the layout above.

Automatic migration (provided by the skill):
```
worktree-helper/scripts/migrate_to_main_layout.sh <repo-root>
```

Manual steps:
1. Ensure the working tree is clean
2. Create `main/` and `worktrees/`
3. Move `.git` and all project files into `main/`

## Preflight checks

Before creating a worktree, verify:

- The working tree is clean
- You know the base branch
- You aren’t duplicating an existing worktree

Commands (from `main/`):
```
# Clean working tree

git status --porcelain

# Base branch (prefer remote default)

git symbolic-ref refs/remotes/origin/HEAD | sed 's@^refs/remotes/origin/@@'

# Existing worktrees

git worktree list
```

If you have a remote configured, fetch updates:
```
git fetch origin
```

## Branch and directory naming

- Issue-based: `issue-<id>-<slug>`
- Task-based: `task/<slug>`

Worktree directory:
- `worktrees/issue-<id>-<slug>`
- `worktrees/task-<slug>`

Slug rules: lowercase, replace spaces with `-`, remove non-alphanumerics.

## Create a worktree

From `main/`:
```
# New branch

git worktree add -b issue-25-fix-login ../worktrees/issue-25-fix-login main

# Existing branch

git worktree add ../worktrees/issue-25-fix-login issue-25-fix-login
```

## Finish and clean up

From `main/`:
```
# Merge

git merge issue-25-fix-login

# Remove worktree

git worktree remove ../worktrees/issue-25-fix-login

# Delete branch

git branch -d issue-25-fix-login

# Clean stale metadata

git worktree prune
```

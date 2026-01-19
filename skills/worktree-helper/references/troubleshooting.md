# Worktree Troubleshooting (Agent Reference)

## Common errors

- **"not a git repository"**
  - You are not in `main/`. Change to the repo root and retry.

- **"fatal: A branch named 'X' already exists"**
  - Use `git worktree add <path> <branch>` without `-b`.

- **"worktree already exists" / path exists**
  - Pick a new directory name or remove the old worktree:
    `git worktree remove <path>`

- **"locked" worktree**
  - Run `git worktree prune` and retry.

- **Uncommitted changes block checkout**
  - Commit, stash, or clean the working tree before creating a new worktree.

## Clean up

```
git worktree list
git worktree prune
```

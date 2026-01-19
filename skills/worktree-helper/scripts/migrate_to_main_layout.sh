#!/usr/bin/env bash
set -euo pipefail

ROOT="${1:-$PWD}"

if ! command -v git >/dev/null 2>&1; then
  echo "Error: git is not installed." >&2
  exit 1
fi

cd "$ROOT"

if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  echo "Error: '$ROOT' is not a git repository." >&2
  exit 1
fi

TOP=$(git rev-parse --show-toplevel)
if [ "$TOP" != "$ROOT" ]; then
  echo "Error: run this from the repo root: $TOP" >&2
  exit 1
fi

if [ -n "$(git status --porcelain)" ]; then
  echo "Error: working tree is not clean. Commit or stash changes first." >&2
  exit 1
fi

if [ -e main ] || [ -e worktrees ]; then
  echo "Error: 'main' or 'worktrees' already exists. Aborting." >&2
  exit 1
fi

mkdir main worktrees

# Move the git directory first, then everything else into main/
if [ -d .git ]; then
  mv .git main/.git
else
  echo "Error: .git directory not found." >&2
  exit 1
fi

find . -maxdepth 1 -mindepth 1 \
  -not -name main \
  -not -name worktrees \
  -exec mv {} main/ \;

echo "Done. Repository moved to: $ROOT/main"
echo "Worktrees directory created at: $ROOT/worktrees"

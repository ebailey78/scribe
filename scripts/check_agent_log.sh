#!/usr/bin/env bash
set -euo pipefail

# Files changed in the staged set
CHANGED_FILES=$(git diff --cached --name-only)

# If no staged changes, nothing to do
if [[ -z "$CHANGED_FILES" ]]; then
  exit 0
fi

# Determine if any tracked code/config files changed (heuristic)
NEEDS_LOG=0
while IFS= read -r file; do
  case "$file" in
    src/*|config/*|pyproject.toml|AGENTS.md|README.md)
      NEEDS_LOG=1
      ;;
  esac
done <<< "$CHANGED_FILES"

if [[ "$NEEDS_LOG" -eq 0 ]]; then
  exit 0
fi

# Check whether AGENT_LOG.md is staged
if ! grep -q "^AGENT_LOG.md$" <<< "$CHANGED_FILES"; then
  echo "ERROR: Code/config/docs changes detected but AGENT_LOG.md is not updated." >&2
  echo "       Please add an entry at the top of AGENT_LOG.md describing this change." >&2
  exit 1
fi

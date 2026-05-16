#!/usr/bin/env bash
set -euo pipefail

payload="$(cat)"
message=$(echo "$payload" | jq -r '.message')

# Nombre del worktree (raíz del repo actual)
repo_root=$(git rev-parse --show-toplevel 2>/dev/null || pwd)
worktree_name=$(basename "$repo_root")

/usr/bin/say -v Kate "[$worktree_name] $message"

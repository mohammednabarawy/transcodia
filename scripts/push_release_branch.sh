#!/usr/bin/env bash
# Advance the release branch without rewriting remote history.
# Usage:  ./scripts/push_release_branch.sh
set -euo pipefail

if [[ -n "$(git status --porcelain)" ]]; then
  echo "Commit or save local changes before updating the release branch." >&2
  exit 1
fi
git fetch origin main
git push origin refs/remotes/origin/main:refs/heads/transcodia-release
echo "Release branch advanced. Desktop jobs require ENABLE_DESKTOP_RELEASES=true."

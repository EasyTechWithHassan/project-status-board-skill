#!/usr/bin/env bash
# Link this repository's skill into Claude Code, Gemini CLI and Codex (user level).
#
#   ./install.sh              create the links
#   ./install.sh --uninstall  remove them (only links that point here)
#
# One canonical copy, two symlinks:
#   ~/.claude/skills/project-status-board  -> Claude Code
#   ~/.agents/skills/project-status-board  -> Gemini CLI and Codex (shared folder)
# Edits in this repo take effect immediately in all three tools.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/skills/project-status-board"
TARGETS=("$HOME/.claude/skills/project-status-board" "$HOME/.agents/skills/project-status-board")

[ -f "$SRC/SKILL.md" ] || { echo "error: $SRC/SKILL.md not found" >&2; exit 1; }

for target in "${TARGETS[@]}"; do
  if [ "${1:-}" = "--uninstall" ]; then
    if [ -L "$target" ] && [ "$(readlink "$target")" = "$SRC" ]; then
      rm "$target" && echo "removed  $target"
    else
      echo "skipped  $target (not a link to this repo)"
    fi
  elif [ -L "$target" ] && [ "$(readlink "$target")" = "$SRC" ]; then
    echo "ok       $target (already linked)"
  elif [ -e "$target" ] || [ -L "$target" ]; then
    echo "skipped  $target already exists and is not a link to this repo; move it away and re-run" >&2
  else
    mkdir -p "$(dirname "$target")"
    ln -s "$SRC" "$target" && echo "linked   $target -> $SRC"
  fi
done

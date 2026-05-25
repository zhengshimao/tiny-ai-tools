#!/bin/bash
# run.sh — cross-platform wrapper for smoke.sh
# Auto-detects Windows (Git Bash / MSYS2) vs native Linux / WSL
# and invokes smoke.sh correctly for the current platform.
#
# Usage (from repo root or anywhere):
#   bash .claude/skills/run-ds4-fastq-qc/run.sh          # all tests
#   bash .claude/skills/run-ds4-fastq-qc/run.sh build    # single target
#   bash .claude/skills/run-ds4-fastq-qc/run.sh se json  # multiple targets

set -euo pipefail

# Repo root is three levels up from this script's directory
# (.claude/skills/run-ds4-fastq-qc/run.sh)
REPO_ROOT="$(cd "$(dirname "$0")/../../.." && pwd)"
SCRIPT=".claude/skills/run-ds4-fastq-qc/smoke.sh"

is_windows() {
  [ "${OS:-}" = "Windows_NT" ] && return 0
  case "$(uname -s 2>/dev/null)" in
    MINGW*|MSYS*|CYGWIN*) return 0 ;;
    *) return 1 ;;
  esac
}

windows_to_wsl() {
  # Handles both Git Bash (/d/path) and Windows native (D:\path) formats
  local p="$1"
  # Git Bash format: /d/path → /mnt/d/path
  if [[ "$p" =~ ^/([a-zA-Z])/ ]]; then
    local drive="${BASH_REMATCH[1],,}"
    echo "/mnt/$drive/${p:3}"
  else
    # Windows native format: D:\path → /mnt/d/path
    local drive="${p:0:1}"
    drive="${drive,,}"
    echo "/mnt/$drive/${p:3}" | sed 's|\\|/|g'
  fi
}

if is_windows; then
  WSL_ROOT="$(windows_to_wsl "$REPO_ROOT")"
  exec wsl bash -c "cd '$WSL_ROOT' && bash $SCRIPT $*"
else
  cd "$REPO_ROOT"
  exec bash "$SCRIPT" "$@"
fi

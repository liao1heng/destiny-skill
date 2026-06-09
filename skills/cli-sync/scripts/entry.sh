#!/usr/bin/env bash
set -euo pipefail

mode="status"
message="Sync local Codex skills"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --mode|-m)
      mode="${2:?missing mode value}"
      shift 2
      ;;
    --message)
      message="${2:?missing message value}"
      shift 2
      ;;
    status|pull|push)
      mode="$1"
      shift
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

test_python() {
  local cmd="$1"
  command -v "$cmd" >/dev/null 2>&1 || return 1
  "$cmd" -c 'import sys' >/dev/null 2>&1
}

if test_python python3; then
  exec python3 "$script_dir/sync_skills.py" --mode "$mode" --message "$message"
elif test_python python; then
  exec python "$script_dir/sync_skills.py" --mode "$mode" --message "$message"
elif command -v uv >/dev/null 2>&1; then
  exec uv run --python 3.11 "$script_dir/sync_skills.py" --mode "$mode" --message "$message"
else
  echo "cli-sync requires a working Python interpreter or uv, but neither is available." >&2
  exit 1
fi

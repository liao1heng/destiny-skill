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

python_cmd=""
if command -v python3 >/dev/null 2>&1; then
  python_cmd="python3"
elif command -v python >/dev/null 2>&1; then
  python_cmd="python"
else
  echo "Python is required for cli-sync but was not found in PATH." >&2
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$python_cmd" "$script_dir/sync_skills.py" --mode "$mode" --message "$message"

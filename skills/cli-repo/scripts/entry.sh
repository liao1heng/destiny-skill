#!/usr/bin/env bash
set -euo pipefail
script_dir=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
for cmd in python3 python; do
 if command -v "$cmd" >/dev/null 2>&1 && "$cmd" -c 'import sys; assert sys.version_info >= (3, 10)' >/dev/null 2>&1; then
  exec "$cmd" "$script_dir/repo.py" "$@"
 fi
done
if command -v uv >/dev/null 2>&1; then exec uv run --python 3.11 "$script_dir/repo.py" "$@"; fi
echo 'cli-repo需要Python 3.10+或uv' >&2
exit 1

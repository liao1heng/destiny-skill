#!/usr/bin/env bash
set -euo pipefail

python_cmd=""
if command -v python3 >/dev/null 2>&1; then
  python_cmd="python3"
elif command -v python >/dev/null 2>&1; then
  python_cmd="python"
else
  echo "Python 3 is required for cli-vpn-install but was not found in PATH." >&2
  exit 1
fi

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec "$python_cmd" "$script_dir/cli_vpn_install.py" "$@"

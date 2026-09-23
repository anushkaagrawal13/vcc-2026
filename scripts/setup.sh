#!/usr/bin/env bash
# Run from a checkout of the reviewed commit. Never replaces an existing venv.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ ! -x .venv/bin/python ]]; then
  bootstrap_dir=$(mktemp -d)
  trap 'rm -rf "$bootstrap_dir"' EXIT
  python3 -m venv "$bootstrap_dir/venv"
  "$bootstrap_dir/venv/bin/pip" install 'uv==0.8.22'
  "$bootstrap_dir/venv/bin/uv" python install 3.12.2
  "$bootstrap_dir/venv/bin/uv" venv --python 3.12.2 .venv
fi
.venv/bin/python -c 'import sys; assert sys.version_info[:3] == (3,12,2), sys.version'
.venv/bin/python -m ensurepip
.venv/bin/python -m pip install -r requirements.lock.txt
.venv/bin/python -m pip check
.venv/bin/python -m pytest -q

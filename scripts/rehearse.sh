#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
# Synthetic cells only; no download, authentication, submission, or shutdown.
.venv/bin/python -m pytest -q tests/test_roundtrip.py tests/test_runner.py

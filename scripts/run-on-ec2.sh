#!/usr/bin/env bash
# One bounded batch: power off on completion/failure; retained EBS still bills.
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ $(uname -s) != Linux ]] || ! grep -qi 'Amazon EC2' /sys/class/dmi/id/sys_vendor; then
  echo 'Refusing shutdown automation outside an Amazon EC2 Linux instance.' >&2
  exit 1
fi
# Require preconfigured passwordless sudo before doing any expensive work.
sudo -n true
: "${VCC_TOKEN:?Set VCC_TOKEN through a private terminal prompt before starting}"
# A system-level deadline survives terminal disconnection and script failure.
# Fail closed if a timer with this name exists; do not silently extend it.
sudo -n systemd-run --unit=vcc-deadline --on-active=8h /usr/bin/systemctl poweroff
trap 'rc=$?; trap - EXIT; sudo -n /usr/bin/systemctl poweroff; exit "$rc"' EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
bash scripts/setup.sh
.venv/bin/python -m src.run --config "${1:-config/000_zero_delta.yaml}"

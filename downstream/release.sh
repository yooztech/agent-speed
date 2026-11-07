#!/usr/bin/env bash
set -euo pipefail
log_dir="${XDG_CACHE_HOME:-${HOME:?HOME must be set}/.cache}/agent-speed"
log_file="$log_dir/release.log"
mkdir -p "$log_dir"

set +e
python3 "$(dirname "$0")/release.py" "$@" 2>&1 | tee "$log_file"
statuses=("${PIPESTATUS[@]}")
set -e

status=${statuses[0]}
if (( status == 0 )); then
  status=${statuses[1]}
fi
if (( status != 0 )); then
  printf 'Release command failed; log: %s\n' "$log_file" >&2
  printf 'If Actions already started, it may still be running. Resume observation with: bash downstream/release.sh --resume RUN_ID\n' >&2
  if [[ -t 0 && -t 2 ]]; then
    read -r -p 'Press Enter to close this terminal...' _ || true
  fi
fi
exit "$status"

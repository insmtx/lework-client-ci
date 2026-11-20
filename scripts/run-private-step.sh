#!/usr/bin/env bash
set -euo pipefail

if "$@" >/dev/null 2>&1; then
  exit 0
else
  status="$?"
  printf 'The command exited with status %s. Reproduce in the private pipeline for detailed logs.\n' "$status" >&2
  exit "$status"
fi

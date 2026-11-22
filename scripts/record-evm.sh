#!/usr/bin/env bash
# Runs the evm-recordings tests (which fail on purpose so the runner prints real revert data), decodes each revert
# and writes web/recorded.json. Use --check to verify the recorded file without writing.
# Prints "Expected failures: N/N recorded" and exits 0 only when every expected failure was recorded.
set -eu
cd "$(dirname "$0")/.."
exec python3 scripts/record_evm.py "$@"

#!/usr/bin/env bash
# Runs the proof suites (planted bugs, std, ERC20) and writes docs/PROOF.md; --check verifies without writing.
set -eu
cd "$(dirname "$0")/.."
exec python3 scripts/proof.py "$@"

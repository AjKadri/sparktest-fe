#!/usr/bin/env bash
# Runs the 5 cross-check scenarios on sonatina (events) and native (println) with identical numeric seeds
# and diffs the results. Exit 0 only if identical.
set -eu
export PATH="$HOME/.fe/bin:$PATH"
cd "$(dirname "$0")/.."
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT

( cd tests-evm && fe test --filter xcheck --show-logs ) 2>&1 | python3 -I scripts/xcheck_format.py > "$tmp/evm.txt"
( cd xcheck-native && fe build --backend native --emit executable --out-dir "$tmp/native-out" >/dev/null 2>&1 && "$tmp/native-out/xcheck_native" ) > "$tmp/native.txt"

echo "--- sonatina ($(grep -c 'failed=' "$tmp/evm.txt") scenarios)"; cat "$tmp/evm.txt"
echo "--- native ($(grep -c 'failed=' "$tmp/native.txt") scenarios)"; cat "$tmp/native.txt"
if [ "$(grep -c 'failed=' "$tmp/evm.txt")" != 5 ]; then echo "cross-check: expected 5 EVM scenarios"; exit 1; fi
if diff "$tmp/evm.txt" "$tmp/native.txt" > "$tmp/diff.txt"; then echo "CROSS-CHECK: IDENTICAL (5/5)"; else echo "CROSS-CHECK: MISMATCH"; cat "$tmp/diff.txt"; exit 1; fi

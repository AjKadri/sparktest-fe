#!/usr/bin/env bash
# Runs every test ingot. Exits non-zero if any fails.
# To add a target, append a line to SUITES: "<dir> <extra fe test args...>"
set -u
export PATH="$HOME/.fe/bin:$PATH"
cd "$(dirname "$0")/.."

SUITES=(
  "tests-evm"
  # "tests-native --backend native"   # later
  # "tests-wasm --backend wasm"       # later
)

failed=0
for entry in "${SUITES[@]}"; do
  read -r dir args <<<"$entry"
  echo "=== $dir ${args:-}"
  # shellcheck disable=SC2086
  if ! (cd "$dir" && fe test ${args:-}); then
    echo "FAILED: $dir"
    failed=1
  fi
done
exit $failed

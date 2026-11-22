#!/usr/bin/env bash
# Runs every part of the suite; exits non-zero if any part fails. Each part prints a header and a PASS/FAIL line.
set -u
export PATH="$HOME/.fe/bin:$PATH"
cd "$(dirname "$0")/.."

failed=0
part() { # part <name> <command...>
  local name="$1"; shift
  echo "=== $name"
  if "$@"; then echo "--- PART OK: $name"; else echo "--- PART FAILED: $name"; failed=1; fi
}

fe_suite()  { (cd "$1" && shift && fe test "$@"); }
freshness() {
  python3 scripts/gen_widths.py && python3 scripts/gen_composite.py && python3 scripts/gen_checked.py \
    && git diff --exit-code -- sparktest/src/widths.fe sparktest/src/composite.fe sparktest/src/checked.fe \
    && echo "generated files are up to date"
}

part "tests-evm (sonatina)"      fe_suite tests-evm
part "tests-native (native)"     fe_suite tests-native
part "decode-revert (node)"      node tools/decode-revert/test.mjs
part "cross-check (sonatina vs native)" ./scripts/cross-check.sh
part "freshness (generated files)" freshness

if [ "$failed" -eq 0 ]; then echo "ALL PARTS PASSED"; else echo "SOME PARTS FAILED"; fi
exit $failed

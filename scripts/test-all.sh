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
demo_web() {
  ./scripts/build-demo.sh && node web/sparktest.test.mjs
}
recordings() {
  ./scripts/record-evm.sh --check
}
erc20() {
  ./scripts/check-vendored.sh && fe_suite examples/erc20 && fe_suite tests-erc20
}
rewards() {
  fe_suite tests-rewards
}
proof() {
  ./scripts/proof.sh --check
}
freshness() {
  python3 scripts/gen_widths.py && python3 scripts/gen_composite.py && python3 scripts/gen_checked.py && python3 scripts/gen_proof.py && python3 scripts/gen_erc20_tests.py \
    && git diff --exit-code -- sparktest/src/widths.fe sparktest/src/composite.fe sparktest/src/checked.fe props/src/proof_scenarios.fe tests-evm/src/proof.fe proof-native/src/lib.fe tests-erc20/src/original.fe tests-erc20/src/buggy.fe tests-erc20/src/original_idx.fe tests-erc20/src/buggy_idx.fe tests-erc20/src/stateful_orig.fe tests-erc20/src/stateful_bug.fe \
    && echo "generated files are up to date"
}

part "tests-evm (sonatina)"      fe_suite tests-evm
part "tests-native (native)"     fe_suite tests-native
part "decode-revert (node)"      node tools/decode-revert/test.mjs
part "cross-check (sonatina vs native)" ./scripts/cross-check.sh
part "erc20 (sonatina only): vendored example + properties + planted bug" erc20
part "rewards (sonatina only): contract panic via try_call vs direct call" rewards
part "quickstart example (a separate ingot using sparktest as the README says)" fe_suite examples/quickstart
part "docs (README excerpts verbatim from the quickstart; every API.md example compiles and passes)" ./scripts/check-docs.py
part "proof suites (planted bugs, std, erc20 -> docs/PROOF.md --check)" proof
part "web demo (build wasm + node test)" demo_web
part "evm recordings are current (record-evm.sh --check)" recordings
part "freshness (generated files)" freshness

if [ "$failed" -eq 0 ]; then echo "ALL PARTS PASSED"; else echo "SOME PARTS FAILED"; fi
exit $failed

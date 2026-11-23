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
coolcoin() {
  fe_suite examples/coolcoin && fe_suite tests-coolcoin
}
isolated() {
  fe_suite tests-isolated
}
rewards() {
  fe_suite tests-rewards
}
proof() {
  ./scripts/proof.sh --check
}
# first-party ingots that are formatted with `fe fmt` (the vendored upstream files, their planted-bug copies and the generated mutants are NOT:
# they must stay byte-identical to their sources)
FMT_DIRS="sparktest sparktest-evm sparktest-native props erc20-actors tests-evm tests-native tests-erc20 tests-coolcoin tests-rewards tests-isolated examples/quickstart examples/rewards evm-recordings demo-wasm bench-native proof-native replay-native xcheck-native"
format() {
  local bad=0
  for d in $FMT_DIRS; do
    if ! fe fmt --check "$d" >/dev/null 2>&1; then echo "not formatted: $d (run: fe fmt $d)"; bad=1; fi
  done
  [ "$bad" -eq 0 ] && echo "fe fmt --check: all first-party ingots are formatted"
  return $bad
}
freshness() {
  python3 scripts/gen_widths.py && python3 scripts/gen_composite.py && python3 scripts/gen_checked.py && python3 scripts/gen_proof.py && python3 scripts/gen_erc20_tests.py && python3 scripts/gen_mutants.py \
    && python3 scripts/gen_heldout_mutants.py && python3 scripts/gen_hunt.py && python3 scripts/gen_signed.py \
    && for d in sparktest props tests-evm proof-native tests-erc20 tests-coolcoin; do fe fmt "$d" >/dev/null 2>&1; done \
    && git diff --exit-code -- sparktest/src/widths.fe sparktest/src/composite.fe sparktest/src/checked.fe sparktest/src/signed.fe props/src/proof_scenarios.fe props/src/hunt_map.fe tests-evm/src/proof.fe proof-native/src/lib.fe tests-erc20/src/original.fe tests-erc20/src/buggy.fe tests-erc20/src/original_idx.fe tests-erc20/src/buggy_idx.fe tests-erc20/src/stateful_orig.fe tests-erc20/src/stateful_bug.fe tests-erc20/src/vacuous_demo.fe tests-coolcoin/src examples/coolcoin-mutants examples/coolcoin-heldout \
    && echo "generated files are up to date (regenerated, formatted, identical to the committed files)"
}

part "tests-evm (sonatina)"      fe_suite tests-evm
part "tests-native (native)"     fe_suite tests-native
part "decode-revert (node)"      node tools/decode-revert/test.mjs
part "cross-check (sonatina vs native)" ./scripts/cross-check.sh
part "erc20 (sonatina only): vendored example + properties + planted bug" erc20
part "coolcoin (sonatina only): the Fe Guide ERC-20 unchanged + 10 mutants (results recorded; the proof part checks them)" coolcoin
part "isolated (sonatina): panic recovery through a harness contract" isolated
part "rewards (sonatina only): contract panic via try_call vs direct call" rewards
part "quickstart example (a separate ingot using sparktest as the README says)" fe_suite examples/quickstart
part "docs (README excerpts verbatim from the quickstart; every API.md example compiles and passes)" ./scripts/check-docs.py
part "proof suites (planted bugs, std, erc20 -> docs/PROOF.md --check)" proof
part "web demo (build wasm + node test)" demo_web
part "evm recordings are current (record-evm.sh --check)" recordings
part "format (fe fmt --check on every first-party ingot)" format
part "freshness (generated files)" freshness

if [ "$failed" -eq 0 ]; then echo "ALL PARTS PASSED"; else echo "SOME PARTS FAILED"; fi
exit $failed

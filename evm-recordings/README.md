# evm-recordings

These tests **fail on purpose**. Each `rec_*` test that checks a failing property is marked
`#[test(should_revert, selector = 0xdeadbeef)]`, a selector that is deliberately wrong, so `fe test` prints the
real `PropertyFailed` revert data it got instead: `Expected revert with selector 0xdeadbeef, but got revert data: 0x4c350703…`.
`scripts/record-evm.sh` runs them, decodes each revert with `tools/decode-revert`, and writes the result to
`web/recorded.json`, which the demo page shows in its "Recorded on EVM" panel. The one passing test records how many
cases ran and the gas they cost.

Do not add this ingot to `test-all.sh`'s test suites: a red run here is the expected outcome. `scripts/record-evm.sh --check`
re-runs the recordings and verifies `web/recorded.json` still matches, without writing anything.

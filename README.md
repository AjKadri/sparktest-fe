# fe-quickcheck

fe-quickcheck is a property-testing library for [Fe](https://fe-lang.org): you state a property of your code, it generates many random inputs (biased toward edge values), and when a case fails it shrinks the input to a minimal counterexample. The core (`qc/`) is written in Fe and has no effects, so it can run on every Fe backend; `qc-evm/` adds a thin EVM shim that reverts with the shrunk input.

**Status: work in progress.** Only `u256` and `bool` are supported so far.

## Run the tests

Requires Fe 26.7.0 (`export PATH=$HOME/.fe/bin:$PATH`).

```bash
./scripts/test-all.sh
```

The script runs `fe test` in each test ingot (currently `tests-evm/`) and exits non-zero if any suite fails.

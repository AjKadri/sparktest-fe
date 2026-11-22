# Sparktest

Property testing for Fe: find the input that breaks your code, shrink it, replay it.

Sparktest generates many random inputs (biased toward edge values such as 0, max and powers of two), checks a property you state, and when a case fails it shrinks the input to a minimal counterexample and reports the seed so the failure can be replayed exactly. The core (`sparktest/`) is written in Fe and has no effects, so it runs on every Fe backend; `sparktest-evm/` adds a thin EVM shim that reverts with the shrunk input, and `sparktest-native/` prints it.

**Live demo:** https://ajkadri.github.io/sparktest-fe/ (placeholder until the first deploy)

**Status: work in progress.** Supported inputs so far: `bool`, `u8`..`u256`, `Address`, tuples of 2 to 4, fixed arrays and user structs (by delegating to a tuple).

## Run the tests

Requires Fe 26.7.0 (`export PATH=$HOME/.fe/bin:$PATH`) and Node 20+.

```bash
./scripts/test-all.sh
```

The script runs the sonatina (EVM) and native suites, the revert decoder tests, a sonatina-vs-native cross-check, the web demo build and its Node test, and a freshness check of the generated files. It exits non-zero if any part fails.

## Web demo

`web/` is a static page (no framework, no build step, no CDN) that runs compiled Fe properties in the browser: pick a property, run it, watch the first counterexample get shrunk, and replay it from the seed. The Fe module is compiled to WebAssembly by `demo-wasm/`.

```bash
./scripts/build-demo.sh                      # compile demo-wasm, copy the .wasm, extract Fe sources, record EVM + native runs into web/props.json
cd web && python3 -m http.server 8765        # then open http://localhost:8765/   (local run)
```

The page loads `props.json` and `demo_wasm.wasm` with relative paths, so it also works under a sub-path such as `https://<user>.github.io/<repo>/`. `./scripts/record-evm.sh` re-records the sonatina runs shown in the page's "Recorded on EVM" panel (`--check` verifies them without writing). `node web/sparktest.test.mjs` checks that the wasm results equal the recorded sonatina (EVM) and native results for the same seeds.

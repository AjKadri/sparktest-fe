# Sparktest: pitch

**Sparktest is a property-testing library written in Fe: state a rule, and it finds the input that breaks it (in values, contract calls or call sequences), shrinks it to a minimal case even through panics, and replays it from a seed on the EVM, natively and in the browser.**

**Problem.** Unit tests only check the inputs you thought of. Contract bugs live at the edges: a rounding direction, an overflow at a large amount, a state that takes several calls to reach. Fe's built-in test runner has no property testing.

**Evidence.** Trail of Bits studied 246 findings from 23 of its audits and estimated that 63% of the high-severity, low-difficulty ones (17 of 27) were plausibly detectable with user-defined properties (arXiv:1911.07567).

**Cost.** Rounding direction is a known attack surface: OpenZeppelin's ERC-4626 guide shows how an inflation attack uses share rounding to take a depositor's tokens. The demo's vault bug rounds the other way and overpays depositors, draining the vault instead.

**Solution.** You state a rule; Sparktest tries many inputs, favouring edge values such as zero and the maximum. When the rule breaks, it shrinks the input to the smallest one that still breaks it and prints a seed that reproduces the failure exactly. It runs on EVM tests, native code and WebAssembly, calls deployed contracts, recovers from panics, tests sequences of calls, takes custom generators, discards cases whose premise fails (counting the discards and flagging a vacuous run) and replays regression seeds first, and stops shrinking before the gas cap so a failure never loses its report.

**Walkthrough.** Open the demo, pick *Buggy sort*, press Run. Sparktest finds an unsorted input, shrinks it in 132 steps to `[1, 1, 1, 0]`, and Replay reproduces it from the seed. For the same numeric seed, every demo result is identical on WebAssembly, native and EVM.

**Before / after.** Three unit tests of a vault with a rounding bug pass. One property finds it and shrinks it to a vault of 3 assets and 1 share, with a deposit of 1.

Proof in the repo: five planted bug classes found, an ERC20 fixture checked through contract calls, the Fe Guide's ERC-20 with 8 of 10 planted mutants caught and 4 of 5 held-out mutants caught as predicted, 27 std properties pass (no Fe bug found), a panic shrunk to its exact boundary, expectations written before running.

## Fe-specific highlight (for the submission form)

Sparktest's runner is effect-polymorphic (`uses P::E`), so one `check` accepts pure properties and properties that call contracts; a property that records its calls in a `Tally` effect hands it to its caller through the same mechanism, which is how vacuous passes are caught. The core stays effect-free and per-backend shims handle the `Evm` and `Host` entry effects. It uses const-generic arrays and trait-based generators, turns a contract panic into a value through `try_call`, and builds `check_isolated` on that to shrink panicking properties. The same numeric seed gives identical results on sonatina, native and WebAssembly, so the library doubles as a cross-backend consistency check for the compiler.

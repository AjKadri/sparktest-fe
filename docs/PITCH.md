# Sparktest: pitch

**Sparktest is a property-testing library written in Fe: state a rule, and it finds the input that breaks it (in values, contract calls or call sequences), shrinks it to a small case even through panics, and replays it from a seed on the EVM, natively and in the browser.**

**Problem.** Unit tests only check the inputs you thought of. Contract bugs live at the edges: a rounding direction, an overflow at a large amount, a state that takes several calls to reach. Fe's built-in test runner has no property testing.

**Evidence.** Trail of Bits studied 246 findings from 23 of its audits and estimated that 63% of the high-severity, low-difficulty ones (17 of 27) were plausibly detectable with user-defined properties (arXiv:1911.07567).

**Cost.** Rounding direction is a known attack surface: OpenZeppelin's ERC-4626 guide shows how an inflation attack uses share rounding to take a depositor's tokens. The demo's vault bug rounds the other way and overpays depositors, draining the vault instead.

**Solution.** You state a rule; Sparktest tries many inputs, favouring edge values such as zero and the maximum. When the rule breaks, it shrinks the input to a small one that still breaks it (shrinking is greedy, so not always the smallest) and prints a seed that reproduces the failure exactly. It runs on EVM tests, native code and WebAssembly, calls deployed contracts, recovers from panics, tests sequences of calls, takes custom generators, discards cases whose premise fails (counting the discards and flagging a vacuous run) and replays regression seeds first, and, with `check_gas` (or `check_gen_gas`), stops shrinking before the gas cap so a failure run that way never loses its report.

**Walkthrough.** Open the demo, pick *Buggy sort*, press Run. Sparktest finds an unsorted input, shrinks it in 132 steps to `[1, 1, 1, 0]`, and Replay reproduces it from the seed. For the same numeric seed, every demo result is identical on WebAssembly, native and EVM.

**Before / after.** Three unit tests of a vault with a rounding bug pass. One property finds it and shrinks it to a vault of 3 assets and 1 share, with a deposit of 1.

Proof in the repo: five planted bug classes found, an ERC20 fixture checked through contract calls, the Fe Guide's ERC-20 with 8 of 10 planted mutants caught and 4 of 5 held-out mutants caught as predicted, 27 std properties pass (no Fe bug found), a panic shrunk to its exact boundary, expectations committed before the results commit.

## Fe-specific highlight (for the submission form)

On the EVM test backend a panicking property becomes a value: `check_isolated` runs each evaluation inside a harness contract through `try_call`, so the panic is reported with its reason and shrunk inside `fe test` instead of ending the test. The same Fe property code runs on sonatina, native and WebAssembly, and the same numeric seed gives identical results on sonatina and native, and on WebAssembly for the demo properties, so a disagreement between backends on the same seed is a finding (the repo compares 11 fixed scenarios, and the demo compares its six properties); the live demo runs it in the browser. Underneath is an effect-polymorphic runner (`uses P::E`): one `check` accepts pure properties, contract-calling properties and properties that record into a `Tally` effect, which travels back to the caller and is how vacuous passes are caught. The core stays effect-free, with per-backend shims for the `Evm` and `Host` entry effects, and generators are trait-based, including const-generic arrays.

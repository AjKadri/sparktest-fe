# Sparktest: pitch

**Problem.** Unit tests only check the inputs you thought of. Contract bugs live at the edges: a rounding direction, an overflow at a large amount, a state that takes several calls to reach.

**Evidence.** Trail of Bits studied 246 findings from 23 of its audits and estimated that 63% of the high-severity, low-difficulty ones (17 of 27) were plausibly detectable with user-defined properties (arXiv:1911.07567). Fe had no property-testing library.

**Cost.** In OpenZeppelin's ERC-4626 write-up, bad share rounding lets an attacker steal every token a user deposits.

**Solution.** Sparktest is a property-testing library written in Fe. You state a rule; it tries many inputs, favouring edge values such as zero and the maximum. When the rule breaks, it shrinks the input to the smallest one that still breaks it and prints a seed that reproduces the failure exactly. It runs on EVM tests, native code and WebAssembly, calls deployed contracts and tests sequences of calls.

**Walkthrough.** Open the demo, pick *Buggy sort*, press Run. Sparktest finds an unsorted input, shrinks it in 132 steps to `[1, 1, 1, 0]`, and Replay reproduces it from the seed. Every demo result is identical on WebAssembly, native and EVM.

**Before / after.** Three unit tests of a vault with a rounding bug pass. One property finds it and shrinks it to a vault of 3 assets and 1 share, with a deposit of 1.

Proof in the repo: five planted bug classes found, an ERC20 fixture checked through contract calls, a panic shrunk to its exact boundary, expectations written before running.

## Fe-specific highlight (for the submission form)

Sparktest's runner is effect-polymorphic (`uses P::E`), so one `check` accepts pure properties and properties that call contracts, while its core stays effect-free and per-backend shims handle the `Evm` and `Host` entry effects. It uses const-generic arrays and trait-based generators, and turns a contract panic into a value through `try_call`. The same seed gives identical results on sonatina, native and WebAssembly, so the library doubles as a cross-backend consistency check for the compiler.

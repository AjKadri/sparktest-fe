# Design notes: recovering from panics in properties

Problem: a property whose code panics (overflow, division by zero) used to end the whole test with no report, because a panic reverts the test itself (sonatina), aborts the process (native) or traps (wasm).
Expected results are in [EXPECTATIONS.md](EXPECTATIONS.md) (section "L7b"); measured results are in [PROOF.md](PROOF.md) ("Panic recovery").

## The design spike (sonatina)

Idea: run each property evaluation inside a contract called through `evm.try_call`, so a panic is a failed call whose revert data says why.

| option | what I tried | result |
|---|---|---|
| (a) a generic harness contract | `pub contract Harness<P: Fn(u256) -> bool> { ... }` | does not parse: `error[1-0001]: contract definition requires a body` (`expected {`). Fe 26.7.0 contracts cannot be generic |
| (b) a small user-written harness with one `recv` arm per property | a contract whose arm calls a generic helper: `Run { id, words } -> u256 { run_prop(prop, words) }` | works. A generic function called from a `recv` arm compiles, and a message type defined in the library ingot (`Isolated`) can be answered by a contract in the user's ingot |
| (c) anything better | a single generic message carrying the input as `DynArray<u256>` words, decoded inside the arm by a new `Decode` trait (the inverse of `Encode`) | this is (b) plus a library-supplied message and decoder, so the user's arm is one line per property. I found no way to avoid writing the contract itself |

**Chosen: (b) with the library-supplied message.** The user writes one contract (about 8 lines) with one line per property; Sparktest supplies `msg Isolated`, `run_prop`, the `Decode` trait for every built-in generator except `Seq`, and `check_isolated`.

How the reason is read: `CallOutcome::returndata()` returns a `MemSpan`; `read_be<u32>(0) == 0x4e487b71` identifies `Panic(uint256)` and `read_word(4)` is the code (`0x11` overflow, `0x12` division by zero). An empty revert is reported as "failed without data" (for example out of gas).

Cost of one isolated evaluation (encode the input, call the harness, decode the result), measured on sonatina: 1,576 gas when the property holds, 1,585 when it returns false, 1,516 when it panics.

## Native and wasm

No harness is needed: a panic aborts the process (native, exit status 134, stderr `panicked: arithmetic overflow`) or throws through the `__fe_revert` import (wasm). Both recover by replay: bisect the case limit to the first case that fails, take that case's input, and shrink by evaluating candidates one at a time. The candidates come from the same `Shrink` code, so the result matches the EVM path step for step.

# Expected minimums (written BEFORE the proof suites were run)

This file is committed before any L4 property was executed, so the results in PROOF.md cannot be fitted to the
outcomes. Every expectation below is a prediction from reading the planted code, not from running it.

Sparktest shrinks greedily (take the first simpler candidate that still fails, repeat), so it finds a *local*
minimum, not necessarily the global one. Where a global minimum can be computed independently, it is given.

## Part 1: planted bugs (pure functions; sonatina and native)

| id | bug | property | expected minimum |
|---|---|---|---|
| a | vault `deposit` rounds minted shares UP (should round down) | deposit x into a vault (assets A, shares S), then withdraw the minted shares: never get back more than x | an almost-empty vault: all of A, S, x <= 10. Independent brute force (Python, not Sparktest) over A,S,x in 1..40 gives the global minimum (A=3, S=1, x=1); it also shows 8,575 failing triples, so a greedy local minimum may differ but must stay small. Fixed version: passes 256 cases |
| b | fee = amount * bps / 10000 computed multiply-first in u64 | with bps <= 10000, `amount.checked_mul(bps)` must not overflow (overflow is a reported failure, not a panic) | amount * bps >= 2^64 and locally minimal: `(amount - 1) * bps < 2^64`. With bps <= 10000 the smallest possible amount is 1,844,674,407,370,956. Fixed version (split multiply) passes |
| c | withdraw subtracts (wrapping) before checking balance >= amount | if withdraw reports success then amount <= balance and new balance = balance - amount | (balance 0, amount 1). Fixed version passes |
| d | pack(a, b) of two u128 into a u256 shifts `a` by 127 instead of 128 | unpack(pack(a, b)) == (a, b) | (a = 1, b = 0). Fixed version passes |
| e | index check `i <= len` where `i < len` is needed | in_bounds(i, len) implies i < len | (i = 0, len = 0) with u8 inputs. Fixed version passes |

Expectation for both backends: identical shrunk values, case numbers and seeds (as in scripts/cross-check.sh).

## Part 2: ERC20 through contract calls (sonatina only)

Contract: `crates/fe/tests/fixtures/fe_test/erc20.fe` of the Fe v26.7.0 clone, vendored unchanged. By reading it:
`transfer` and `transferFrom` return `false` on insufficient balance or allowance (they do not revert), and `mint` is
open to anyone. So "reverts" in the task text is checked as "does not succeed: returns false or reverts, and changes nothing".
Actors are 4 proxy contracts, so the token sees four different `msg.sender`s. Initial state: actor 0 receives the supply and
sends 250 to actors 1, 2 and 3 in setup.

| property | expected on the unchanged contract |
|---|---|
| transfer(amount <= balance) succeeds and moves exactly amount | passes |
| transfer(amount > balance) does not succeed and changes nothing | passes |
| transfers never change totalSupply | passes |
| approve then transferFrom(amount <= allowance) lowers the allowance by exactly amount | passes |
| transferFrom(amount > allowance) does not succeed | passes |

Planted bug (examples/erc20-buggy, ONE bug): in `transfer`, when `to == sender` the debit is skipped but the credit is
applied (a self-transfer mints). Expected minimum: sender = receiver = actor 0, amount = 1 (actor 0 holds the most, so
the shrinker can keep a funded sender); the failing property is "transfer(amount <= balance) moves exactly amount".
Case count 64 per property.

## Part 3: std (sonatina and native)

Expected to PASS, as std is widely used: integer saturating/wrapping/checked helpers vs a widened-u256 model;
sort (core::sort) output sorted and a permutation of the input; ABI round trip decode(encode(x)) == x for integers and
tuples. If any fails and the property is right, it is reduced to a repro and reported as a candidate Fe bug (not filed).

## L4.1 amendments (2026-11-22, written BEFORE steps 2 and 3 were run)

The rows above are unchanged. These expectations cover the L4.1 gaps.

### Step 2: `Index<N>` (a value in 0..N-1) and the ERC20 self-transfer bug

- `Index<N>` values are always `< N`; about 1 draw in 4 is an edge (0 or N-1); the rest are uniform. Within 256 cases both 0 and N-1 appear
  for N = 4, and shrinking `Index<10>` against the false property `i < 3` ends at exactly 3.
- ERC20 planted self-transfer bug, actors chosen with `Index<4>` for sender and receiver, amount `u16`:
  - **Original pre-registered minimum (unchanged): sender 0, receiver 0, amount 1.**
  - **Honest prediction, from reading the shrinker:** the failure needs sender == receiver, and a tuple shrinks one component at a time,
    so a pair of equal non-zero indices such as (3, 3) is a local minimum (changing either index alone makes the transfer a normal one,
    which passes). I therefore predict the result is `(a, a, 1)` with `a` in 0..3 and the amount exactly 1, and that it is exactly
    (0, 0, 1) only if the first failing case already has sender = receiver = 0. Either outcome will be recorded as found, with no re-fitting.
    Properties P1 and P6 are expected to fail; P2 to P5 to pass.

### Step 3: `examples/rewards` (a contract that panics), checked through `try_call`

- Contract: `claim` computes `stake * RATE / SCALE` in `u64` with `RATE = 1000`, `SCALE = 10000`. The multiplication overflows (Panic 0x11,
  the call reverts) as soon as `stake * 1000 >= 2^64`. Smallest overflowing stake (computed independently): **18446744073709552**
  (`18446744073709552 * 1000 >= 2^64` and `18446744073709551 * 1000 < 2^64`).
- Property: for every `stake <= MAX_STAKE` (`MAX_STAKE = 2^63`), staking then claiming through `evm.try_call` succeeds. The failure set is
  monotone (every stake from 18446744073709552 up to MAX_STAKE fails), and the last shrink candidate is `x - 1`, so the expected shrunk
  value is exactly **18446744073709552**. Fixed version (divide first, split the multiply): passes all cases.
- Direct vs `try_call`: the same property written with the plain `evm.call` is expected to make the whole test revert with Panic(0x11)
  (no Outcome, no shrink, no seed), as the existing probe `probe_overflow_in_property_reverts_whole_run` already shows for a pure overflow; through `try_call`
  the failure is a value that is found, shrunk and reported with its seed.

### Step 4: other ERC20 sources

- Prediction: the Fe v26.7.0 docs sources (`docs/`, `docs/language/*.md`) contain no ERC20 or token example contract; the ERC20s in the clone are test fixtures
  (`crates/fe/tests/fixtures/fe_test/erc20.fe`, `crates/codegen/tests/fixtures/erc20.fe`, `crates/fe/tests/fixtures/build_foundry/erc20.fe`) and the std helper
  `ingots/std/src/evm/erc20.fe` (a client library, not a token). If the search proves this wrong, the found example is vendored unchanged and gets the same 6 properties.

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

## L6 stateful testing (2026-11-22, written BEFORE steps 2 to 5 were run)

Rows above are unchanged. A "command" below is `(kind, a, b, amount)`; sequences are shrunk by: halve the length, drop one command, then
shrink single commands. Components of different commands that must stay equal for the bug to show (the same account in three commands)
cannot be shrunk one at a time, so such indices can stop at a local minimum (as in L4.1); lengths and amounts are expected exact.

### Seq<C, N> unit test
- Property "no two adjacent commands are equal" over `Seq<Index<3>, 8>`: expected minimal failing sequence has **length exactly 2** and two equal
  commands `(a, a)`; `a` is 0 only if the first failing sequence already had a = 0 (a pair of equal non-zero values is a local minimum).

### Pure bank model (3 accounts; commands deposit / withdraw / transfer; sonatina and native)
- Invariant after every command: total deposited - total withdrawn == sum of balances.
- Planted bug: a withdrawal that takes an account to exactly 0 sets a flag; the account's next deposit is credited twice (the books count it once).
- Expected minimal failing sequence: **length 3**: `deposit(a, 1)`, `withdraw(a, 1)` (withdraw clamps to the balance), `deposit(a, 1)`, i.e. commands
  `(0, a, 0, 1), (1, a, 0, 1), (0, a, 0, 1)` with the same account `a` in all three (`a` in 0..2; a = 0 only if the first failing sequence already used account 0 throughout).
  No sequence of length 1 or 2 can fail (a single call cannot reveal it). The unused field `b` shrinks to 0. Fixed version: passes 256 cases.
- Sonatina and native must find identical sequences (same seed).

### ERC20 stateful (sonatina only): the ERC20 test fixture from the Fe compiler repo, compared with a pure reference model after every call
- Setup per case: fresh token with supply 16 to actor 0, which sends 4 to each other actor (every actor holds 4); amounts are taken `% 9` (0..8), so a full-balance
  transfer (amount 4) is common. N = 8, 64 cases, `Index<4>` actors.
- Unchanged fixture: expected to **pass** all 64 cases (the model equals the contract: balances, touched allowance, totalSupply, sum of balances == totalSupply).
- Planted bug (`examples/erc20-stateful-bug`, in `Transfer` only): when a transfer takes the sender to exactly 0, the sender is flagged; the next transfer INTO a flagged
  account is credited twice. A single call cannot reveal it.
- Expected minimal failing sequence: **length 2**: `Transfer(a -> b, 4)` then `Transfer(c -> a, 1)` with `b != a`, `c != a`; amounts exactly (4, 1) (4 is the
  full balance and cannot shrink; 1 is the smallest credit). `a` is shared by both commands, so it may stop at a non-zero local minimum; `b` and `c` are expected
  to be the smallest indices different from `a`. Not expected: length 3 or more.

### Demo (5th property = the pure bank model)
- The shrunk sequence (all words, length included) is identical on wasm, native and sonatina for the same seed; so are case and shrink steps.

## L7a vacuity guards and the Fe Guide ERC-20 (2026-11-22, written BEFORE the runs of this step)

Rows above are unchanged.

### Vacuity guards
- A property run over contracts or command sequences counts calls attempted, calls that succeeded and (stateful) commands executed per kind. A run that PASSES is reported
  as vacuous (not as a pass) when no call succeeded where success is expected, or when a command kind was never executed across the whole run. A run that fails is
  reported as a failure as before (a failure is information whatever the counts).
- Properties about failing calls (transfer over the balance, transferFrom over the allowance) must not be flagged merely because no call succeeds; their guard is "calls were attempted".
- Demo: a deliberately vacuous property ("if the transfer succeeds it moves exactly the amount", with every amount above the balance) PASSES unguarded and is reported
  VACUOUS (reason: no call succeeded) with the guard. Every existing ERC20 and stateful property (the ERC20 test fixture, the Guide's CoolCoin, the planted copies) is expected NOT to be vacuous.

### The Fe Guide ERC-20 (CoolCoin) at https://fe-lang.org/examples/erc20/
- Expected to compile unchanged on Fe 26.7.0 and to pass its three own tests; expected to pass the 6 ERC20 properties and the stateful model check
  (differences from the compiler-repo fixture: `transfer`/`transferFrom` revert on a shortfall instead of returning `false`; `mint` requires the MINTER role, granted to the `owner` init argument).
- Mutation test: 10 single-change mutants of the vendored source. Setup: the owner is the test contract (it holds MINTER), supply 12, each of 4 actors holds 4. Properties P1 to P6 as in PROOF.md,
  64 cases each; the stateful run uses 8-command sequences over Transfer, Approve, TransferFrom, Mint (64 cases). A mutant counts as caught when any property fails.

| mutant | single change | expected | by which property |
|---|---|---|---|
| M01 | `transfer` credits the receiver `amount + 1` | caught | P1 (moves exactly amount) and P6 (balances sum to supply), and stateful |
| M02 | the `from_balance >= amount` assert in `transfer` removed | MISSED: equivalent mutant (Fe's checked subtraction still reverts, with Panic(0x11) instead of the message; properties see only success or failure) | none |
| M03 | `TransferFrom` swaps `from` and `to` in the inner transfer | caught | P4 (transferFrom moves exactly amount) and stateful |
| M04 | `spend_allowance` no longer lowers the allowance | caught | P4 (allowance drops by exactly amount) and stateful |
| M05 | `transfer` writes the receiver's credit first and then the debit computed from the stale sender balance (a self-transfer destroys `amount`) | caught | P1 (self-transfer moves nothing), P6, and stateful |
| M06 | balance check `>=` becomes `>` (the full balance cannot be sent) | caught | P1 (amount equal to the balance) and stateful |
| M07 | allowance check `>=` becomes `>` (the full allowance cannot be spent) | caught, less certainly (needs amount == allowance, reached through edge values such as an allowance of 0) | P4, and stateful |
| M08 | the Transfer event is no longer emitted in `transfer` | MISSED: the properties read balances, allowances and supply, and cannot observe logs | none |
| M09 | `mint` no longer increases `total_supply` | caught only by the stateful run (P1 to P6 never mint) | stateful (Mint command: totalSupply compared with the model) |
| M10 | `mint` no longer requires the MINTER role | MISSED: only the owner (who holds MINTER) ever calls `mint`; detecting it needs a non-owner caller | none |

Not covered by any command, so no mutant of them is claimed: `burn`, `burnFrom`, `increaseAllowance`, `decreaseAllowance`, `name`, `symbol`, `decimals`.

### L7a erratum (written before any mutant result was interpreted)
The mutation-test setup sentence above ("supply 12, each of 4 actors holds 4") was inconsistent (4 x 4 is 16). The first implementation used supply 12 with 3 per actor, which drains the owner's
balance to exactly 0 in the last setup transfer; mutant M06 (balance check `>=` becomes `>`) then reverted INSIDE THE SETUP and every M06 test died there, so M06 would have been "caught" by the setup instead
of by a property. Only pass/fail counts of that first run were looked at. The setup is now: supply 13 minted to the owner (the test contract, which holds MINTER), 3 sent to each of 4 actors, the owner keeps 1,
and the conservation property and the stateful sum include the owner's balance. The mutant table above is unchanged.

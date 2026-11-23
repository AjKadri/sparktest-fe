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

## L7b panic recovery (2026-11-22, written BEFORE the runs of this step)

Rows above are unchanged. Goal: a property whose code panics is reported and shrunk like any other failure, through NEW APIs only (`check` keeps its behaviour and results).

### Planted properties (same two on every path)
- **overflow**: input `x: u64`; the property computes `x * 1000` in `u64` (checked arithmetic) and returns `x * 1000 / 1000 == x`. It panics with `Panic(0x11)` (arithmetic overflow) exactly when
  `x * 1000 >= 2^64`. The failure set is every `x >= 18446744073709552` (`18446744073709552 * 1000 >= 2^64`, `18446744073709551 * 1000 < 2^64`; computed independently). The set is monotone and the last
  integer shrink candidate is `x - 1`, so the expected minimum is exactly **18446744073709552**, reason "panicked: arithmetic overflow (0x11)".
- **divzero**: input `(a: u32, b: u32)`; the property returns `a / b * b <= a`. It panics with `Panic(0x12)` (division by zero) exactly when `b == 0`, whatever `a` is. Expected minimum: **(a = 0, b = 0)**
  (`a` shrinks to 0 independently; `b` is already 0), reason "panicked: division by zero (0x12)".
- **a normal false-returning property** (the existing `x < 1000` over `u256`) must give the same result through the isolated path as through `check` (shrunk to exactly 1000), reason "returned false".

### Backends and agreement
- Same seed on every path gives the same input stream, so the first failing CASE INDEX, the shrunk input and the NUMBER of shrink steps are expected to be identical on sonatina (isolated through `try_call`),
  native (a replay driver script that bisects the case limit to the first aborting case and shrinks by replaying single-case runs) and wasm (the page, which catches the trap and replays).
  The reason (panicked 0x11 / 0x12, or returned false) must agree wherever the platform exposes it: sonatina reads the revert data, wasm reads the `__fe_revert` payload; native only learns that the process aborted
  (stderr text `panicked: arithmetic overflow` / `division by zero` is expected, to be checked).
- Expected costs: one isolated evaluation costs a contract call (hundreds to a few thousand gas); the whole isolated run stays well below the 1e9 per-test cap.

### What is expected NOT to be covered by the new paths (stated before the runs)
- Properties that loop forever or run out of gas (a call that runs out of gas is a failed call on sonatina, reported as a failure of unknown reason).
- A panic in the generator or the shrinker (they run in the test, not in the harness).
- Pure-code properties on sonatina need a harness contract (user-written, one `recv` arm per property); native and wasm need no harness.

## L7c joint shrink, adversarial Mint, bounded amounts (2026-11-22, written BEFORE any run of this step)

Rows above are unchanged. Results that change become dated amendment rows with the commit; earlier values stay visible (frozen in `proof/history.json`).

### Step 1: joint shrink
Definition (flattened `Encode` words `w`, leading `skip` words excluded; for `Seq` the length word is excluded). "Simpler than": `a` is simpler than `b` when `sum(a) < sum(b)` (saturating) or the sums are equal and `a` is
lexicographically smaller. A joint candidate is accepted into the list only if it is strictly simpler, decodes back to the same words (it fits the type's width), and differs from the original, so shrinking always terminates.
Joint candidates come AFTER all component-wise candidates (so every previous shrink step is unchanged; joint steps only happen where the old shrinker was stuck), in this order:
(a) every word halved; every nonzero word minus 1; (b) every group of equal nonzero words set to 0, to half, to minus 1; for `Seq` also every group of equal words in the same column of the commands;
(c) redistribution: for each pair i < j with `w_i > 0`, move `d` from `w_i` to `w_j` (sum preserved, lexicographically smaller), for d = w_i, w_i/2, w_i/4, ..., 1.
Termination test: `max_shrinks = 1,000,000` on adversarial properties must end, far below that bound.

Predicted changes of EXISTING results (everything not listed here is predicted UNCHANGED, including every shrink-step count):

| result | before | predicted after |
|---|---|---|
| cross-check scenario `arr_u64x4_sum` (seed 1003) | shrunk 0,0,10,0 in 14 steps | **0,0,0,10 in 15 steps** (one redistribution), identical on sonatina and native |
| ERC20 fixture planted bug, `Index<4>` actors, P1 | (3, 3, 1), local minimum | **(0, 0, 1)** (equal components set to 0 together) |
| ERC20 fixture planted bug, raw `u8 % 4` actors | P1 (21, 125, 1), P6 (26, 190, 1) | exact values NOT predicted (redistribution moves the pair); criterion: a self-transfer (same actor class), amount 1, indices lexicographically at most (21, 125) and (26, 190) |
| `fee_buggy`, seed 5003 | amount 145249953336295683, bps 127 (local minimum) | **(1844674407370956, 10000)**: redistribution raises bps to its useful maximum 10000 (amount drops by 9873), after which amount shrinks to the global boundary 1844674407370956; step count changes (not predicted) |
| stateful `bank_buggy`, seed 8002 (proof) | commands on account 1, case 137, 48 steps | accounts all **0**: `deposit(0,1); withdraw(0,1); deposit(0,1)`, case 137 (unchanged), **49 steps** (one column-group step) |
| demo property `bank_sequence`, seed 55 | commands on account 2, case 76, 43 steps | accounts all **0**, case 76, **44 steps** |
| quickstart vault, seeds 1 to 12 | 10 of 12 reach (3, 1, 1); seeds 1 and 12 stop at (18, 1, 271) and (8, 1, 41) | at least 10 of 12; seeds 1 and 12 may now reach (3, 1, 1) (not predicted individually) |
| `buggy_sort` (demo and cross-check) | [1, 1, 1, 0] | unchanged: I checked all redistributions of [1, 1, 1, 0] by hand; each gives a sorted output, which holds |

Predicted UNCHANGED: every single-integer result, `pair_sum` (0, 10), `capped_mint` (0, 1001), vault (3, 1, 1), withdraw (0, 1), pack (1, 0), bounds (0, 0), transfer struct (0, 501), the rewards boundary, the isolated overflow
and divzero results ((0, 0)), and all passing runs.
Gas: passing runs unchanged; runs that fail and shrink pay one extra joint round at the end (more shrink evaluations), expected at most about 2x on the failing suites and far below the 1e9 per-test cap.

### Step 2: adversarial Mint
The stateful command set gets `Mint` from ANY actor (kind 4: actor `a` tries to mint to `b`), besides the owner's mint (kind 3). The model predicts: on the Fe Guide's CoolCoin an actor's mint fails (no MINTER role, no state change);
on the compiler-repo ERC20 test fixture it succeeds (mint is open). Expected: **M10 (mint without the MINTER check) is now caught by the stateful run**; every other mutant outcome is unchanged; mutation score
**8 of 10** caught (M02 equivalent and M08 event-only stay missed); the unchanged CoolCoin and the fixture still pass the stateful check, not vacuous, with all five command kinds executed. Command kinds are generated by `Index<5>`,
so the generated sequences change (cases and shrink steps of the stateful runs are not predicted).

### Step 3: bounded amounts
Amounts taken modulo a balance become `Index<N>` (P1 and P6: N = every actor's balance + 1, that is 251 for the fixture and 4 for CoolCoin; P4: the allowance is a plain `u16` and the amount an `Index<N>` clamped to
min(allowance, balance)). Predicted counterexamples show the real amount: M06 via P1: **amount 3** (was "input 15099"); M01 via P1: amount 0; M05 via P1: amount 1; M03 and M04 via P4: owner 0, spender 0, allowance 1, amount 1
(M03: to 1); M07 via P4: allowance 0, amount 0. Which properties catch which mutants is predicted unchanged apart from M10.

### L7c results (amendment rows, 2026-11-22; measured at commit a99f06d, after the pre-registration commit 965cb2a)
Rows above are not edited. "expected" is the prediction written above; "found" is the measured value.

| result | before | expected | found | as expected |
|---|---|---|---|---|
| cross-check `arr_u64x4_sum` | 0,0,10,0 in 14 steps | 0,0,0,10 in 15 steps, identical on both backends | 0,0,0,10 in 15 steps; CROSS-CHECK IDENTICAL (11/11) | yes |
| ERC20 fixture bug, `Index<4>`, P1 | (3, 3, 1), 16 steps | (0, 0, 1) | (0, 0, 1), 9 steps | yes |
| ERC20 fixture bug, `Index<4>`, P6 | (0, 0, 1), 16 steps | unchanged shape | (0, 0, 1), 8 steps | yes |
| ERC20 fixture bug, raw `u8`, P1 | (21, 125, 1), 13 steps | same actor class, amount 1, indices at most (21, 125) | (1, 1, 1), 40 steps | yes (criterion met; not (0, 0, 1)) |
| ERC20 fixture bug, raw `u8`, P6 | (26, 190, 1), 20 steps | same actor class, amount 1, indices at most (26, 190) | (0, 0, 1), 22 steps | yes |
| `fee_buggy`, seed 5003 | (145249953336295683, 127), 32 steps | (1844674407370956, 10000) | (1844674407370956, 10000), 187 steps | yes (steps not predicted) |
| `bank_buggy`, seed 8002 | account 1, case 137, 48 steps | accounts 0, case 137, 49 steps | accounts 0, case 137, 49 steps | yes |
| demo `bank_sequence`, seed 55 | account 2, case 76, 43 steps | accounts 0, case 76, 44 steps | accounts 0, case 76, 44 steps; wasm = native = EVM for all 6 demo properties | yes |
| quickstart vault, seeds 1 to 12 | 10 reach (3, 1, 1); seeds 1, 12 stop at (18, 1, 271), (8, 1, 41) | at least 10 of 12 | exactly 10; seeds 1 and 12 still stop at (18, 1, 271) and (8, 1, 41) | yes (no improvement either) |
| `buggy_sort`, every single-integer result, `pair_sum`, `capped_mint`, rewards, isolated, passing runs | as before | unchanged | unchanged | yes |
| gas of PASSING runs | as before | unchanged | **not unchanged**: +129 gas on most (code of `check` grew), up to +2.2% (`std_abi_tuple` 274,897 to 281,073; `std_int_u32` 323,629 to 329,783) | **no** |
| gas of FAILING runs | as before | at most about 2x | vault 1.6x, withdraw 1.4x, bounds 1.9x, pack 1.02x; **`fee_buggy` 6.6x (17.6M to 116.1M), `bank_buggy` 20.8x (17.7M to 369.5M, 37% of the 1e9 cap), ERC20 raw P1 2.4x**; ERC20 `Index<4>` P1 and P6 about 0.6x (cheaper) | **no** (prediction too low) |
| demo wasm size | 46,157 bytes | not predicted | 73,481 bytes (+59%) | n/a |

Step 2 (adversarial Mint):

| result | expected | found | as expected |
|---|---|---|---|
| M10 | caught by the stateful run | caught: `Mint(actor 0 -> to 0, 0, NOT the owner)`, 1 command, calls accepted / attempted 51 / 66 | yes |
| mutation score | 8 of 10 (M02, M08 missed) | 8 of 10 caught, 2 missed (M02, M08) | yes |
| unchanged CoolCoin and fixture pass the stateful check, not vacuous, all five kinds executed | yes | CoolCoin 64 cases, kinds 61, 38, 37, 34, 69, accepted / attempted 115 / 239 (was 165 / 239: refused adversarial mints count as attempted, not accepted); fixture 64 cases, kinds 64, 39, 51, 29, 65, 183 / 248; none vacuous | yes |
| every other mutant outcome unchanged | yes | **M03 and M04 are no longer caught by the stateful run in 64 cases** (still caught by P4, so the score is unchanged); recorded as "partly" | **no** |
| (not predicted) the planted ERC20 stateful bug | found within 64 cases as before (case 21) | **64 cases found nothing**; with 128 cases found at case 102, shrunk to the same 2-call shape `Transfer(0 -> 1, 4); Transfer(1 -> 0, 1)` in 9 steps. The suite uses 128 cases for that run. | **no** |

Step 3 (bounded amounts), the counterexamples as predicted: M06 via P1 amount 3, M01 amount 0, M05 amount 1, M03 (owner 0, spender 0, to 1, allowance 1, amount 1), M04 (owner 0, spender 0, to 0, allowance 1, amount 1),
M07 (allowance 0, amount 0): all **yes**. The Pr event now carries 5 shrunk words and 3 original words (an event holds at most 16 fields).

Joint shrink termination test (`shrinking_terminates_with_a_huge_step_budget`, max_shrinks 1,000,000): passes on sonatina and native; every run ended in under 10,000 steps.

## L7d gas-safe shrinking (2026-11-22, written BEFORE any run of this step)

Rows above are unchanged. Results that change become dated amendment rows with the commit.

Cause (read from the code, not yet measured): in L7c every nested tuple, array and `Seq` shrinker appends its own joint candidates, and `count_candidates` (called by every composite
`shrink_step`) walks all of them again, so a `Seq` of tuples pays a quadratic enumeration cost per call. The greedy loop already tries every component candidate before any joint
candidate and returns to the components after each joint step, so the ORDER of exploration is the order the brief asks for; what changes in step 1 is WHERE joint candidates live:
only at the top level (a separate `joint_step` method, default none), tried as a finishing pass after the component candidates reach a fixed point, repeating while anything improves.

### Step 1 predictions
| case | L7c gas | predicted after | why |
|---|---|---|---|
| `bank_buggy` seed 8002 (`Seq` of tuples) | 369,471,853 | **at most 60,000,000** (at least 6x cheaper; pre-L7c was 17.7M) | nested joint enumeration disappears |
| `fee_buggy` seed 5003 (a flat `(u64, u64)`) | 116,137,403 | **within +-15% of 116M** (no real change) | a flat tuple has no nested joint candidates; its cost is the 187 accepted steps, which stay |
| ERC20 raw `u8` P1 (a flat 3-tuple) | 159,818,273 | **within +-15% of 160M** (no real change) | same |
| ERC20 stateful planted bug (128 cases) | 563,967,611 | at most 300,000,000 | nested tuples inside `Seq` |
| minima | as in the L7c table | **unchanged for every result** (the top-level joint candidates cover the words of nested groups; `bank_buggy` accounts all 0, 49 steps may differ by a few) | |
| step counts | as in L7c | unchanged for flat tuples and arrays (same candidate sequence); may differ for `Seq`-based runs (not predicted) | |
Cross-check stays IDENTICAL on both backends.

### Step 2 design (stated before the code)
Core stays effect-free. A new `check_with(cfg, prop, stop)` takes a second closure `stop: Fn() -> bool`, polled before EVERY shrink evaluation (`uses (P::E, B::E)`); `check` is `check_with` with a stop that is never true, so its behaviour
and gas are unchanged apart from the polling call. `sparktest_evm::check_gas(cfg, prop)` passes `|| evm.gas() < margin` (default margin 50,000,000; `check_gas_with_margin` to choose). On a stop, the loop returns the best input so far and
`Outcome::Fail` carries a new field `early: bool` (true = shrink stopped early because gas ran low). `assert_holds` reverts with a new error `PropertyFailedEarly` (same fields), so the old selector still decodes; the decoder prints "shrink stopped early (gas)".
Native has no gas: `early` is always false there. Choice against an effect like `Tally`: an effect would have to be provided by every caller of `check`; a closure is provided only by the shim that knows about gas.
`Summary` and `Full` get an `early` field.

### Step 3 prediction
A failing property that burns about 1.5M gas per evaluation, over a `u64` that needs thousands of shrink evaluations, exceeds the 1e9 cap with plain `check` (test halts with `OutOfGas`, no report); with `check_gas`
it returns `failed == 1`, `early == 1`, a shrunk input that still fails the property, strictly smaller than the original but not minimal (above the true minimum 1000), and at least the margin of gas is left.

### Step 4 prediction
Only the runs listed in Step 1 change gas; every other proof row keeps its minimum and moves by under 1% in gas (the per-evaluation stop poll costs a few gas, only in suites that switch to `check_gas`).

### L7d results (amendment rows, 2026-11-22; measured after the pre-registration commit e8b1ed4)
Rows above are not edited. Gas is the `gas` column of docs/PROOF.md.

| case | before joint shrinking (L7b) | L7c | expected after L7d | found after L7d | as expected |
|---|---|---|---|---|---|
| `bank_buggy` seed 8002 | 17,737,382 | 369,471,853 | at most 60,000,000 | **18,617,705** (1.05x of before joint shrinking); same minimum (accounts 0, case 137, 49 steps) | yes |
| `fee_buggy` seed 5003 | 17,614,067 | 116,137,403 | within +-15% of 116M | **114,304,157** (-1.6%; still 6.5x of before joint shrinking); same minimum (1844674407370956, 10000), same 187 steps | yes |
| ERC20 raw `u8` P1 | 66,384,537 | 159,818,273 | within +-15% of 160M | **159,523,204** (-0.2%; 2.4x of before joint shrinking); same minimum (1, 1, 1), same 40 steps | yes |
| ERC20 stateful planted bug (128 cases) | 99,283,665 (64 cases) | 563,967,611 | at most 300,000,000 | **75,992,616**; same 2-call minimum, same case 102 | yes |
| every minimum and every step count in docs/PROOF.md | | | unchanged | unchanged (only the gas column and, for runs that shrink, the calls accepted / attempted counters differ, because fewer evaluations run) | yes |
| other proof rows | | | under 1% gas change | passing rows moved by less than 0.1% (a few hundred gas), except `pack_fixed` +6.5% (260,998 to 277,932) and `std_sort_heap` +0.2% | **partly** (pack_fixed is above the predicted 1%; not investigated) |
| cross-check | | | IDENTICAL | IDENTICAL (11/11) | yes |

Why the flat cases did not get cheaper: the two flat ones (`fee_buggy`, ERC20 raw P1) already explored the component candidates first; their extra cost is the accepted joint steps themselves (187 and 40 steps), which stay.
The nested ones (`Seq` of tuples) got cheap because joint candidates were enumerated at every nesting level, and `count_candidates` walked them again on every call.

Step 2/3: `check_gas` (margin 50,000,000). The test `expensive_shrink_stops_early_instead_of_running_out_of_gas` (a property costing about 20M gas per evaluation) passes with `early = 1`, a shrunk input that still fails (235, from 8446975623834719884; the minimum is 1), and 43,456,686 gas left (below the margin, within one evaluation of it as predicted).
The control, plain `check` on the same property and seed: `Test halted: OutOfGas(Basic) (gas: 1000000000)`.

## L9 std hunt, held-out mutants, formatting, CI (2026-11-23, written BEFORE any run of this step)

Rows above are unchanged. The library (`sparktest/`, `sparktest-evm/`, `sparktest-native/`) is frozen: this step adds tests, generated test files for new mutants, formatting and CI only.

### Step 1: std hunt. Every property below is predicted to PASS (a failure is first suspected to be a mistake in our property; only then reduced to a repro)
Sonatina and native wherever the API exists on both (`core::*` on both; `std::evm::random` is sonatina only). 64 cases per property unless a loop makes that expensive.
| area | properties (all expected to pass) |
|---|---|
| a) `core::map::HashMap<u256, u256>` | one stateful property over `(prefill, Seq<command, 12>)`: `prefill` (0..39) distinct keys are inserted first so the table grows past its 14-entry first capacity (16 slots, 7/8 load) even when the commands are few; commands: insert (new key or overwrite), get, remove (then possibly re-insert), contains_key, clear; keys come from 24 indices spread as `k * 0x10000000000000001`. After EVERY command: `len()` equals the model's count, `is_empty()` agrees, and for every key index the contents (`contains_key`, `get`) equal the reference model (two fixed arrays: present flags and values). `insert` returns the old value exactly when the model has one; `remove` returns the stored value. Expected: pass on both backends |
| b) `core::fixed` (`Wad` = `UFixed<18>`, `Fixed<18>`, `UFixed<27>`) | 12 properties with raw values below 2^128 so a widened `u256` model is exact: raw round trip; `from_int`/`floor_int`/`ceil_int`; `(a + b) - b == a`; `mul` equals `a*b/10^18`; `mul_up` equals the ceiling; `div` equals `a*10^18/b`; `div_up` equals the ceiling; `mul` is monotonic in either argument; `rescale` up and down and back equals the model (down floors); `sqrt` is the integer square root of `raw * 10^18` (`s^2 <= x < (s+1)^2`); signed `mul` and `div` truncate toward zero like the model; `Ord` agrees with raw order. Expected: pass on both backends |
| c) `core::text` | 8 properties: `parse_uint(decimal(x)) == x` (inputs include 10^k - 1, 10^k and 10^k + 1 for every k, the boundaries of the digit estimate in `decimal`); `decimal(x)` has exactly the digits of x; `parse_hex_uint(hex(x, 32)) == x` and `hex` has `2 * bytes` digits and `hex_upper` is its uppercase; `decode_hex(hex)` returns the bytes; `base64` and `base58` round trips (base58 with leading zero bytes); `split(sep)` then `concat` with the separator gives back the text, and the piece count is one more than the separator count; `UFixed::parse` of `"i.f"` built with `decimal` equals the model. Expected: pass on both backends |
| d) `std::evm::random` (sonatina only) | 5 properties: the same seed gives the same word stream (`KeccakRng`); `uniform(upper) < upper` for any `upper > 0`; `shuffle` returns a permutation of the input (same multiset); `chance(0, d)` is never true and `chance(d, d)` always; two different seeds give different first words. Expected: pass |
Expected result of the whole step: no bug found. If a property fails, the report says whether our property was wrong; a real divergence becomes a minimal repro in `repros/` marked "candidate Fe bug" in HANDOFF.md and is not filed.

### Step 2: held-out mutants (five NEW single changes of the Fe Guide CoolCoin; the test templates are not changed, only a new loop generates their files)
Written now, before any of them runs. Score is over the five; "caught by" lists the properties I expect to fail (P1 to P6 and the stateful check, 64 cases).
| mutant | single change | expected | by |
|---|---|---|---|
| H01 | `spend_allowance` RAISES the allowance (`current + amount`) instead of lowering it | caught | P4 (allowance 1, amount 1); stateful uncertain (M03 and M04 are no longer caught by it in 64 cases) |
| H02 | `transferFrom` debits the SPENDER (`store.transfer(from: ctx.caller(), ...)`) instead of the owner | caught | P4 (the owner's balance does not drop, or the spender's balance is too small and the call fails); stateful uncertain |
| H03 | `mint` credits the receiver `amount + 1` (off by one) | caught | P6 and stateful (the constructor mints through `mint`, so balances exceed `total_supply` from deployment) |
| H04 | `approve` stores the allowance under `(owner, owner)` instead of `(owner, spender)` | caught | P4 and P5 (and stateful) |
| H05 | `burn` no longer lowers `total_supply` | **missed** | none: no property or command calls `burn` (the burn commands are not in the stateful set); a probe will show the mutant really differs from the original |
Predicted held-out score: 4 of 5 caught. Predicted counterexamples: H01 owner 0, spender 0 (or any), allowance 1, amount 1; H04 allowance 1; H03 a first command or P6 with any input.

### Step 3: `fe fmt`
`fe fmt` exists in 26.7.0. Prediction: it rewrites many files (the repository has been written by hand without it), including the GENERATED ones, so the freshness check (generators then `git diff --exit-code`) will fail after formatting unless the generated files are formatted again after generation; the freshness part will therefore run `fe fmt` on the generated paths before the diff. Formatting must not change any result (test counts, PROOF.md, recordings): the run after it is expected to match the one before, apart from the demo wasm bytes only if formatting changes the compiled code (not expected).

### Step 4: CI
Cannot be run here (no push). Predicted portability issues, by reading the scripts (before the grep): BSD `sed -i ''` or `shasum` in `scripts/*.sh` and `*.py`, `date` flags, `mktemp` forms, `timeout`. CI is "added", not "passed": the README keeps "Tested on macOS (Apple Silicon) only" until a CI run has passed.

### L9 results, steps 1 and 2 (amendment rows, 2026-11-23; measured after the pre-registration commit 5caff69)
Rows above are not edited.

Step 1, std hunt: **no divergence found; every property passed, so there is no candidate Fe bug and nothing in `repros/`.**
| area | pre-registered | found |
|---|---|---|
| a) HashMap | one stateful property, pass | **two** (spread keys, and keys that all hash alike) over `Seq<(Index<6>, Index<24>, u8), 12>`, both pass on sonatina and native. Deviation: a `Seq` cannot sit inside a tuple input (`Seq` has no `Decode`, tuple shrinking needs it), so the planned `(prefill, Seq)` input became a "bulk insert of up to 39 fresh keys" command; growth past the first capacity of 14 was confirmed (a copy that failed above capacity 14 did fail) |
| b) `core::fixed` | 12 properties, pass | 12 properties, pass on both. One of MY properties was wrong first: `sqrt_full_range` called `mul_div_ceil((s+1)^2, ...)`, which overflows for `a` near `u256::max` and panics by design (`Panic(0x11)`); I restricted that check to `a <= 2^255`. Not a std bug |
| c) `core::text` | 8 properties, pass | 8 properties, pass on both (two casts needed `.downcast_truncate()`: compile errors in my code, not behaviour) |
| d) `std::evm::random` | 5 properties, pass | 5 properties, pass (sonatina only) |

Step 2, held-out mutants (`examples/coolcoin-heldout`; the test templates were not changed, only a loop that generates the five new files was added):
| mutant | expected | found | counterexample | as expected |
|---|---|---|---|---|
| H01 allowance raised | caught by P4; stateful uncertain | caught by P4 only (stateful did not catch it in 64 cases) | (owner 0, spender 0, to 0, allowance 1, amount 1) | yes |
| H02 transferFrom debits the spender | caught by P4; stateful uncertain | caught by P4 only | (owner 0, spender 1, to 0, allowance 1, amount 1) | yes |
| H03 mint +1 | caught by P6 and stateful | caught by P6 and stateful | (sender 0, receiver 0, amount 0) | yes |
| H04 approve wrong key | caught by P4, P5 (and stateful) | caught by P4, P5 and stateful | (owner 0, spender 1, to 0, allowance 1, amount 0) | yes |
| H05 burn leaves supply | missed by all | missed by all; two probes show it is a real difference (original supply 13 to 10 after burn 3, mutant stays 13) | - | yes |
Held-out score: **4 of 5 caught, 5 of 5 as predicted.** The stateful check catching only 2 of the 4 caught mutants is consistent with the L7c finding (its power fell with the fifth command kind), and no Burn command exists, which is why H05 is invisible.

## L10 generators, assume, regression seeds (2026-11-23, written BEFORE any run of this step)

Rows above are unchanged. Additive APIs only: `check`, its results, `web/recorded.json` and every number in docs/PROOF.md must stay unchanged, **gas included**.
Language facts established before this entry (probes in a scratch ingot, no repository code run): a trait can declare an associated effect row (`uses E`) and an associated type, and an impl can set `uses E = F::E`, so a combinator holding a closure can implement the generator trait; a closure stored in a struct field compiles when the method says `uses E`.

### Design (stated before the code)
- `trait Gen { uses E; type Value; fn generate<R: Rng>(self, rng: mut R) -> Self::Value; fn shrink(self, x, i) -> Option<Value>; fn contains(self, x) -> bool }`. `check_gen(cfg, gen, prop)` returns the same `Outcome<G::Value>`; `check_gen_with` takes the `stop` closure; `sparktest_evm::check_gen_gas` is the guarded one. No isolated variant (not a small step).
- Combinators: `between(lo, hi)` (inclusive, values `u256`, shrinks toward `lo` and never below it, edge bias on `lo`, `lo+1`, `hi-1`, `hi`), `one_of([..])` (shrinks toward earlier elements), `pair(a, b)` (independent), `dependent(a, f)` (generate `a`, then `b` from the generator `f(a)`; shrinking tries `b` first, then `a`, and only keeps a smaller `a` if `f(a')` still contains `b`), `map(g, f, inverse)` (`inverse` recovers the source value so shrinking works; `f` must be a bijection on the domain).
- `assume`: a property shape returning `Judged { Holds, Fails, Discard }`; `check_assume(cfg, prop)` and `check_gen_assume`. A discarded case is counted, not replaced (the case budget includes discards), and during shrinking a discarded candidate is not a failure. The result carries `Discards { cases, discarded }`; `assume_guard(result, max_discard_percent)` returns the existing `Verdict`: vacuous with reason 2 (existing "none succeeded") when no case was accepted, and with a new reason `VACUOUS_TOO_MANY_DISCARDS = 100` when more than the threshold (documented default 90) percent were discarded.
- Regressions: `Config::with_regressions([s1, s2, ...])` (at most 8). Each listed seed is run as a full run of `cfg.cases` cases (the same stream `Config::new(s)` would give) BEFORE the random cases of `cfg.seed`; a failing regression is reported with its own seed and the case index inside that seed's stream, so `Config::new(seed)` replays it.

### Predictions
Gas: with no regressions listed the new loop is predicted to be folded away by the optimizer (the count is a constant at the `Config::new` call site), so every gas figure in PROOF.md and recorded.json is predicted **exactly unchanged**. If it is not, I will report the difference and the cheapest way to restore it; I will not re-record to hide it.
| step | prediction |
|---|---|
| 1 range | `between(10, 1000)`, property `x < 500`: fails, shrunk exactly 500, every value inside [10, 1000] |
| 1 range floor | `between(100, 1000)`, property always false: shrunk exactly 100 (never below `lo`; the plain `u256` generator would reach 0) |
| 1 one_of | `one_of([5, 3, 9])`, property `x != 3 && x != 9`: shrunk exactly 3 |
| 1 map | `map(between(0, 100), x * 2, y / 2)`, property `y < 50`: shrunk exactly 50 |
| 1 dependent | `dependent(between(1, 1000), \|b\| between(0, b))`, property `amount <= balance`: 256 cases pass; property `amount <= balance / 2`: shrunk exactly (balance 1, amount 1), amount never above balance |
| 1 ERC20 valid transfer (new property, balances 700/100/200/0, amount drawn up to the sender's balance) | unchanged fixture: passes 64 cases and every call succeeds (accepted = attempted = 64), not vacuous; planted self-transfer bug: fails, shrunk sender == receiver, amount exactly 1 (the sender index may stop above 0: the generator's pair has no joint shrink) |
| 1 backends | the pure combinator tests pass on sonatina and native with identical shrunk values; `check_gen_gas` with the default margin equals `check_gen` (`early = 0`) |
| 2 weak premise | transfers with a raw `u32` amount and `assume(amount <= 250)`: discard rate predicted between 70% and 95% (I do not predict which side of 90%); reported, with the verdict |
| 2 vacuous | `assume(x == 12345)` over `u32`: nothing accepted, vacuous reason 2. `assume(x == 0)` over `u64`: more than 90% discarded but some accepted, vacuous reason 100 |
| 3 regression | the vault bug with the quickstart seed 25286971856348077807 listed and `with_cases(256)`: the buggy version fails with `seed == 25286971856348077807`, case index 2, 178 steps, shrunk (3, 1, 1); the fixed version (rounding down) passes; with no regressions listed the results equal L9's |
| 4 signed (only if time remains) | edge values include min, -1, 0, 1, max; shrinking goes toward 0 (a negative value tries its absolute value first); `x * x >= 0` over `i8` fails on overflow only through a checked helper |
| 5 unchanged | cross-check IDENTICAL (11/11); `./scripts/proof.sh --check` passes with no edit to the existing rows; `./scripts/record-evm.sh --check` passes |

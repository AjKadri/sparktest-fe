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

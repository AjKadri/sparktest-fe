# Sparktest API

Every public item of the `sparktest` ingot (`sparktest/`), then the two small shims. Examples are compiled and run by
`./scripts/check-docs.py` (part of `./scripts/test-all.sh`), so they stay true. Property inputs are any type that has
`Arbitrary`, `Shrink` and `Copy`; a property is a function (or closure) that returns `true` when it holds.

## Running a property

### `check(cfg: Config, prop) -> Outcome<T>`
Generates `cfg.cases` inputs, runs `prop` on each, and on the first failure shrinks the input greedily (first simpler candidate that still fails, repeated) for at most `cfg.max_shrinks` accepted steps. `prop: Fn(T) -> bool`; the runner is declared `uses P::E`, so a property that needs an effect (for example `Evm`) is accepted when its caller provides it.
```fe
let outcome = check(Config::new(fixed_seed(1)), |x: u256| x < 1000)
match outcome {
    Outcome::Pass { cases: _ } => { assert!(false) }
    Outcome::Fail { original: _, shrunk, case: _, seed: _, steps: _, early: _ } => { assert!(shrunk == 1000) }
}
```

### `Config { cases, seed, max_shrinks }`
Run settings. `Config::new(seed)` uses 256 cases and 1000 shrink steps; `with_cases(n)` and `with_max_shrinks(n)` change one field and return the new `Config`.
```fe
let c = Config::new(7).with_cases(10).with_max_shrinks(5)
assert!(c.seed == 7 && c.cases == 10 && c.max_shrinks == 5)
assert!(Config::new(7).cases == 256 && Config::new(7).max_shrinks == 1000)
```

### `Config::with_regressions([seed, ...])`: regression seeds
At most 8 seeds of earlier failures. Each is run as a full run of `cases` cases (the stream `Config::new(seed)` would give) BEFORE the random cases of `seed`. A failing regression is reported with its own seed and the case index inside that seed's stream, so `Config::new(seed)` replays it. Honoured by `check`, `check_with`, `check_gen` and `check_gen_with` (not by `check_assume`). With no regression seeds the run is exactly the random run.
```fe
let c = Config::new(1).with_regressions([25286971856348077807, 42])
assert!(c.n_regressions == 2 && c.regressions[0] == 25286971856348077807 && c.seed == 1)
assert!(Config::new(1).n_regressions == 0)
```

### `check_with(cfg, prop, stop) -> Outcome<T>`
`check` with a third closure `stop: Fn() -> bool`, polled before every shrink evaluation; when it returns `true`, shrinking ends at once and the best input so far comes back with `early = true`. The core has no effects, so what "stop" means is the caller's: `sparktest_evm::check_gas` passes "remaining gas is below a margin". `check` is `check_with` with a `stop` that is never true.
```fe
let o = check_with(Config::new(fixed_seed(1)), |x: u64| x < 1000, || true)
match o {
    Outcome::Pass { cases: _ } => { assert!(false) }
    Outcome::Fail { original, shrunk, case: _, seed: _, steps, early } => { assert!(early && steps == 0 && shrunk == original) }
}
```

### `Outcome<T>`
`Pass { cases }`, or `Fail { original, shrunk, case, seed, steps, early }`: the first failing input, the shrunk input, the 0-based index of the failing case, the seed (pass it to `Config::new` to replay), the number of accepted shrink steps, and `early`: `true` when shrinking was stopped before it finished (see `check_with` and `check_gas`), in which case `shrunk` is the best input found so far (it still fails, but may not be minimal). `Summary` and `Full` carry it as `early` (0 or 1).
```fe
match check(Config::new(fixed_seed(1)), |x: u8| x != 255) {
    Outcome::Pass { cases } => { assert!(cases == 256) }
    Outcome::Fail { original, shrunk, case: _, seed: _, steps: _, early: _ } => { assert!(original == 255 && shrunk == 255) }
}
```

### `Summary` and `summarize(outcome) -> Summary`
A flat, comparable view of an `Outcome`: `failed` (0 or 1), `case`, `steps`, and the first four words of the original and shrunk inputs. Used to compare backends.
```fe
let s = summarize(check(Config::new(fixed_seed(1)), |x: u256| x < 1000))
assert!(s.failed == 1 && s.shrunk[0] == 1000)
```

### `Full` and `full(outcome) -> Full`
Like `Summary` but with the complete words (`original` and `shrunk` are `DynArray<u256>`), for inputs longer than four words such as `Seq`.
```fe
let f = full(check(Config::new(fixed_seed(1)), |x: u256| x < 1000))
assert!(f.failed == 1 && f.shrunk.len() == 1 && f.shrunk.get(0) == 1000)
```

### `shrink_input(start, prop, max_shrinks) -> (T, u256)`
Shrinks an input that is already known to fail, with the same greedy rule as `check` (first candidate that still fails, repeat; at most `max_shrinks` accepted steps). Returns the shrunk input and the number of accepted steps. Useful for replaying a reported counterexample.
```fe
let (m, steps) = shrink_input(1000000 as u256, |x: u256| x < 1000, 1000)
assert!(m == 1000 && steps > 0)
```

## Randomness

### `trait Rng { fn next(mut self) -> u256 }`
A source of pseudorandom words. Implement it to plug in your own generator.
```fe-item
struct Counter { n: u256 }
impl Rng for Counter {
    fn next(mut self) -> u256 {
        self.n += 1
        self.n
    }
}
```

### `Xorshift::seeded(seed: u256) -> Xorshift`
The built-in 64-bit xorshift generator. Equal seeds give equal streams; the all-zero state is avoided.
```fe
var a = Xorshift::seeded(42)
var b = Xorshift::seeded(42)
assert!(a.next() == b.next())
```

## Traits a type needs to be tested

### `trait Arbitrary { fn arbitrary<R: Rng>(_ rng: mut R) -> Self }`
Generates a value. Call it as `<T as Arbitrary>::arbitrary(...)` or through generics (not `Type::arbitrary`, which does not resolve for types from other ingots such as `Address`: argotorg/fe#2066).
```fe
var rng = Xorshift::seeded(1)
let x = <u8 as Arbitrary>::arbitrary(mut rng)
let a = <Address as Arbitrary>::arbitrary(mut rng)
assert!(a.word() < 1461501637330902918203684832716283019655932542976)
```

### `trait Shrink { fn shrink_step(self, _ i: u256) -> Option<Self>; fn joint_step(self, _ i: u256) -> Option<Self> }`
The `i`-th simpler candidate (`i = 0, 1, 2, ...`), or `None` when candidates run out. For integers: `0`, then `x - x/2`, `x - x/4`, ..., then `x - 1`. `joint_step` (default: none) offers joint candidates that move several components together (tuples, arrays and `Seq` implement it, at the top level only). `check` tries the `shrink_step` candidates until none fails (a fixed point), then the `joint_step` candidates as a finishing pass, and repeats while anything improves.
```fe
let x: u256 = 1000
match x.shrink_step(0) {
    Option::Some(c) => { assert!(c == 0) }
    Option::None => { assert!(false) }
}
match x.shrink_step(1) {
    Option::Some(c) => { assert!(c == 500) }
    Option::None => { assert!(false) }
}
```

### `trait Encode { fn words(self) -> DynArray<u256> }`
Flattens a value to words, so any counterexample can be reported in full (for example in `PropertyFailed`).
```fe
let w = (7 as u8, true).words()
assert!(w.len() == 2 && w.get(0) == 7 && w.get(1) == 1)
```

### `one_word(w: u256) -> DynArray<u256>` and `append_words(out, src)`
Helpers for writing your own `Encode`: a one-word array, and appending every word of `src` to a `MemVec<u256>`.
```fe
var out: MemVec<u256> = MemVec::new()
append_words(mut out, one_word(5))
append_words(mut out, one_word(6))
assert!(out.len() == 2)
```

## Built-in generators

| type | generated values | shrinks toward |
|---|---|---|
| `u256` | about 1 in 4 draws is an edge: 0, 1, 2, `MAX`, `MAX - 1`, 2^k, 2^k - 1, 2^k + 1; the rest are uniform | 0 |
| `u8`, `u16`, `u32`, `u64`, `u128` | the same edge set within the width | 0 |
| `i8`, `i16`, `i32`, `i64`, `i128`, `i256` | about 1 draw in 4 is an edge value (min, max, -1, 0, 1, 2, -2, +-2^k), the rest are uniform over all bit patterns; `Encode` is the sign-extended 256-bit word (-1 is 2^256 - 1) | 0: first 0, then (for a negative) its absolute value, then the magnitude halved toward 0 with the original sign. Joint shrinking works on the magnitude and keeps the sign, so signed components inside tuples and arrays take the same joint moves as unsigned ones (all together, equal together, redistribution) |
| `bool` | either | `false` |
| `Address` | 160 random bits with edge values (zero address, `0x...01`, max address) | the zero address |
| tuples of 2, 3 and 4 | each component | one component at a time, then joint moves (all together, equal components together, redistribution) |
| `[T; N]` | each element | one element at a time, then the same joint moves |
| `Index<N>` | 0..N-1, edge bias to 0 and N-1 | 0 |
| `Seq<C, N>` | a length 0..=N and N commands | shorter sequences, then simpler commands, then joint moves over the commands (groups of equal values) |

### `MAX: u256`
The largest `u256`.
```fe
assert!(MAX == 0xffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffffff)
assert!(MAX.checked_add(1).is_none())
```

### `Index<N>` and `Index { value }`
A value in `0..N-1` (use it to pick from a small fixed set, so shrinking stays inside the set). `N` must be at least 1.
```fe
let i: Index<4> = Index { value: 3 }
let w = i.words()
assert!(w.get(0) == 3)
match i.shrink_step(0) {
    Option::Some(c) => { assert!(c.value == 0) }
    Option::None => { assert!(false) }
}
```

### `Seq<C, N>` (`len`, `items`)
A sequence of up to `N` commands for stateful testing: `len` is generated too, and only the first `len` of the `N` items are used. Shrink order: halve the length, drop one command, then shrink single commands. `words()` is the length followed by the commands' words.
```fe
let s: Seq<u8, 4> = Seq { len: 3, items: [10, 20, 30, 40] }
match s.shrink_step(0) {
    Option::Some(c) => { assert!(c.len == 1) }
    Option::None => { assert!(false) }
}
let w = s.words()
assert!(w.len() == 4 && w.get(0) == 3 && w.get(3) == 30)
```

### `trait Checked`: `checked_add`, `checked_sub`, `checked_mul`
Overflow-safe arithmetic for `u8` to `u256` that returns `Option<Self>` and never panics. Use it inside properties, because a panic inside a property ends the whole test instead of being reported.
```fe
let a: u8 = 250
assert!(a.checked_add(5).is_some())
assert!(a.checked_add(6).is_none())
assert!(a.checked_sub(251).is_none())
assert!(a.checked_mul(2).is_none())
```

### `widths::bits_value(rng, bits) -> u256` and `composite::count_candidates(x) -> u256`
`bits_value` draws a value below `2^bits` with the edge-biased scheme (used by the integer and `Address` generators); `count_candidates` counts how many shrink candidates a value has (used by the tuple, array and `Seq` shrinkers).
```fe
var rng = Xorshift::seeded(3)
assert!(bits_value(mut rng, 8) < 256)
let x: u8 = 3
assert!(count_candidates(x) == 3)   // 0, 3 - 1 = 2, then x - 1 = 2
```

## Custom generators: `Gen`

A `Gen` generates a value from an `Rng`, offers shrink candidates that stay INSIDE its own domain, and says whether a value belongs to its domain. `check_gen(cfg, gen, prop)` runs a property over it and returns the same `Outcome` as `check`; `check_gen_with(cfg, gen, prop, stop)` is the version with a `stop` closure, and `sparktest_evm::check_gen_gas` is the gas-guarded one. The trait has an associated effect row, so a generator built from a closure forwards the closure's effects.

```fe-trait
trait Gen { uses E; type Value; fn generate<R: Rng>(self, rng: mut R) -> Value; fn shrink(self, x: Value, i: u256) -> Option<Value>; fn contains(self, x: Value) -> bool }
```

### `between(lo, hi)`
An inclusive range of `u256` values. About 1 draw in 4 is `lo`, `lo + 1`, `hi - 1` or `hi`; the rest are uniform (modulo bias is ignored). It shrinks toward `lo` and never below it.
```fe
let o = check_gen(Config::new(fixed_seed(1)), between(100, 1000), |x: u256| x < 500)
match o {
    Outcome::Pass { cases: _ } => { assert!(false) }
    Outcome::Fail { original: _, shrunk, case: _, seed: _, steps: _, early: _ } => { assert!(shrunk == 500) }
}
// a property that always fails shrinks to the lower bound, not to 0
let s = summarize(check_gen(Config::new(fixed_seed(1)), between(100, 1000), |x: u256| false))
assert!(s.shrunk[0] == 100)
```

### `one_of([a, b, c])`
A value from a small set of `u256`s; it shrinks toward earlier elements.
```fe
let s = summarize(check_gen(Config::new(fixed_seed(1)), one_of([5, 3, 9]), |x: u256| x != 3 && x != 9))
assert!(s.shrunk[0] == 3)
```

### `pair(a, b)`
Two independent generators; the value is a tuple. It shrinks the first, then the second.
```fe
let g = pair(between(5, 50), between(100, 200))
let s = summarize(check_gen(Config::new(fixed_seed(1)), g, |p: (u256, u256)| p.0 + p.1 < 130))
assert!(s.failed == 1 && s.shrunk[0] >= 5 && s.shrunk[1] >= 100)
```

### `dependent(a, f)`
Generate `a`, then the second value from the generator `f(a)`: "an amount up to the balance". The value is `(a, b)`. Shrinking tries `b` first (inside `f(a)`), then a smaller `a` that `f(a')` still accepts, then both together, so it never leaves the domain.
```fe
let g = dependent(between(1, 1000), |balance: u256| between(0, balance))
let s = summarize(check_gen(Config::new(fixed_seed(1)), g, |v: (u256, u256)| v.1 <= v.0 / 2))
assert!(s.failed == 1 && s.shrunk[0] == 1 && s.shrunk[1] == 1)   // never an amount above the balance
```

### `mapped(g, f, inverse)`
The values of `g` seen through `f`. `inverse` must recover the source value (so `f` is a bijection on the domain); shrinking shrinks the source and maps again.
```fe
let g = mapped(between(0, 100), |x: u256| x * 2, |y: u256| y / 2)
let s = summarize(check_gen(Config::new(fixed_seed(1)), g, |y: u256| y < 50))
assert!(s.shrunk[0] == 50)
```

### `check_gen_gas(cfg, gen, prop)` (`sparktest_evm`)
`check_gen` with the same gas guard as `check_gas`: shrinking stops when the remaining gas is below `GAS_MARGIN` and the best input so far comes back with `early = true`. `check_gen_gas_with_margin` chooses the margin.
```fe
let s = summarize(check_gen_gas(Config::new(fixed_seed(1)), between(0, 1000000), |x: u256| x < 12345))
assert!(s.failed == 1 && s.early == 0 && s.shrunk[0] == 12345)
```

## Discarding cases: `assume`

A property can return `Judged::Holds`, `Judged::Fails` or `Judged::Discard`. `judged(ok)` maps a boolean; `assuming(premise, holds)` is `Discard` when the premise is false (both arguments are evaluated first: use an early `return Judged::Discard` when evaluating `holds` is only valid under the premise). `check_assume(cfg, prop)` and `check_gen_assume(cfg, gen, prop)` run it and return an `AssumeResult { outcome, cases, discarded }`. A discarded case is counted and not replaced (the case budget includes the discards), and during shrinking a discarded candidate is not a failure, so a shrunk input always satisfies the premise.

`discard_percent(r)` is the share discarded in whole percent. `assume_guard(r, max_percent)` returns the existing `Verdict`: `Failed` if the property failed; `Vacuous { reason: 2 }` if no case was accepted; `Vacuous { reason: VACUOUS_TOO_MANY_DISCARDS }` (100) if MORE than `max_percent` percent were discarded (`DEFAULT_MAX_DISCARD_PERCENT` is 90); else `Held`.
```fe
// "assume x <= 250" over a raw u32: only edge values satisfy it, so most cases are discarded
let r = check_assume(Config::new(fixed_seed(1)), |x: u32| assuming(x <= 250, true))
assert!(discard_percent(r) > 50)
// a premise that never holds is vacuous (reason 2: nothing was accepted)
let never = check_assume(Config::new(fixed_seed(1)), |x: u32| assuming(x == 12345, true))
match assume_guard(never, DEFAULT_MAX_DISCARD_PERCENT) {
    Verdict::Vacuous { reason } => { assert!(reason == VACUOUS_NONE_SUCCEEDED) }
    Verdict::Held => { assert!(false) }
    Verdict::Failed => { assert!(false) }
}
```

## Vacuity guards (contract and stateful properties)

A run that passes proves nothing if the property never exercised its premise: a conditional property whose condition never held, or a command kind that was never generated. A property that makes calls records what it did in a `Tally` (an effect, so the runner forwards it like any other); the caller then asks whether a passing run was vacuous. A run that fails is a failure whatever the counts.

### `Tally { attempted, accepted, kinds }`
Counters: calls attempted, calls that succeeded, and commands executed per kind (0 to 7). A property declares `uses (tally: mut Tally)` and calls `tally.call(ok)` after each call it makes and `tally.command(kind)` for each command it executes. The caller provides the tally with `with (mut tally) { check(...) }`.
```fe-item
fn counted_property(_ x: u8) -> bool uses (tally: mut Tally) {
    tally.call(x > 100)
    tally.command(1)
    true
}
```
```fe
var tally = Tally::new()
let outcome = with (mut tally) { check(Config::new(fixed_seed(1)), counted_property) }
match outcome {
    Outcome::Pass { cases } => { assert!(cases == 256) }
    Outcome::Fail { original: _, shrunk: _, case: _, seed: _, steps: _, early: _ } => { assert!(false) }
}
assert!(tally.attempted == 256 && tally.accepted > 0 && tally.accepted < 256)
assert!(tally.kinds[1] == 256 && tally.kinds[0] == 0)
```

### `vacuity(tally, need_accepted, kinds) -> u256`
Returns 0 for a run that exercised its premise, otherwise the reason: `VACUOUS_NO_CALLS` (1: nothing attempted), `VACUOUS_NONE_SUCCEEDED` (2: calls attempted but none succeeded, checked only when `need_accepted`; properties about calls that must fail pass `false`), or `VACUOUS_KIND_BASE + k` (3 + k: no command of kind `k` was executed, checked for kinds `0..kinds`).
```fe
var t = Tally::new()
assert!(vacuity(t, false, 0) == VACUOUS_NO_CALLS)
t.call(false)
assert!(vacuity(t, false, 0) == 0)
assert!(vacuity(t, true, 0) == VACUOUS_NONE_SUCCEEDED)
t.call(true)
assert!(vacuity(t, true, 0) == 0)
assert!(vacuity(t, true, 2) == VACUOUS_KIND_BASE)       // no command of kind 0 was executed
t.command(0)
assert!(vacuity(t, true, 2) == VACUOUS_KIND_BASE + 1)   // kind 1 still missing
t.command(1)
assert!(vacuity(t, true, 2) == 0)
```

### `Verdict` and `guard(outcome, tally, need_accepted, kinds) -> Verdict`
Applies `vacuity` to an `Outcome`: `Failed` for a failing run, `Held` for a passing run that exercised its premise, `Vacuous { reason }` for a passing run that did not.
```fe
var t = Tally::new()
t.call(false)
let o: Outcome<u8> = Outcome::Pass { cases: 10 }
match guard(o, t, true, 0) {
    Verdict::Vacuous { reason } => { assert!(reason == VACUOUS_NONE_SUCCEEDED) }
    Verdict::Held => { assert!(false) }
    Verdict::Failed => { assert!(false) }
}
```

## Decode (the inverse of Encode)

### `trait Decode { fn decode(_ w: DynArray<u256>, _ pos: usize) -> (Self, usize) }`
Rebuilds a value from the words `Encode` produced: it reads one value starting at word `pos` and returns it with the position after it, so composites decode their parts in order. Implemented for `u8` to `u256`, `bool`, `Address`, `Index<N>`, tuples of 2 to 4 and `[T; N]` (not for `Seq`). Since L7c the trait also has `fn fits(_ w: [u256; 64], _ pos: usize) -> usize`: it checks, without allocating, that the words at `pos` form a valid value (an `Index<N>` word is below `N`, a `u8` is at most 255) and returns the position after it, or 0 if not. Joint shrinking uses it to reject invalid candidates before decoding.
```fe
let w = (7 as u8, 500 as u32).words()
let (back, next) = <(u8, u32) as Decode>::decode(w, 0)
assert!(back.0 == 7 && back.1 == 500 && next == 2)
```

## Panic recovery on the EVM (`sparktest_evm`)

A panic inside a property used to end the whole test. `check_isolated` runs each evaluation inside a harness contract called through `evm.try_call`, so a panic is a failed call that is found, shrunk and reported (with its reason). `check` itself is unchanged. Fe contracts cannot be generic, so you write the harness once: a contract with one `recv Isolated` arm and one line per property.

### `msg Isolated { Run { id, words } -> u256 }` and `run_prop(prop, words) -> u256`
The message every harness answers: run property `id` on the input given as `Encode` words (reply 1 = held, 0 = returned false; a panic makes the call fail). `run_prop` is the arm's one-liner: it decodes the words and runs the property.
```fe-item
fn halves_never_exceed(_ x: u64) -> bool { x / 2 <= x }
fn thousand_times_round_trips(_ x: u64) -> bool { x * 1000 / 1000 == x }   // panics (overflow) for large x

contract Harness {
    init() {}
    recv Isolated {
        Run { id, words } -> u256 {
            if id == 0 { return run_prop(halves_never_exceed, words) }
            if id == 1 { return run_prop(thousand_times_round_trips, words) }
            0
        }
    }
}
```

### `check_isolated<T>(cfg, harness, id) -> IsoOutcome<T>`
Like `check`, but each evaluation is a `try_call` to the harness: it generates inputs in the test, a failed call (returned false or panicked) is a failing case, and the input is shrunk the same way. `IsoOutcome::Pass { cases }` or `IsoOutcome::Fail { original, shrunk, case, seed, steps, reason, original_reason }`.
```fe
let harness = evm.create<Harness>(value: Wei::zero(), args: ())
match check_isolated<u64>(Config::new(fixed_seed(1)), harness, 1) {
    IsoOutcome::Pass { cases: _ } => { assert!(false) }
    IsoOutcome::Fail { original: _, shrunk, case: _, seed: _, steps: _, reason, original_reason: _ } => {
        assert!(shrunk == 18446744073709552)              // the smallest x for which x * 1000 overflows u64
        assert!(reason == REASON_PANIC_BASE + 0x11)       // Panic(0x11): arithmetic overflow
    }
}
```

### `eval_isolated(harness, id, x) -> u256` and the reason codes
One isolated evaluation: `REASON_HELD` (0), `REASON_FALSE` (1, the property returned false), `REASON_OTHER_REVERT` (2), `REASON_NO_DATA` (3, for example out of gas) or `REASON_PANIC_BASE + code` for `Panic(code)` (`0x11` overflow, `0x12` division by zero). `reason_text(r)` gives a short description.
```fe
let harness = evm.create<Harness>(value: Wei::zero(), args: ())
assert!(eval_isolated(harness, 0, 10 as u64) == REASON_HELD)
assert!(eval_isolated(harness, 1, 18446744073709552 as u64) == REASON_PANIC_BASE + 0x11)
assert!(reason_text(REASON_PANIC_BASE + 0x12) == "panicked: division by zero")
```

### Native and wasm
A panic aborts a native process and traps in wasm, so it cannot be caught inside the run. The replay driver `replay-native/` plus `scripts/find-panic.sh` bisect the case limit to the first aborting case and shrink by replaying candidates as single-case runs; the demo page does the same with the wasm trap (see [PROOF.md](PROOF.md), "Panic recovery").

## Writing your own type

A struct becomes testable by delegating `Arbitrary`, `Shrink` and `Encode` to a tuple of its fields:
```fe-item
struct Pair { a: u8, b: u8 }
impl Copy for Pair {}
impl Arbitrary for Pair {
    fn arbitrary<R: Rng>(_ rng: mut R) -> Self {
        let t = <(u8, u8) as Arbitrary>::arbitrary(mut rng)
        Pair { a: t.0, b: t.1 }
    }
}
impl Shrink for Pair {
    fn shrink_step(self, _ i: u256) -> Option<Self> {
        match (self.a, self.b).shrink_step(i) {
            Option::Some(t) => Option::Some(Pair { a: t.0, b: t.1 })
            Option::None => Option::None
        }
    }
}
impl Encode for Pair {
    fn words(self) -> DynArray<u256> { (self.a, self.b).words() }
}
```
```fe
match check(Config::new(fixed_seed(1)), |p: Pair| (p.a as u256) + (p.b as u256) < 10) {
    Outcome::Pass { cases: _ } => { assert!(false) }
    Outcome::Fail { original: _, shrunk, case: _, seed: _, steps: _, early: _ } => { assert!((shrunk.a as u256) + (shrunk.b as u256) == 10) }
}
```

## `sparktest_evm` (sonatina / EVM shim)

### `assert_holds(outcome)`
Returns on `Pass`; on `Fail` reverts with `PropertyFailed { seed, case, steps, input: DynArray<u256> }` (selector `0x4c350703`), where `input` is the shrunk input's words. `tools/decode-revert` decodes the revert data.
(The compiled example is the quickstart test `assert_holds_reverts_with_the_shrunk_input` in `examples/quickstart/src/lib.fe`.)

### `PropertyFailed`
The `#[error]` struct above: `seed`, `case` (0-based), `steps`, `input`.

### `check_gas(cfg, prop) -> Outcome<T>`, `check_gas_with_margin(cfg, prop, margin)` and `GAS_MARGIN`
`check` for the EVM that cannot lose its report to the gas cap while shrinking: before every shrink evaluation it compares the remaining gas with the margin (`GAS_MARGIN` = 50,000,000, about 33 evaluations of the most expensive property in this repository) and, below it, stops and returns the best input found so far with `early = true`. Only shrinking is guarded; generating cases is not. Native has no gas, so `early` is always `false` there.
```fe
let o = check_gas(Config::new(fixed_seed(1)), |x: u64| x < 1000)
match o {
    Outcome::Pass { cases: _ } => { assert!(false) }
    Outcome::Fail { original: _, shrunk, case: _, seed: _, steps: _, early } => { assert!(shrunk == 1000 && !early) }
}
assert!(GAS_MARGIN == 50000000)
```
With a margin above the gas available it stops before the first shrink evaluation (`check_gas_with_margin(cfg, prop, margin)` chooses the margin).

### `PropertyFailedEarly`
Same fields as `PropertyFailed`; `assert_holds` reverts with it instead (selector `0x52e195ec`) when `early` is true, so the input is the best found so far, not necessarily a minimum. `tools/decode-revert` decodes it and prints "shrink stopped early (gas)".

### `runtime_seed() -> u256` and `fixed_seed(salt) -> u256`
`runtime_seed()` mixes the remaining gas and `prevrandao`, so each run differs (a seed the optimizer cannot fold). `fixed_seed(salt)` mixes `salt` with the chain id: the same value on every run in a fresh test EVM, but opaque to the optimizer. The native `fixed_seed` is built differently, so `fixed_seed(5)` is NOT the same number on sonatina and native: test suites that use it have backend-specific seeds on purpose, and their individual runs differ. The same NUMERIC seed (for example `Config::new(25286971856348077807)`) gives identical results on every backend; `scripts/cross-check.sh` compares them that way.
```fe
assert!(fixed_seed(5) == fixed_seed(5))
assert!(fixed_seed(5) != fixed_seed(6))
let r = runtime_seed()
```

## `sparktest_native` (native shim)

### `assert_holds(outcome)`
Returns on `Pass`; on `Fail` prints the seed, case, steps and the shrunk input words with `println!`, then fails the test. Needs the `Stdout` effect.

### `opaque_zero()`, `fixed_seed(salt)`, `ticks()`
`opaque_zero()` is a zero the optimizer cannot see (it depends on the CPU clock host call); `fixed_seed(salt)` is a deterministic seed built on it (a different number from the sonatina `fixed_seed(salt)`); `ticks()` reads process CPU time in clock ticks, for benchmarks only (the repository's tests assert exact evaluation counts through a `Tally`, never time).
```fe-native
assert!(opaque_zero() == 0)
assert!(fixed_seed(5) == fixed_seed(5))
let _ = ticks()   // for benchmarks only: print it, never assert on it
```

### `print_summary(name, summary)` and `print_full(name, full)`
Print a result as comparable `XC` / `XW` lines (used by the cross-backend checks).

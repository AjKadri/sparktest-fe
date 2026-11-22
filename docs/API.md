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
    Outcome::Fail { original: _, shrunk, case: _, seed: _, steps: _ } => { assert!(shrunk == 1000) }
}
```

### `Config { cases, seed, max_shrinks }`
Run settings. `Config::new(seed)` uses 256 cases and 1000 shrink steps; `with_cases(n)` and `with_max_shrinks(n)` change one field and return the new `Config`.
```fe
let c = Config::new(7).with_cases(10).with_max_shrinks(5)
assert!(c.seed == 7 && c.cases == 10 && c.max_shrinks == 5)
assert!(Config::new(7).cases == 256 && Config::new(7).max_shrinks == 1000)
```

### `Outcome<T>`
`Pass { cases }`, or `Fail { original, shrunk, case, seed, steps }`: the first failing input, the shrunk input, the 0-based index of the failing case, the seed (pass it to `Config::new` to replay) and the number of accepted shrink steps.
```fe
match check(Config::new(fixed_seed(1)), |x: u8| x != 255) {
    Outcome::Pass { cases } => { assert!(cases == 256) }
    Outcome::Fail { original, shrunk, case: _, seed: _, steps: _ } => { assert!(original == 255 && shrunk == 255) }
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

### `trait Shrink { fn shrink_step(self, _ i: u256) -> Option<Self> }`
The `i`-th simpler candidate (`i = 0, 1, 2, ...`), or `None` when candidates run out. For integers: `0`, then `x - x/2`, `x - x/4`, ..., then `x - 1`.
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
| `bool` | either | `false` |
| `Address` | 160 random bits with edge values (zero address, `0x...01`, max address) | the zero address |
| tuples of 2, 3 and 4 | each component | one component at a time |
| `[T; N]` | each element | one element at a time |
| `Index<N>` | 0..N-1, edge bias to 0 and N-1 | 0 |
| `Seq<C, N>` | a length 0..=N and N commands | shorter sequences, then simpler commands |

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
    Outcome::Fail { original: _, shrunk: _, case: _, seed: _, steps: _ } => { assert!(false) }
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
    Outcome::Fail { original: _, shrunk, case: _, seed: _, steps: _ } => { assert!((shrunk.a as u256) + (shrunk.b as u256) == 10) }
}
```

## `sparktest_evm` (sonatina / EVM shim)

### `assert_holds(outcome)`
Returns on `Pass`; on `Fail` reverts with `PropertyFailed { seed, case, steps, input: DynArray<u256> }` (selector `0x4c350703`), where `input` is the shrunk input's words. `tools/decode-revert` decodes the revert data.
(The compiled example is the quickstart test `assert_holds_reverts_with_the_shrunk_input` in `examples/quickstart/src/lib.fe`.)

### `PropertyFailed`
The `#[error]` struct above: `seed`, `case` (0-based), `steps`, `input`.

### `runtime_seed() -> u256` and `fixed_seed(salt) -> u256`
`runtime_seed()` mixes the remaining gas and `prevrandao`, so each run differs (a seed the optimizer cannot fold). `fixed_seed(salt)` mixes `salt` with the chain id: the same value on every run in a fresh test EVM, but opaque to the optimizer.
```fe
assert!(fixed_seed(5) == fixed_seed(5))
assert!(fixed_seed(5) != fixed_seed(6))
let r = runtime_seed()
```

## `sparktest_native` (native shim)

### `assert_holds(outcome)`
Returns on `Pass`; on `Fail` prints the seed, case, steps and the shrunk input words with `println!`, then fails the test. Needs the `Stdout` effect.

### `opaque_zero()`, `fixed_seed(salt)`, `ticks()`
`opaque_zero()` is a zero the optimizer cannot see (it depends on the CPU clock host call); `fixed_seed(salt)` is a deterministic seed built on it; `ticks()` reads process CPU time in clock ticks.
```fe-native
assert!(opaque_zero() == 0)
assert!(fixed_seed(5) == fixed_seed(5))
assert!(ticks() >= 0)
```

### `print_summary(name, summary)` and `print_full(name, full)`
Print a result as comparable `XC` / `XW` lines (used by the cross-backend checks).

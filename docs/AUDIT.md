# Independent audit

- Audited commit: `28ee20aef283768eeb54cebd179c171e60f5bcb4`
- Auditor: an independent Claude session, working from a fresh clone, read-only, given only the repository URL, the commit, the live demo URL, the contest rules and the submission template.
- Date: 2026-11-24
- Written after the fixes: the commits listed at the end of this file.

## Result

The test suite passed from a clean clone. The audit reported 13 findings: 1 major, 8 minor and 4 nits. Eight are fixed in code, tests or text (F1 to F8), four are documented without a code change (F9 to F12), and one (F13) is fixed in part. One further audit remark, that CI had not been verified for the audited commit, was incorrect and is corrected below.

Severities are the audit report's own; the one-line descriptions summarise its findings.

## Findings

| id | severity | finding | outcome | commits |
|---|---|---|---|---|
| F1 | major | Signed integers inside tuples or arrays make per-type shrinking and the joint "minus 1" pass pull opposite ways and cycle to the 1000-step cap (`(i32, u8)` with `p.0 >= -100` gave 1000 steps and -102; the true minimum is -101) | fixed | cbcb5b2, d615079, 02c6e67, a00b030, 108fd17, 29d0020, ddc2393 |
| F2 | minor | The Buggy / Fixed toggle shows on Pair sum and Saturating add: a CSS `display` rule overrides the `hidden` attribute | fixed | 7b33e4f |
| F3 | minor | A note in docs/PROOF.md says `fee_buggy` stops at a local minimum, which contradicts the table in the same file | fixed | 8784fba |
| F4 | minor | Test counts in the README did not match what `test-all.sh` prints | fixed | dd04fb2 |
| F5 | minor | Docs said expected results were "written down before each run"; what the commit history shows is expectations committed before the results commit. On 22 November, before the repository was first pushed, the history was rewritten once to replace a placeholder commit identity (`spike <spike@localhost>`) with the author's own (`AjKadri`); commit messages, contents and author dates were unchanged, and `2555bd4` re-recorded the EVM runs because every commit hash changed. | fixed (reworded) | 36b9319 |
| F6 | minor | "A failure never loses its report" holds only with `check_gas` / `check_gen_gas`, and "smallest" overstated what greedy shrinking guarantees | fixed (reworded) | 3412e17 |
| F7 | minor | Two native tests have names that claim more than they check (a bare `should_revert`, where any panic passes), and a comment claimed `PropertyFailed` carries all 6 words | fixed | dc7940e |
| F8 | minor | CI and the README installed Fe from `feup.sh` on `master`, with no checksum | fixed | 8ccfc2b (CI), 289a1ca (README) |
| F9 | minor | The vendored CoolCoin has no stated licence and was not excluded from the MIT OR Apache-2.0 statement | documented | e301915 |
| F10 | nit | Joint shrinking silently switches off above 64 words | documented, code left as-is | 5a48f22 |
| F11 | nit | The 256-bit seed is folded to 64 bits by XOR, so different seeds can give the same stream | documented, code left as-is | 5a48f22 |
| F12 | nit | `check_isolated` ignores the regression seeds of `Config` | documented | 5a48f22 |
| F13 | nit | Hygiene: `__pycache__` not ignored, demo picker cards without accessible names, build outputs under `spike/` tracked | fixed in part (`.gitignore`, `aria-label`); `spike/` outputs left as-is | 3461a00 |

Not numbered by the audit but fixed during the same pass: a dead second check in `scripts/check-docs.py` that matched nothing and whose comment described a section that does not exist (23d0283), and the stale "5 cross-check scenarios" comment in `scripts/cross-check.sh`, whose real count is 11 (ec1dca8).

## F1 in detail

**Cause.** A signed integer is encoded as a sign-extended 256-bit word, so -1 is 2^256 - 1. The per-type shrinker moves a negative toward zero (-3 to -2). The joint "minus 1" pass works on the raw words and takes the smaller raw word, which moves a negative away from zero (-2 to -3). Inside a tuple or array the two undo each other until the step cap.

**Fix (A).** Joint candidates use the same order as the per-type shrinkers: for each signed word the joint moves work on the magnitude and keep the sign. Which words are signed comes from the type, through a new `Decode` method, `mark_signed` (default: one unsigned word; the signed integer types, tuples and arrays override it). The change is confined to `joint.fe`, `seq.fe`, the `Decode` trait and the per-type encoding code.

**Order of work.**
- `cbcb5b2`: expectations committed before any test or fix.
- `d615079`: regression tests, which fail before the fix.
- `02c6e67`: the fix.
- `a00b030`: docs/PROOF.md regenerated.
- `108fd17`: demo wasm rebuilt.
- `29d0020`: web/recorded.json re-recorded.
- `ddc2393`: amendment to docs/EXPECTATIONS.md recording the gas change.

**Result.** All four regression tests pass on sonatina and native. The test that only joint shrinking can solve, `(-40, -40)` with a property that fails only for equal negative pairs at or below -5, reaches exactly `(-5, -5)`.

**Alternative (B), not taken.** Skipping joint moves for signed components was also tried. It also changed gas figures, and it fails the joint-only case, which is the reason joint shrinking exists.

**Cost of A.** Gas figures moved even for runs that never reach a joint step. Cases, steps, shrunk inputs, verdicts and seeds did not change in docs/PROOF.md (53 lines changed, gas only), and the failing demo recordings are identical.
- `vault_buggy`: 1,187,692 to 1,518,030 gas (+28%)
- `bounds_buggy`: 56,746 to 75,340 gas (+33%)
- `withdraw_buggy`: 207,642 to 235,414 gas (+13%)
- the five passing demo runs in web/recorded.json: +52 to +123 gas each
- the largest figure in PROOF.md is about 160 million gas, far below the 1,000,000,000 cap

The mechanism is not fully identified. Adding the `mark_signed` method alone moved nothing; the drift appears once the joint-shrinking code changes. The pre-registration said gas should not move; that row was wrong, and the amendment `ddc2393` says so.

## Left as-is, with reasons

- **F10, the 400-candidate cap.** The audit suggested returning early once joint shrinking reaches its 400-candidate cap, instead of looping through the remaining candidates. That only saves gas, and as F1 showed, any change to the shrinking code moves recorded gas, so it was not added. The 64-word limit the audit also flagged is documented in docs/API.md and the README Limitations.
- **F11, seed folding.** Changing how seeds are mixed would change every recorded result, every row of docs/PROOF.md and every demo output. It is documented instead (docs/API.md, README Limitations). Replaying a reported seed is not affected, because it folds the same way.
- **F13, tracked build outputs under `spike/`.** They are the evidence cited by the spike reports, so they stay.

## Audit remarks that were corrected

- **CI for the audited commit.** The audit said CI for `28ee20a` was unverified. CI passed on `28ee20a` (run 45360242834).
- **Installing Fe.** The auditor installed Fe from the release asset, because piping the install script to `bash` was blocked in its environment. The README and CI now install from the release asset and check its sha256, so they no longer depend on that script.

## Commits after the audited commit

Everything between `28ee20a` and the commit that adds this file, oldest first. The commits that add this file and its two links in the README come after it.

```
cbcb5b2 docs: pre-register expectations for the signed joint-shrinking fix (F1)
d615079 test: regression tests for signed components in joint shrinking (F1), failing before the fix
02c6e67 fix: joint shrinking works on magnitudes for signed components (F1)
a00b030 docs: regenerate PROOF.md after the F1 fix (gas figures only)
108fd17 chore: rebuild demo wasm after the F1 fix
29d0020 chore: re-record EVM runs after the F1 fix (gas of passing runs only)
ddc2393 docs: amend F1 expectations, gas-only drift accepted
20479f8 docs: pin the README git dependency to the F1 fix commit
7b33e4f fix: hide the Buggy / Fixed toggle on properties without a fixed version
dc7940e test: rename native tests to what they check and fix the 'all 6 words' comment
3461a00 chore: ignore __pycache__ and give the picker cards accessible names
23d0283 chore: remove the dead fe-excerpt <path> check from check-docs.py
8ccfc2b ci: install Fe from the pinned v26.7.0 release asset and verify its sha256
3412e17 docs: align the pitch with what shrinking guarantees; qualify the gas-guard claim (F6)
dd04fb2 docs: update the README test counts (337 at the root, 163 sonatina, 126 native)
8784fba docs: correct the fee_buggy note in PROOF.md, which contradicted its own table (F3)
36b9319 docs: say expectations were committed before the results commit instead of written before each run (F5)
e301915 docs: state that the vendored CoolCoin is not covered by the project licence (F9)
5a48f22 docs: document the 64-word joint limit, seed folding and check_isolated regression seeds; fix stale signed-shrinking notes (F10-F12)
081b725 docs: add the tested Fe version line next to the install step
2cc72df docs: rewrite the Fe highlight lead and the PITCH Fe-specific paragraph
c7ea872 docs: add the For judges block to the README
5245c54 docs: say the seed guarantee covers sonatina and native, and wasm for the demo properties; soften two shrink claims
ec1dca8 chore: correct the scenario count in the cross-check.sh header comment
089f911 docs: drop 'minimal' from the PROOF.md column note
289a1ca docs: install Fe from the pinned v26.7.0 release asset with a sha256 check, per platform (F8)
```

Text-only changes that did not come from an audit finding: the new pitch wording, the rewritten Fe highlight (README and docs/PITCH.md), the "For judges" block, the tested-version line, and the sentences softened in `5245c54` and `089f911`.

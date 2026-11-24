// Node test for the web demo: the compiled wasm must agree with the recorded sonatina (EVM) and native results
// for the same seed, replay must reproduce, the passing property must pass, case numbers are 1-based for users,
// and each card's description must agree with its property's `// BUG:` comment.
// Run: node web/sparktest.test.mjs
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { loadSparktest, PROPS, PANIC_PROPS, FIXED_PROPS } from './sparktest-runner.mjs';

const here = (f) => new URL(f, import.meta.url);
const doc = JSON.parse(fs.readFileSync(here('./props.json'), 'utf8'));
const recorded = JSON.parse(fs.readFileSync(here('./recorded.json'), 'utf8'));
const bytes = fs.readFileSync(here('./' + doc.wasm.file));
assert.equal(bytes.length, doc.wasm.bytes, 'wasm size matches props.json');
const st = await loadSparktest(bytes);
const pad4 = (a) => [...a, 0, 0, 0, 0].slice(0, 4).map(BigInt);
// sequences carry all their words (length + 4 per command); other properties carry 4
const words = (p, a) => (p.seq ? a.map(BigInt) : pad4(a));
const show = (a) => '[' + a.join(', ') + ']';

assert.deepEqual(doc.props.map((p) => p.id), PROPS);

// --- card text must not drift from the code ---
for (const p of doc.props) {
  const blurb = p.blurb.toLowerCase();
  const bug = p.bug.toLowerCase();
  if (p.bug_keywords?.length) {
    assert.ok(bug.length > 0, `${p.id}: has bug_keywords but the source has no "// BUG:" comment`);
    for (const k of p.bug_keywords) {
      assert.ok(bug.includes(k), `${p.id}: "${k}" is not in the source's BUG comment: ${p.bug}`);
      assert.ok(blurb.includes(k), `${p.id}: the card description does not mention "${k}" (BUG comment: ${p.bug})`);
    }
  } else {
    assert.equal(bug, '', `${p.id}: the source has a "// BUG:" comment but the card declares no bug_keywords`);
  }
  assert.ok(p.source.includes('pub fn prop_'), `${p.id}: source shown on the page contains the property`);
}
console.log('PASS card descriptions agree with the BUG comments in the shown Fe source');

let n = 0;
for (const p of doc.props) {
  if (PANIC_PROPS.includes(p.id)) {
    // a property that panics: the page finds the first panicking case by bisecting the case limit, then shrinks by replay
    const rec = recorded.props[p.id];
    const f = st.findPanic(p.id, p.seed, p.cases);
    assert.equal(f.passed, false);
    assert.deepEqual([f.shrunk], p.native.shrunk.map(BigInt), `${p.id}: wasm vs native shrunk`);
    assert.deepEqual([f.shrunk], rec.input.map(BigInt), `${p.id}: wasm vs EVM (check_isolated) shrunk`);
    assert.deepEqual([f.original], p.native.original.map(BigInt), `${p.id}: first panicking input, wasm vs native`);
    assert.deepEqual([f.original], rec.original.map(BigInt), `${p.id}: first panicking input, wasm vs EVM`);
    assert.equal(f.caseIndex, p.native.case_index, `${p.id}: native case`);
    assert.equal(f.caseIndex, rec.case_index, `${p.id}: EVM case`);
    assert.equal(f.steps, p.native.steps, `${p.id}: native steps`);
    assert.equal(f.steps, rec.steps, `${p.id}: EVM steps`);
    assert.equal(f.reason, p.native.reason, `${p.id}: reason, wasm vs native`);
    assert.equal(f.reason, rec.reason, `${p.id}: reason, wasm vs EVM`);
    assert.equal(f.reason, 'panicked: arithmetic overflow');
    // replay: same seed, same result
    assert.deepEqual(st.findPanic(p.id, p.seed, p.cases), f, `${p.id}: replay`);
    // a limit below the first panicking case finds nothing
    if (f.caseIndex > 0) assert.equal(st.findPanic(p.id, p.seed, f.caseIndex).passed, true);
    console.log(`PASS ${p.id.padEnd(15)} seed ${p.seed}: ${f.reason} on case ${f.caseNumber} (bisected in ${f.bisect.length} steps), ${f.steps} shrink steps, ${f.original} -> ${f.shrunk} (wasm = EVM = native)`);
    n++;
    continue;
  }
  const r = st.run(p.id, p.seed, p.cases);
  const rec = recorded.props[p.id];
  if (p.expect === 'pass') {
    assert.equal(r.passed, true, `${p.id} must pass`);
    assert.equal(r.cases, p.cases);
    assert.equal(rec.cases, p.cases, 'EVM ran the same number of cases');
    assert.equal(p.native.failed, 0, 'native passed too');
    console.log(`PASS ${p.id.padEnd(15)} seed ${p.seed}: holds for ${r.cases} cases (wasm = EVM = native; EVM gas ${rec.gas})`);
  } else {
    assert.equal(r.passed, false, `${p.id} must fail`);
    const wasm = r.words, evm = words(p, rec.input), nat = words(p, p.native.shrunk);
    assert.deepEqual(wasm, evm, `${p.id}: wasm vs EVM shrunk`);
    assert.deepEqual(wasm, nat, `${p.id}: wasm vs native shrunk`);
    assert.equal(r.caseIndex, rec.case_index, `${p.id}: EVM case`);
    assert.equal(r.caseIndex, p.native.case_index, `${p.id}: native case`);
    assert.equal(r.steps, rec.steps, `${p.id}: EVM steps`);
    assert.equal(r.steps, p.native.steps, `${p.id}: native steps`);
    assert.equal(r.seed, BigInt(rec.seed), `${p.id}: EVM seed`);
    assert.equal(r.caseNumber, r.caseIndex + 1, `${p.id}: case numbers shown to users are 1-based`);
    // replay: the same seed reproduces the identical failure
    assert.deepEqual(st.run(p.id, p.seed, p.cases), r, `${p.id}: replay`);
    // a different seed gives a different first counterexample
    const first = st.run(p.id, p.seed, p.cases, 0).words;
    const other = st.run(p.id, p.seed + 1, p.cases, 0);
    assert.equal(other.passed, false);
    assert.notDeepEqual(other.words, first, `${p.id}: other seed, other counterexample`);
    // the shrink animation ends at the same minimal value
    const trace = st.shrinkTrace(p.id, p.seed, p.cases);
    assert.equal(trace.length, r.steps + 1, `${p.id}: trace length`);
    assert.deepEqual(trace[0].words, first);
    assert.deepEqual(trace.at(-1).words, r.words);
    console.log(`PASS ${p.id.padEnd(15)} seed ${p.seed}: case ${r.caseNumber}, ${r.steps} shrink steps, ${show(first)} -> ${show(wasm)} (wasm = EVM = native)`);
  }
  n++;
}
// --- the Buggy / Fixed toggle: the fixed code passes the very seed that broke the buggy code, on all three backends ---
assert.deepEqual(doc.props.filter((p) => p.fixed).map((p) => p.id), FIXED_PROPS, 'the props with a fixed version');
let nf = 0;
for (const p of doc.props.filter((q) => q.fixed)) {
  const id = p.id + '_fixed';
  const rec = recorded.props[id];
  assert.ok(p.fixed.source.includes('FIXED:'), `${p.id}: the fixed source says what changed`);
  assert.ok(p.fixed.note.length > 0, `${p.id}: the fixed version has a note`);
  assert.ok(!/BUG:/.test(p.fixed.source), `${p.id}: the fixed source has no BUG comment`);
  // the buggy version fails with this seed (again) ...
  const buggy = PANIC_PROPS.includes(p.id) ? st.findPanic(p.id, p.seed, p.cases) : st.run(p.id, p.seed, p.cases);
  assert.equal(buggy.passed, false, `${p.id}: buggy fails with seed ${p.seed}`);
  // ... and the fixed version passes it: wasm = native = EVM, same number of cases
  const w = PANIC_PROPS.includes(p.id) ? st.findPanic(id, p.seed, p.cases) : st.run(id, p.seed, p.cases);
  assert.equal(w.passed, true, `${p.id}: fixed passes seed ${p.seed} (wasm)`);
  assert.equal(w.cases, p.cases, `${p.id}: wasm ran all ${p.cases} cases`);
  assert.equal(p.fixed.native.failed, 0, `${p.id}: fixed passes (native)`);
  assert.equal(p.fixed.native.cases, p.cases, `${p.id}: native ran all ${p.cases} cases`);
  assert.equal(rec.cases, p.cases, `${p.id}: EVM ran all ${p.cases} cases`);
  assert.ok(rec.gas > 100000, `${p.id}: EVM gas ${rec.gas} shows the cases ran`);
  // replay is identical, and random seeds pass too
  assert.deepEqual(PANIC_PROPS.includes(p.id) ? st.findPanic(id, p.seed, p.cases) : st.run(id, p.seed, p.cases), w, `${p.id}: replay of the fixed run`);
  for (let k = 1n; k <= 25n; k++) {
    const seed = BigInt(p.seed) * 1000003n + k * 7919n;
    const r = PANIC_PROPS.includes(p.id) ? st.findPanic(id, seed, p.cases) : st.run(id, seed, p.cases);
    assert.equal(r.passed, true, `${p.id}: fixed passes random seed ${seed}`);
  }
  console.log(`PASS ${id.padEnd(22)} seed ${p.seed}: buggy fails, fixed passes ${w.cases} cases and 25 more seeds (wasm = EVM = native; EVM gas ${rec.gas})`);
  nf++;
}
console.log(`\nall ${nf} fixed versions pass the seeds that broke the buggy versions, across wasm, sonatina (EVM) and native`);
assert.equal(st.run('buggy_sort', 22, 256, 3).steps, 3); // max_shrinks caps the steps
assert.throws(() => st.run('nope', 1), /unknown property/);
console.log(`\nall ${n} demo properties agree across wasm, sonatina (EVM) and native`);

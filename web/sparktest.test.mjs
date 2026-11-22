// Node test for the web demo: the compiled wasm must agree with the recorded sonatina (EVM) and native results
// for the same seed, replay must reproduce, the passing property must pass, case numbers are 1-based for users,
// and each card's description must agree with its property's `// BUG:` comment.
// Run: node web/sparktest.test.mjs
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { loadSparktest, PROPS } from './sparktest-runner.mjs';

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
assert.equal(st.run('buggy_sort', 22, 256, 3).steps, 3); // max_shrinks caps the steps
assert.throws(() => st.run('nope', 1), /unknown property/);
console.log(`\nall ${n} demo properties agree across wasm, sonatina (EVM) and native`);

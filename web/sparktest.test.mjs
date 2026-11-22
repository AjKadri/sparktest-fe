// Node test for the web demo: the compiled wasm must agree with the recorded sonatina (EVM) and native results
// for the same seed, replay must reproduce, and the passing property must pass. Run: node web/sparktest.test.mjs
import fs from 'node:fs';
import assert from 'node:assert/strict';
import { loadSparktest, PROPS } from './sparktest-runner.mjs';

const here = (f) => new URL(f, import.meta.url);
const doc = JSON.parse(fs.readFileSync(here('./props.json'), 'utf8'));
const bytes = fs.readFileSync(here('./' + doc.wasm.file));
assert.equal(bytes.length, doc.wasm.bytes, 'wasm size matches props.json');
const st = await loadSparktest(bytes);
const pad4 = (a) => [...a, 0, 0, 0, 0].slice(0, 4).map(BigInt);
const show = (a) => '[' + a.join(', ') + ']';

assert.deepEqual(doc.props.map((p) => p.id), PROPS);
let n = 0;
for (const p of doc.props) {
  const r = st.run(p.id, p.seed, p.cases);
  if (p.expect === 'pass') {
    assert.equal(r.passed, true, `${p.id} must pass`);
    assert.equal(r.cases, p.cases);
    assert.equal(p.evm.cases, p.cases, 'EVM ran the same number of cases');
    assert.equal(p.native.failed, 0, 'native passed too');
    console.log(`PASS ${p.id.padEnd(15)} seed ${p.seed}: holds for ${r.cases} cases (wasm = EVM = native; EVM gas ${p.evm.gas})`);
  } else {
    assert.equal(r.passed, false, `${p.id} must fail`);
    const wasm = r.words, evm = pad4(p.evm.input), nat = pad4(p.native.shrunk);
    assert.deepEqual(wasm, evm, `${p.id}: wasm vs EVM shrunk`);
    assert.deepEqual(wasm, nat, `${p.id}: wasm vs native shrunk`);
    for (const [who, o] of [['EVM', p.evm], ['native', p.native]]) {
      assert.equal(r.case, o.case, `${p.id}: ${who} case`);
      assert.equal(r.steps, o.steps, `${p.id}: ${who} steps`);
    }
    assert.equal(r.seed, BigInt(p.evm.seed), `${p.id}: EVM seed`);
    // replay: the same seed reproduces the identical failure
    const again = st.run(p.id, p.seed, p.cases);
    assert.deepEqual(again, r, `${p.id}: replay`);
    // a different seed gives a different first counterexample
    const first = st.run(p.id, p.seed, p.cases, 0).words;
    const other = st.run(p.id, p.seed + 1, p.cases, 0);
    assert.equal(other.passed, false);
    assert.notDeepEqual(other.words, first, `${p.id}: other seed, other counterexample`);
    // the shrink animation ends at the same minimal value and shrinks monotonically in step count
    const trace = st.shrinkTrace(p.id, p.seed, p.cases);
    assert.equal(trace.length, r.steps + 1, `${p.id}: trace length`);
    assert.deepEqual(trace[0].words, first);
    assert.deepEqual(trace.at(-1).words, r.words);
    console.log(`PASS ${p.id.padEnd(15)} seed ${p.seed}: case ${r.case}, ${r.steps} shrink steps, ${show(first)} -> ${show(wasm)} (wasm = EVM = native)`);
  }
  n++;
}
// shrinking semantics: max_shrinks caps the steps
const capped = st.run('buggy_sort', 22, 256, 3);
assert.equal(capped.steps, 3);
// an unknown property is rejected
assert.throws(() => st.run('nope', 1), /unknown property/);
console.log(`\nall ${n} demo properties agree across wasm, sonatina (EVM) and native`);

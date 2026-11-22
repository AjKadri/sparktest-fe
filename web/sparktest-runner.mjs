// Sparktest runner: loads the compiled Fe demo module and runs properties. Used by the page (app.js) and the Node test.
// No dependencies; works in browsers and Node 20+.

export const PROPS = ['capped_mint', 'buggy_sort', 'pair_sum', 'saturating_add', 'bank_sequence'];
const U64 = (1n << 64n) - 1n;

// bytes: ArrayBuffer | Uint8Array of the .wasm. Returns { run, shrinkTrace }.
export async function loadSparktest(bytes) {
  let last = null; // result of the current call, set by the imports
  let seqWords = []; // words of a sequence counterexample, reported one by one by st_word
  let memory = null;
  const imports = {
    env: {
      st_pass: (cases) => { last = { passed: true, cases }; },
      st_word: (index, value) => { seqWords[Number(index)] = value; },
      st_fail_seq: (seed, kase, steps, nwords) => { last = { passed: false, seed, caseIndex: kase, steps, words: seqWords.slice(0, Number(nwords)) }; },
      st_fail: (seed, kase, steps, w0, w1, w2, w3) => { last = { passed: false, seed, caseIndex: kase, steps, words: [w0, w1, w2, w3] }; },
      // Fe panics (overflow, assert) call this with Solidity Panic/Error data
      __fe_revert: (addr, len) => {
        const data = Array.from(new Uint8Array(memory.buffer, addr, len)).map((b) => b.toString(16).padStart(2, '0')).join('');
        throw new Error('Fe panic: 0x' + data);
      },
    },
  };
  const { instance } = await WebAssembly.instantiate(bytes, imports);
  memory = instance.exports.memory;

  // Case numbers: `caseIndex` is 0-based (internal); `caseNumber` is 1-based (what users see).
  // Runs one property. seed/cases/maxShrinks may be Number or BigInt (u64). max_shrinks = 0 returns the unshrunk counterexample.
  function run(prop, seed, cases = 256, maxShrinks = 1000) {
    const fn = instance.exports['run_' + prop];
    if (!fn) throw new Error('unknown property: ' + prop);
    last = null;
    seqWords = [];
    const s = BigInt(seed) & U64;
    const held = fn(s, BigInt(cases), BigInt(maxShrinks));
    if (!last) throw new Error('property returned without reporting');
    return held
      ? { passed: true, cases: Number(last.cases), seed: s }
      : { passed: false, seed: s, caseIndex: Number(last.caseIndex), caseNumber: Number(last.caseIndex) + 1, steps: Number(last.steps), words: last.words.map(BigInt) };
  }

  // The shrink animation: [unshrunk, after 1 step, after 2 steps, ...]. Each entry is a full run with max_shrinks = k.
  function shrinkTrace(prop, seed, cases = 256, limit = 5000) {
    const trace = [];
    for (let k = 0; k < limit; k++) {
      const r = run(prop, seed, cases, k);
      if (r.passed) return trace; // property holds: nothing to shrink
      trace.push({ step: k, words: r.words, caseIndex: r.caseIndex });
      if (r.steps < k) { trace.pop(); break; } // no more progress: the previous entry is minimal
    }
    return trace;
  }

  return { run, shrinkTrace };
}

// A fresh random u64 seed (browser or Node).
export function randomSeed() {
  const a = new Uint32Array(2);
  globalThis.crypto.getRandomValues(a);
  return (BigInt(a[0]) << 32n) | BigInt(a[1]);
}

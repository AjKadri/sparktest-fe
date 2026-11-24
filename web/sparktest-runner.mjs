// Sparktest runner: loads the compiled Fe demo module and runs properties. Used by the page (app.js) and the Node test.
// No dependencies; works in browsers and Node 20+.

export const PROPS = ['capped_mint', 'buggy_sort', 'pair_sum', 'saturating_add', 'bank_sequence', 'panic_overflow'];
export const PANIC_PROPS = ['panic_overflow'];
// properties that also have a fixed version, run under the name <id>_fixed (same seeds, same number of cases)
export const FIXED_PROPS = ['capped_mint', 'buggy_sort', 'bank_sequence', 'panic_overflow'];
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
  const { instance: first, module } = await WebAssembly.instantiate(bytes, imports);
  let instance = first;
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

  // ---- panics: a panic is a trap (the module calls the __fe_revert import, which throws), so it cannot be returned as false. ----
  // findPanic replays: bisect the case limit to the first case that panics, then shrink by evaluating candidates one at a time.
  const PANIC_TEXT = { 0x01: 'assertion failed', 0x11: 'arithmetic overflow', 0x12: 'division by zero', 0x32: 'index out of bounds' };
  function panicText(e) {
    const m = /Fe panic: 0x4e487b71([0-9a-f]{64})/.exec(String(e && e.message));
    if (!m) return 'trap: ' + String(e && e.message);
    const code = parseInt(m[1], 16);
    return 'panicked: ' + (PANIC_TEXT[code] ?? 'panic code 0x' + code.toString(16));
  }
  // after a panic the old instance may hold a half-unwound stack: use a fresh one (same compiled module)
  function fresh() { instance = new WebAssembly.Instance(module, imports); memory = instance.exports.memory; }

  function findPanic(name, seed, maxCases = 256) {
    const s = BigInt(seed) & U64;
    const x = (kind) => instance.exports[`${kind}_${name}`];
    if (!x('run') && !instance.exports[`run_${name}_cases`]) throw new Error('unknown panic property: ' + name);
    let runs = 0;
    const bisect = [];
    const fails = (n) => {
      runs++;
      try { return !instance.exports[`run_${name}_cases`](s, BigInt(n)); } catch (e) { fresh(); return true; }
    };
    if (!fails(maxCases)) return { passed: true, cases: maxCases, seed: s, runs };
    let lo = 1, hi = maxCases;
    while (lo < hi) {
      const mid = Math.floor((lo + hi) / 2);
      const f = fails(mid);
      bisect.push({ cases: mid, fails: f });
      if (f) hi = mid; else lo = mid + 1;
    }
    const caseIndex = lo - 1;
    const original = instance.exports[`gen_${name}`](s, BigInt(caseIndex));
    // evaluates one input: null if it holds, otherwise the reason it fails
    const reasonOf = (v) => {
      runs++;
      try { return instance.exports[`eval_${name}`](v) ? null : 'returned false'; } catch (e) { const t = panicText(e); fresh(); return t; }
    };
    const originalReason = reasonOf(original);
    let cur = original, steps = 0, reason = originalReason;
    const trace = [original];
    while (steps < 1000) {
      let i = 0n, accepted = false;
      for (;;) {
        const c = instance.exports[`cand_${name}`](cur, i);
        if (c === cur) break;                    // no more candidates
        const r = reasonOf(c);
        if (r !== null) { cur = c; reason = r; steps++; trace.push(c); accepted = true; break; }
        i++;
      }
      if (!accepted) break;
    }
    return { passed: false, seed: s, caseIndex, caseNumber: caseIndex + 1, original, shrunk: cur, steps, reason, originalReason, runs, bisect, trace };
  }

  return { run, shrinkTrace, findPanic };
}

// A fresh random u64 seed (browser or Node).
export function randomSeed() {
  const a = new Uint32Array(2);
  globalThis.crypto.getRandomValues(a);
  return (BigInt(a[0]) << 32n) | BigInt(a[1]);
}

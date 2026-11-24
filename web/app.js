// Sparktest demo page. All paths are relative so the page works from any sub-path (e.g. GitHub Pages).
import { loadSparktest, randomSeed } from './sparktest-runner.mjs';

const $ = (id) => document.getElementById(id);
const el = (tag, cls, html) => { const e = document.createElement(tag); if (cls) e.className = cls; if (html !== undefined) e.innerHTML = html; return e; };
const esc = (s) => String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
const reduceMotion = matchMedia('(prefers-reduced-motion: reduce)').matches;
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

// --- minimal Fe highlighter (escape first, then tag tokens in a single pass) ---
function highlight(src) {
  return esc(src).replace(
    /(\/\/[^\n]*)|\b(pub|fn|let|var|if|else|return|while|const|as)\b|\b(u8|u16|u32|u64|u128|u256|bool|usize)\b|\b(\d+)\b/g,
    (m, cm, kw, ty, num) => (cm ? `<span class="cm">${cm}</span>` : kw ? `<span class="kw">${kw}</span>` : ty ? `<span class="ty">${ty}</span>` : `<span class="num">${num}</span>`),
  );
}

let doc, recorded, st, current, seed, busy = false, skipRequested = false, lastResult = null;
let fixed = false;        // the Buggy / Fixed toggle: true runs the fixed version of the current property
let brokenSeed = null;    // the seed of the latest buggy failure of the current property (what "Replay this seed" runs on the fixed code)
// the picker label of the current property in Fixed mode (the card keeps its title otherwise)
const FIXED_LABELS = { buggy_sort: 'Sort' };
const runId = () => current.id + (fixed ? '_fixed' : '');

async function boot() {
  try {
    const [d, rec, bytes] = await Promise.all([
      fetch('props.json').then((r) => { if (!r.ok) throw new Error('props.json: HTTP ' + r.status); return r.json(); }),
      fetch('recorded.json').then((r) => { if (!r.ok) throw new Error('recorded.json: HTTP ' + r.status); return r.json(); }),
      fetch('demo_wasm.wasm').then((r) => { if (!r.ok) throw new Error('demo_wasm.wasm: HTTP ' + r.status); return r.arrayBuffer(); }),
    ]);
    doc = d;
    recorded = rec;
    st = await loadSparktest(bytes);
  } catch (e) {
    $('stage').innerHTML = `<p><span class="verdict bad">Could not load</span></p><p class="note">${esc(e.message)}. Serve this folder over http (for example <code>python3 -m http.server 8765</code>) rather than opening the file directly.</p>`;
    return;
  }
  buildPicker();
  select(doc.props[0].id);
  $('build').textContent = `Compiled Fe → WebAssembly: ${doc.wasm.bytes.toLocaleString()} bytes, imports ${doc.wasm.imports.join(', ')}. EVM recordings made at commit ${recorded.generated.commit}, ${recorded.generated.date}, ${recorded.generated.fe}.`;
  $('run').onclick = () => start(seed);
  $('random').onclick = () => { seed = randomSeed(); showSeed(); start(seed); };
  $('replay').onclick = () => start(seed, true);
  $('skip').onclick = () => { skipRequested = true; };
  $('mode-buggy').onclick = () => { if (!busy) setMode(false); };
  $('mode-fixed').onclick = () => { if (!busy) setMode(true); };
  setBusy(false);
}

function buildPicker() {
  const box = $('picker');
  for (const p of doc.props) {
    const b = el('button', 'card');
    b.type = 'button';
    b.setAttribute('role', 'radio');
    b.dataset.id = p.id;
    b.innerHTML = `<span class="t"><span class="name">${esc(p.title)}</span><span class="tag ${p.expect}">${p.expect === 'fail' ? 'has a bug' : 'holds'}</span></span><span class="d">${esc(p.blurb)}</span>`;
    b.onclick = () => { if (!busy) select(p.id); };
    box.appendChild(b);
  }
}

function select(id) {
  current = doc.props.find((p) => p.id === id);
  seed = BigInt(current.seed);
  lastResult = null;
  fixed = false;
  brokenSeed = null;
  for (const b of $('picker').children) b.setAttribute('aria-checked', String(b.dataset.id === id));
  showSeed();
  paintMode();
  $('stage').innerHTML = '<p class="muted">Press <strong>Run</strong>. The wasm module generates inputs from the seed, checks the property and, on failure, shrinks the input.</p>';
  $('replay').disabled = true;
}

// Shows the buggy or the fixed code for the current property (the toggle only exists for properties that have a fixed version).
function paintMode() {
  const hasFix = !!current.fixed;
  $('modebox').hidden = !hasFix;
  $('mode-buggy').setAttribute('aria-checked', String(!fixed));
  $('mode-fixed').setAttribute('aria-checked', String(fixed));
  $('modehint').textContent = hasFix ? (fixed ? current.fixed.note : 'This version has a planted bug.') : '';
  $('source-h').textContent = fixed ? 'The fixed code, in Fe' : 'The property, in Fe';
  $('source').firstElementChild.innerHTML = highlight(fixed ? current.fixed.source : current.source);
  $('prop-claim').innerHTML = fixed
    ? `Claim: <strong>${esc(current.property)}</strong> (unchanged). This is the fixed code, and it should hold for every seed, including the one that broke the buggy version.`
    : `Claim: <strong>${esc(current.property)}</strong>. ${current.expect === 'fail' ? 'This property is false; Sparktest should find out why.' : 'This property is true; Sparktest should find nothing.'}`;
  $('replay').textContent = fixed ? 'Replay this seed' : 'Replay';
  for (const b of $('picker').children) {   // every card, so leaving a property while it is on Fixed restores its title
    const p = doc.props.find((q) => q.id === b.dataset.id);
    b.querySelector('.name').textContent = fixed && p === current && FIXED_LABELS[p.id] ? FIXED_LABELS[p.id] : p.title;
  }
  renderRecorded();
}

function setMode(f) {
  if (!current.fixed || f === fixed) return;
  fixed = f;
  lastResult = null;
  paintMode();
  $('stage').innerHTML = fixed
    ? (brokenSeed !== null
      ? `<p class="muted">Fixed code. Press <strong>Replay this seed</strong> to run it with seed <code>${brokenSeed}</code>, the seed that broke the buggy version. Then press <strong>Random seed</strong> to try others.</p>`
      : '<p class="muted">Fixed code. Press <strong>Run</strong> (or run the buggy version first to get a seed that breaks it).</p>')
    : '<p class="muted">Buggy code. Press <strong>Run</strong>.</p>';
  setBusy(false);
}

function showSeed() {
  $('seed').textContent = `${seed}  (0x${seed.toString(16)})`;
}

function setBusy(b) {
  busy = b;
  for (const id of ['run', 'random']) $(id).disabled = b;
  $('replay').disabled = b || (!lastResult && !fixed);
  for (const id of ['mode-buggy', 'mode-fixed']) $(id).disabled = b;
  $('skip').hidden = !b;
  for (const c of $('picker').children) c.disabled = b;
}

const KINDS = ['deposit', 'withdraw', 'transfer'];
// a sequence's words are [length, then 4 words per command: kind, a, b, amount]
function seqCommands(words) {
  const n = Number(words[0]);
  const out = [];
  for (let i = 0; i < n; i++) {
    const [k, a, b, amt] = words.slice(1 + 4 * i, 5 + 4 * i).map(Number);
    out.push(k === 0 ? `deposit(account ${a}, ${amt})` : k === 1 ? `withdraw(account ${a}, ${amt})` : `transfer(account ${a} to account ${b}, ${amt})`);
  }
  return out;
}

function seqHtml(words, prev, cls = '') {
  const cmds = seqCommands(words);
  const before = prev ? seqCommands(prev) : null;
  return `<p class="stepline">${cmds.length} command${cmds.length === 1 ? '' : 's'}</p><ol class="seq ${cls}">${cmds.map((c, i) => `<li class="${before && before[i] !== c ? 'changed' : ''}">${esc(c)}</li>`).join('')}</ol>`;
}

function fmtInput(words) {
  const n = current.labels.length;
  return current.labels.map((l, i) => ({ label: l, value: words[i].toString() })).slice(0, n);
}

function valsHtml(words, prev, cls = '') {
  if (current.seq) return seqHtml(words, prev, cls);
  return `<div class="vals">${fmtInput(words).map((v, i) => {
    const changed = prev && prev[i] !== words[i];
    return `<div class="val ${cls}${changed ? ' changed' : ''}"><span class="n">${esc(v.label)}</span><span class="v">${esc(v.value)}</span></div>`;
  }).join('')}</div>`;
}

// A property that PANICS cannot return false: the page catches the trap, bisects the case limit to the first panicking case, and shrinks by replay.
async function startPanic(s, isReplay) {
  const stage = $('stage');
  const t0 = performance.now();
  const f = st.findPanic(runId(), s, current.cases);
  const ms = performance.now() - t0;
  if (f.passed) {
    stage.innerHTML = fixed ? fixedPassHtml(f.cases, s) : `<div class="block"><h3>Result</h3><p class="big"><span class="verdict good">Held</span></p><p class="note">No panic or failure in ${f.cases} cases for this seed. Try a random seed.</p></div>`;
    lastResult = f; setBusy(false); return;
  }
  brokenSeed = s;
  const one = (v) => `<div class="vals"><div class="val"><span class="n">x</span><span class="v">${esc(v)}</span></div></div>`;
  stage.innerHTML = '';
  const b1 = el('div', 'block');
  b1.innerHTML = `<h3>Panic caught</h3><p class="big"><span class="verdict bad">${esc(f.originalReason)}</span> on case ${f.caseNumber}</p>${one(f.original)}
    <p class="note">The property did not return: the module trapped. The page found the first panicking case by <strong>bisecting the case limit</strong> (${f.bisect.length} steps: ${f.bisect.map((b) => `limit ${b.cases}: ${b.fails ? 'panic' : 'ok'}`).join(', ')}), ${f.runs} module runs in all, taking ${ms.toFixed(1)} ms (measured in your browser, in WebAssembly).</p>`;
  stage.appendChild(b1);
  const b2 = el('div', 'block');
  b2.innerHTML = `<h3>Shrinking by replay</h3><div id="shr"></div><p class="stepline" id="stepline"></p><div class="bar"><i id="barfill"></i></div>`;
  stage.appendChild(b2);
  const total = f.trace.length - 1;
  const delay = reduceMotion ? 0 : Math.max(12, Math.min(90, 3200 / Math.max(total, 1)));
  let prev = null;
  for (let i = 0; i < f.trace.length; i++) {
    $('shr').innerHTML = `<div class="vals"><div class="val${prev !== null && prev !== f.trace[i] ? ' changed' : ''}"><span class="n">x</span><span class="v">${esc(f.trace[i])}</span></div></div>`;
    $('stepline').textContent = i === 0 ? 'step 0: the input as first found' : `step ${i} of ${total}: smaller, still fails`;
    $('barfill').style.width = (total === 0 ? 100 : (i / total) * 100) + '%';
    prev = f.trace[i];
    if (!skipRequested && delay) await sleep(delay);
  }
  $('shr').innerHTML = `<div class="vals"><div class="val final"><span class="n">x</span><span class="v">${esc(f.shrunk)}</span></div></div>`;
  $('stepline').textContent = `done after ${total} shrink step${total === 1 ? '' : 's'}`;
  const b3 = el('div', 'block');
  const same = lastResult && !lastResult.passed && lastResult.seed === f.seed && lastResult.steps === f.steps && lastResult.caseIndex === f.caseIndex && lastResult.shrunk === f.shrunk;
  b3.innerHTML = `<h3>Minimal counterexample</h3>${one(f.shrunk)}
    <p class="note">${esc(f.reason)} · seed <code>${f.seed}</code> · first panic on case ${f.caseNumber} · ${f.steps} shrink steps. 18446744073709552 is the smallest x for which x * 1000 does not fit in 64 bits.</p>
    ${isReplay ? (same ? '<p class="note ok">Replayed with the same seed: identical panic, identical shrink.</p>' : '<p class="note">Replayed.</p>') : '<p class="note">Press <strong>Replay</strong> to reproduce this exact panic from the seed, or <strong>Random seed</strong> to hunt for another.</p>'}
    <p class="note small">How Sparktest handles panics: in a wasm or native run a panic is a trap or an abort, so it is found by bisecting and replaying (this page, <code>scripts/find-panic.sh</code>); on the EVM backend each evaluation runs inside a harness contract called through <code>try_call</code>, so a panic is a failed call. Properties here are prebuilt.</p>`;
  stage.appendChild(b3);
  lastResult = f;
  setBusy(false);
}

function fmtMs(ms) { return ms < 0.01 ? '<0.01 ms' : `${ms.toFixed(ms < 1 ? 2 : 1)} ms`; }

// Browsers coarsen performance.now(), and one run takes well under a millisecond, so: warm up once, time REPS
// identical runs together and report the mean per run. Returns [result, milliseconds per run].
const REPS = 200;

// The result of the fixed code: it passes, with the count and the seed (and a pointer to the seed that broke the buggy version).
function fixedPassHtml(cases, s, ms) {
  const same = brokenSeed !== null && brokenSeed === s;
  return `<div class="block"><h3>Result</h3><p class="big"><span class="verdict good">FIXED: passes ${cases} cases (seed ${s})</span></p>
    ${ms !== undefined ? `<p class="counter">${cases} cases in ${fmtMs(ms)}<small>mean of ${REPS} runs, measured in your browser, in WebAssembly</small></p>` : ''}
    <p class="note ${same ? 'ok' : ''}">${same ? `This is the seed that broke the buggy version: the same inputs now pass.` : brokenSeed !== null ? 'A different seed from the one that broke the buggy version; it passes too.' : 'Flip back to Buggy and press Run to see this property fail.'} ${current.fixed.note}</p>
    <p class="note small">Run it with <strong>Random seed</strong> a few times: the fixed version holds for all of them. These are prebuilt properties; the page cannot compile your own Fe.</p></div>`;
}
function timed(f) {
  let r = f();
  const t0 = performance.now();
  for (let i = 0; i < REPS; i++) r = f();
  return [r, (performance.now() - t0) / REPS];
}

async function start(s, isReplay = false) {
  if (busy) return;
  setBusy(true);
  skipRequested = false;
  const stage = $('stage');
  const cases = current.cases;
  if (current.panic) { await startPanic(s, isReplay); return; }
  const [r, ms] = timed(() => st.run(runId(), s, cases));

  if (r.passed && fixed) {
    stage.innerHTML = fixedPassHtml(r.cases, s, ms);
    lastResult = r;
    setBusy(false);
    return;
  }
  if (r.passed) {
    stage.innerHTML = `<div class="block"><h3>Result</h3><p class="big"><span class="verdict good">Held</span></p>
      <p class="counter">${r.cases} cases in ${fmtMs(ms)}<small>mean of ${REPS} runs, measured in your browser, in WebAssembly</small></p>
      <p class="note">No counterexample in ${r.cases} cases (edge values such as 0, 1, max and powers of two are generated on purpose). Run again with a random seed to try another sequence.</p></div>`;
    lastResult = r;
    setBusy(false);
    return;
  }

  brokenSeed = s;
  const trace = st.shrinkTrace(current.id, s, cases);
  const first = trace[0].words;
  stage.innerHTML = '';
  const b1 = el('div', 'block');
  b1.innerHTML = `<h3>First counterexample</h3><p class="big"><span class="verdict bad">Property failed</span> on case ${r.caseNumber}</p>${valsHtml(first, null)}
    <p class="note">Search and shrink together took ${fmtMs(ms)} (mean of ${REPS} runs, measured in your browser, in WebAssembly).</p>`;
  stage.appendChild(b1);

  const b2 = el('div', 'block');
  b2.innerHTML = `<h3>Shrinking</h3><div id="shr"></div><p class="stepline" id="stepline"></p><div class="bar"><i id="barfill"></i></div>`;
  stage.appendChild(b2);
  const total = trace.length - 1;
  const delay = reduceMotion ? 0 : Math.max(12, Math.min(90, 3200 / Math.max(total, 1)));
  let prev = null;
  for (let i = 0; i < trace.length; i++) {
    const w = trace[i].words;
    $('shr').innerHTML = valsHtml(w, prev);
    $('stepline').textContent = i === 0 ? `step 0: the input as first found` : `step ${i} of ${total}: smaller, still fails`;
    $('barfill').style.width = (total === 0 ? 100 : (i / total) * 100) + '%';
    prev = w;
    if (!skipRequested && delay) await sleep(delay);
  }
  $('shr').innerHTML = valsHtml(trace.at(-1).words, null, 'final');
  $('stepline').textContent = `done after ${total} shrink step${total === 1 ? '' : 's'}`;

  const b3 = el('div', 'block');
  const same = lastResult && !lastResult.passed && lastResult.seed === r.seed && lastResult.steps === r.steps && lastResult.caseIndex === r.caseIndex && lastResult.words.every((x, i) => x === r.words[i]);
  b3.innerHTML = `<h3>Minimal counterexample</h3>${valsHtml(r.words, null, 'final')}
    <p class="note">seed <code>${r.seed}</code> · found on case ${r.caseNumber} · ${r.steps} shrink steps</p>
    ${isReplay ? (same ? '<p class="note ok">Replayed with the same seed: identical counterexample, identical shrink.</p>' : '<p class="note">Replayed.</p>') : '<p class="note">Press <strong>Replay</strong> to reproduce this exact failure from the seed, or <strong>Random seed</strong> to hunt for another.</p>'}`;
  stage.appendChild(b3);
  lastResult = r;
  setBusy(false);
}

function renderRecorded() {
  const e = recorded.props[runId()];
  const box = $('recorded');
  const rows = [];
  if (fixed) {
    rows.push(['seed', current.seed], ['result', `held for ${e.cases} cases`], ['gas for the run', e.gas.toLocaleString()]);
  } else if (current.expect === 'fail') {
    const input = current.panic ? `x = ${e.input[0]}  (${e.reason})` : current.seq ? seqCommands(e.input.map(BigInt)).join('; ') : current.labels.map((l, i) => `${l} = ${e.input[i] ?? 0}`).join(', ');
    rows.push(['seed', e.seed], ['failed on case', e.case_index + 1], ['shrink steps', e.steps], ['shrunk input', input]);
  } else {
    rows.push(['seed', current.seed], ['result', `held for ${e.cases} cases`], ['gas for the run', e.gas.toLocaleString()]);
  }
  rows.push(['commit', recorded.generated.commit], ['recorded', recorded.generated.date]);
  box.innerHTML = `<span class="badge">Recorded, not computed here</span>
    <dl>${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>
    <p class="cmd">to re-record: <code>${esc(recorded.command)}</code></p>
    <p class="note small">This run happened on the sonatina EVM test backend (not in your browser), with the same seed${current.panic && !fixed ? ', through check_isolated (each evaluation inside a harness contract, called with try_call)' : ''}. ${fixed ? 'The native backend also passes all ' + current.fixed.native.cases + ' cases (counted by the repo\'s native tests).' : current.panic ? 'The native backend (<code>scripts/find-panic.sh</code>) gives the same result.' : 'The native backend gives the same result (checked by <code>scripts/cross-check.sh</code>).'}</p>`;
}

boot();

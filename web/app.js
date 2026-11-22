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
  setBusy(false);
}

function buildPicker() {
  const box = $('picker');
  for (const p of doc.props) {
    const b = el('button', 'card');
    b.type = 'button';
    b.setAttribute('role', 'radio');
    b.dataset.id = p.id;
    b.innerHTML = `<span class="t">${esc(p.title)}<span class="tag ${p.expect}">${p.expect === 'fail' ? 'has a bug' : 'holds'}</span></span><span class="d">${esc(p.blurb)}</span>`;
    b.onclick = () => { if (!busy) select(p.id); };
    box.appendChild(b);
  }
}

function select(id) {
  current = doc.props.find((p) => p.id === id);
  seed = BigInt(current.seed);
  lastResult = null;
  for (const b of $('picker').children) b.setAttribute('aria-checked', String(b.dataset.id === id));
  showSeed();
  $('source').firstElementChild.innerHTML = highlight(current.source);
  $('prop-claim').innerHTML = `Claim: <strong>${esc(current.property)}</strong>. ${current.expect === 'fail' ? 'This property is false; Sparktest should find out why.' : 'This property is true; Sparktest should find nothing.'}`;
  renderRecorded();
  $('stage').innerHTML = '<p class="muted">Press <strong>Run</strong>. The wasm module generates inputs from the seed, checks the property and, on failure, shrinks the input.</p>';
  $('replay').disabled = true;
}

function showSeed() {
  $('seed').textContent = `${seed}  (0x${seed.toString(16)})`;
}

function setBusy(b) {
  busy = b;
  for (const id of ['run', 'random']) $(id).disabled = b;
  $('replay').disabled = b || !lastResult;
  $('skip').hidden = !b;
  for (const c of $('picker').children) c.disabled = b;
}

function fmtInput(words) {
  const n = current.labels.length;
  return current.labels.map((l, i) => ({ label: l, value: words[i].toString() })).slice(0, n);
}

function valsHtml(words, prev, cls = '') {
  return `<div class="vals">${fmtInput(words).map((v, i) => {
    const changed = prev && prev[i] !== words[i];
    return `<div class="val ${cls}${changed ? ' changed' : ''}"><span class="n">${esc(v.label)}</span><span class="v">${esc(v.value)}</span></div>`;
  }).join('')}</div>`;
}

function fmtMs(ms) { return ms < 0.01 ? '<0.01 ms' : `${ms.toFixed(ms < 1 ? 2 : 1)} ms`; }

// runs `f` once to warm up, then once more under performance.now(); returns [result, milliseconds]
function timed(f) {
  f();
  const t0 = performance.now();
  const r = f();
  return [r, performance.now() - t0];
}

async function start(s, isReplay = false) {
  if (busy) return;
  setBusy(true);
  skipRequested = false;
  const stage = $('stage');
  const cases = current.cases;
  const [r, ms] = timed(() => st.run(current.id, s, cases));

  if (r.passed) {
    stage.innerHTML = `<div class="block"><h3>Result</h3><p class="big"><span class="verdict good">Held</span></p>
      <p class="counter">${r.cases} cases in ${fmtMs(ms)}<small>measured in your browser, in WebAssembly</small></p>
      <p class="note">No counterexample in ${r.cases} cases (edge values such as 0, 1, max and powers of two are generated on purpose). Run again with a random seed to try another sequence.</p></div>`;
    lastResult = r;
    setBusy(false);
    return;
  }

  const trace = st.shrinkTrace(current.id, s, cases);
  const first = trace[0].words;
  stage.innerHTML = '';
  const b1 = el('div', 'block');
  b1.innerHTML = `<h3>First counterexample</h3><p class="big"><span class="verdict bad">Property failed</span> on case ${r.caseNumber}</p>${valsHtml(first, null)}
    <p class="note">Search and shrink together took ${fmtMs(ms)} (measured in your browser, in WebAssembly).</p>`;
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
  const e = recorded.props[current.id];
  const box = $('recorded');
  const rows = [];
  if (current.expect === 'fail') {
    const input = current.labels.map((l, i) => `${l} = ${e.input[i] ?? 0}`).join(', ');
    rows.push(['seed', e.seed], ['failed on case', e.case_index + 1], ['shrink steps', e.steps], ['shrunk input', input]);
  } else {
    rows.push(['seed', current.seed], ['result', `held for ${e.cases} cases`], ['gas for the run', e.gas.toLocaleString()]);
  }
  rows.push(['commit', recorded.generated.commit], ['recorded', recorded.generated.date]);
  box.innerHTML = `<span class="badge">Recorded, not computed here</span>
    <dl>${rows.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join('')}</dl>
    <p class="cmd">to re-record: <code>${esc(recorded.command)}</code></p>
    <p class="note small">This run happened on the sonatina EVM test backend (not in your browser), with the same seed. The native backend gives the same result (checked by <code>scripts/cross-check.sh</code>).</p>`;
}

boot();

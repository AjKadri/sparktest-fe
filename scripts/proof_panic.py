"""Panic recovery section of docs/PROOF.md. Imported by proof.py. Runs the same planted properties through
  - sonatina: check_isolated (each evaluation inside a harness contract, via try_call)            tests-isolated
  - native:   scripts/find-panic.sh (bisect the case limit to the first abort, shrink by replay)  replay-native
  - wasm:     the demo page's findPanic (catch the trap, bisect, replay), run here with Node      web/sparktest-runner.mjs
and compares them with the expectations written before the runs (docs/EXPECTATIONS.md, L7b)."""
import json, os, re, subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TEXT = {273: 'panicked: arithmetic overflow', 274: 'panicked: division by zero', 1: 'returned false'}

def parse_isolated(out):
    res, gas = {}, None
    for line in out.splitlines():
        m = re.search(r'data: (0x[0-9a-f]*) \}', line)
        if not m:
            continue
        h = m.group(1)[2:]
        w = [int(h[i:i + 64], 16) for i in range(0, len(h), 64)]
        if len(w) == 3:
            gas = dict(held=w[0], false=w[1], panicked=w[2])
        elif len(w) > 9 and w[6] == 9 * 32:
            def arr(off):
                j = off // 32
                return w[j + 1:j + 1 + w[j]]
            res[w[0]] = dict(case=w[2], steps=w[3], reason=w[4], original=arr(w[6]), shrunk=arr(w[7]), gas=w[8])
    return res, gas

def native(run, prop, seed):
    r = run([os.path.join(ROOT, 'scripts/find-panic.sh'), prop, str(seed), '256']).stdout
    m = re.search(r'RESULT prop=\S+ seed=\d+ case=(\d+) steps=(\d+) original="([^"]*)" shrunk="([^"]*)" reason="([^"]*)" native_runs=(\d+)', r)
    if not m:
        return None, r
    return dict(case=int(m.group(1)) - 1, steps=int(m.group(2)), original=[int(x) for x in m.group(3).split()],
                shrunk=[int(x) for x in m.group(4).split()], reason=m.group(5), runs=int(m.group(6))), r

def section(run, problems):
    iso_out = run(['fe', 'test', '--show-logs'], cwd='tests-isolated').stdout
    if 'test result: ok' not in iso_out:
        problems.append('tests-isolated did not pass:\n' + iso_out[-1200:])
    iso, gas = parse_isolated(iso_out)
    wasm = json.loads(run(['node', 'scripts/panic_wasm.mjs', '8101']).stdout or '{}')
    cases = [(1, 'overflow', 8101, 'overflow: `x * 1000 / 1000 == x` over `u64`', 'x = 18446744073709552, panicked: arithmetic overflow', [18446744073709552], 273),
             (2, 'divzero', 8102, 'divzero: `a / b * b <= a` over `(u32, u32)`', '(a, b) = (0, 0), panicked: division by zero', [0, 0], 274),
             (3, 'false', 8103, 'a normal false-returning property: `x < 1000` over `u256`', 'x = 1000, returned false (identical to `check`)', [1000], 1)]
    s = ['## Panic recovery: properties whose code panics (new APIs; `check` is unchanged)', '',
         'A panic inside a property used to end the whole test with no report. Expected results were written before the runs (docs/EXPECTATIONS.md, section "L7b"). The same seed gives the same input stream on every backend,',
         'so the first failing case, the shrunk input and the number of shrink steps are expected to be identical. Case numbers are 1-based.', '',
         '- **sonatina**: `check_isolated` runs each evaluation inside a harness contract called through `evm.try_call`; a panic is a failed call, and the reason is read from the revert data (`Panic(0x11)`, `Panic(0x12)`).',
         '- **native**: a panic aborts the process, so `scripts/find-panic.sh` drives the replay executable: it bisects the case limit to the first aborting case, then shrinks by replaying candidates as single-case runs (the reason is the process\'s stderr text).',
         '- **wasm** (the demo page): the panic is a trap thrown into JavaScript; the page bisects and replays the same way (overflow property only).', '',
         '| property | expected | sonatina (isolated) | native (find-panic.sh) | wasm (demo page) | agree |', '|---|---|---|---|---|---|']
    transcript = ''
    for cid, nm, seed, desc, expect, shrunk_exp, reason_exp in cases:
        e = iso.get(cid)
        n, raw = native(run, nm, seed)
        if nm == 'divzero':
            transcript = raw
        if e is None or n is None:
            problems.append(f'panic recovery {nm}: missing result (isolated={e is not None}, native={n is not None})'); continue
        ok_exp = e['shrunk'] == shrunk_exp and e['reason'] == reason_exp
        if not ok_exp:
            problems.append(f'panic recovery {nm}: expectation not met: shrunk {e["shrunk"]} reason {e["reason"]}')
        agree = e['case'] == n['case'] and e['steps'] == n['steps'] and e['original'] == n['original'] and e['shrunk'] == n['shrunk'] and TEXT.get(e['reason']) == n['reason']
        wcell = '-'
        if nm == 'overflow':
            wagree = (wasm.get('caseIndex') == e['case'] and wasm.get('steps') == e['steps'] and [int(wasm['original'])] == e['original']
                      and [int(wasm['shrunk'])] == e['shrunk'] and wasm.get('reason') == n['reason'])
            agree = agree and wagree
            wcell = f"case {wasm['caseIndex'] + 1}, {wasm['steps']} steps, {wasm['shrunk']}, {wasm['reason']}; bisect {wasm['bisect']} steps, {wasm['runs']} module runs"
        if not agree:
            problems.append(f'panic recovery {nm}: backends disagree: isolated {e} native {n} wasm {wasm}')
        sh = lambda v: '(' + ', '.join(str(x) for x in v) + ')' if len(v) > 1 else str(v[0])
        s.append(f"| {desc} | {expect} | case {e['case'] + 1}, {e['steps']} steps, shrunk {sh(e['shrunk'])}, {TEXT.get(e['reason'], e['reason'])}; {e['gas']:,} gas | case {n['case'] + 1}, {n['steps']} steps, shrunk {sh(n['shrunk'])}, {n['reason']}; {n['runs']} native runs | {wcell} | {'yes' if agree else '**NO**'} |")
    if gas:
        s += ['', f"Gas of ONE isolated evaluation on sonatina (encode the input, `try_call` the harness, decode the result): **{gas['held']:,}** gas when the property holds, **{gas['false']:,}** when it returns false, **{gas['panicked']:,}** when it panics (a reverting call).",
              f"The whole isolated runs above cost {iso[1]['gas']:,} (overflow), {iso[2]['gas']:,} (divzero) and {iso[3]['gas']:,} gas (false-returning, 249 shrink steps), far below the 1,000,000,000 per-test cap."]
    s += ['', 'The native bisect, as printed by `./scripts/find-panic.sh divzero 8102 256` (the first panicking case is deep enough to show the bisection):', '', '```'] + [l for l in transcript.splitlines()] + ['```', '',
          'Rerun: `cd tests-isolated && fe test --show-logs` (sonatina), `./scripts/find-panic.sh overflow 8101 256` (native), `node scripts/panic_wasm.mjs 8101` or the demo page (wasm), or `./scripts/proof.sh`.', '',
          '#### What the new paths do not cover', '',
          '- A property that loops forever or runs out of gas: on sonatina the call fails without a panic code and is reported as "failed without data" (a failure of unknown reason); native and wasm would hang until stopped.',
          '- A panic in the generator or the shrinker themselves (they run in the test, not in the harness).',
          '- On sonatina the harness is a user-written contract (Fe contracts cannot be generic): one `recv` arm per property, one line each; inputs must have a `Decode` impl (all built-in generators except `Seq` do).',
          '- Native recovery is a script around a separate executable, not a call inside the test, and reports only the process\'s stderr text; wasm recovery is shown for one demo property.', '']
    return s

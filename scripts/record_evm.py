#!/usr/bin/env python3
"""Runs evm-recordings (tests that fail on purpose), decodes each revert and writes web/recorded.json.
   --check   do not write; verify web/recorded.json still matches a fresh run.
Prints "Expected failures: N/N recorded"; exits 0 only if every expected failure was recorded."""
import datetime, json, os, re, subprocess, sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
env = dict(os.environ, PATH=os.path.expanduser('~/.fe/bin') + ':' + os.environ['PATH'])
check_only = '--check' in sys.argv

def run(cmd, cwd=None):
    return subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)

EXPECTED_FAILS = ['capped_mint', 'buggy_sort', 'pair_sum', 'bank_sequence']   # rec_<name> tests that must fail with PropertyFailed
EXPECTED_PASS = ['saturating_add']                           # rec_<name> test that must pass and emit its stats

out = run(['fe', 'test', '--show-logs'], cwd='evm-recordings').stdout
lines = out.splitlines()
recs = {}
for i, l in enumerate(lines):
    m = re.match(r'FAIL\s+\[[^\]]*\]\s+rec_(\w+)', l)
    if m and i + 1 < len(lines) and 'got revert data: ' in lines[i + 1]:
        hexdata = lines[i + 1].split('got revert data: ')[1].strip()
        r = run(['node', 'tools/decode-revert/decode.mjs', '--json', hexdata])
        if r.returncode != 0:
            continue
        d = json.loads(r.stdout)
        recs[m.group(1)] = dict(seed=int(d['seed']), case_index=int(d['case']), steps=int(d['steps']), input=[int(x) for x in d['input']], revert_data=hexdata)
    m = re.match(r'PASS\s+\[[^\]]*\]\s+rec_(\w+)', l)
    if m:
        for j in range(i + 1, min(i + 3, len(lines))):
            mm = re.search(r'data: (0x[0-9a-f]*) \}', lines[j])
            if mm:
                h = mm.group(1)[2:]
                w = [int(h[k:k + 64], 16) for k in range(0, len(h), 64)]
                recs[m.group(1)] = dict(cases=w[0], gas=w[1])

# the panic property through check_isolated on sonatina (tests-isolated): the shrunk input and the reason read from the revert data
iso = run(['fe', 'test', '--show-logs'], cwd='tests-isolated').stdout
for line in iso.splitlines():
    m = re.search(r'data: (0x[0-9a-f]*) \}', line)
    if not m:
        continue
    h = m.group(1)[2:]
    w = [int(h[k:k + 64], 16) for k in range(0, len(h), 64)]
    if len(w) > 9 and w[0] == 1 and w[6] == 9 * 32:   # Pi event id 1 (overflow): id, failed, case, steps, reason, original_reason, off_original, off_shrunk, gas
        def arr(off):
            j = off // 32
            return w[j + 1:j + 1 + w[j]]
        recs['panic_overflow'] = dict(seed=8101, case_index=w[2], steps=w[3], input=[str(v) for v in arr(w[7])], original=[str(v) for v in arr(w[6])], reason_code=w[4],   # decimal strings: u64 values exceed 2^53
                                      reason='panicked: arithmetic overflow' if w[4] == 273 else f'reason {w[4]}')

got_fail = [k for k in EXPECTED_FAILS if k in recs and 'revert_data' in recs[k]]
got_pass = [k for k in EXPECTED_PASS if k in recs and 'gas' in recs[k]]
print(f"Expected failures: {len(got_fail)}/{len(EXPECTED_FAILS)} recorded")
print(f"Expected passes:   {len(got_pass)}/{len(EXPECTED_PASS)} recorded")
print(f"Isolated (try_call) recordings: {1 if 'panic_overflow' in recs else 0}/1")
for k in got_fail:
    r = recs[k]
    print(f"  {k}: seed {r['seed']}, case {r['case_index'] + 1} (index {r['case_index']}), {r['steps']} shrink steps, shrunk input {r['input']}")
for k in got_pass:
    print(f"  {k}: held for {recs[k]['cases']} cases, gas {recs[k]['gas']}")
ok = len(got_fail) == len(EXPECTED_FAILS) and len(got_pass) == len(EXPECTED_PASS) and 'panic_overflow' in recs
if not ok:
    print('recording incomplete; fe test output was:\n' + out)
    sys.exit(1)

path = 'web/recorded.json'
if check_only:
    old = json.load(open(path))['props']
    if old != recs:
        print('web/recorded.json is STALE: a fresh run differs from the recorded data')
        print(json.dumps(recs, indent=1)); sys.exit(1)
    print('web/recorded.json matches a fresh run')
    sys.exit(0)

commit = run(['git', 'rev-parse', '--short', 'HEAD']).stdout.strip()
dirty = bool(run(['git', 'status', '--porcelain', '--', 'sparktest', 'props', 'sparktest-evm', 'evm-recordings']).stdout.strip())
doc = dict(
    generated=dict(commit=commit + ('+dirty' if dirty else ''), date=datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%d %H:%M UTC'),
                   fe=run(['fe', '--version']).stdout.strip()),
    command='./scripts/record-evm.sh',
    props=recs)
with open(path, 'w') as f:
    json.dump(doc, f, indent=2)
    f.write('\n')
print(f'wrote {path} (commit {doc["generated"]["commit"]}, {doc["generated"]["date"]})')

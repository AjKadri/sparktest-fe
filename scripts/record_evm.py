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

EXPECTED_FAILS = ['capped_mint', 'buggy_sort', 'pair_sum']   # rec_<name> tests that must fail with PropertyFailed
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

got_fail = [k for k in EXPECTED_FAILS if k in recs and 'revert_data' in recs[k]]
got_pass = [k for k in EXPECTED_PASS if k in recs and 'gas' in recs[k]]
print(f"Expected failures: {len(got_fail)}/{len(EXPECTED_FAILS)} recorded")
print(f"Expected passes:   {len(got_pass)}/{len(EXPECTED_PASS)} recorded")
for k in got_fail:
    r = recs[k]
    print(f"  {k}: seed {r['seed']}, case {r['case_index'] + 1} (index {r['case_index']}), {r['steps']} shrink steps, shrunk input {r['input']}")
for k in got_pass:
    print(f"  {k}: held for {recs[k]['cases']} cases, gas {recs[k]['gas']}")
ok = len(got_fail) == len(EXPECTED_FAILS) and len(got_pass) == len(EXPECTED_PASS)
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

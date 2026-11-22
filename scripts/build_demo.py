#!/usr/bin/env python3
"""Builds the Sparktest web demo data: web/demo_wasm.wasm and web/props.json.
Deterministic: no dates or commit hashes (those live in web/recorded.json, written only by scripts/record-evm.sh).
 - compiles demo-wasm (fe build --backend wasm)
 - extracts each demo property's Fe source from props/src/demo.fe (// @demo <name> ... // @end)
 - records native results (xcheck-native executable)
"""
import hashlib, json, os, re, shutil, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(ROOT)
env = dict(os.environ, PATH=os.path.expanduser('~/.fe/bin') + ':' + os.environ['PATH'])

def run(cmd, cwd=None, check=True):
    r = subprocess.run(cmd, cwd=cwd, env=env, capture_output=True, text=True)
    if check and r.returncode != 0:
        sys.exit(f'command failed: {cmd}\n{r.stdout}\n{r.stderr}')
    return r

# seeds and presentation: ids match the exports run_<id>
SEEDS = {'capped_mint': 11, 'buggy_sort': 22, 'pair_sum': 33, 'saturating_add': 44, 'bank_sequence': 55, 'panic_overflow': 8101}
META = {
    'capped_mint': dict(title='Capped mint', blurb='A token must never exceed its supply cap of 1000. The cap is checked against the supply before minting, so the last mint can overshoot.',
                        bug_keywords=['before minting', 'overshoot'],
                        property='supply never exceeds CAP', labels=['supply', 'amount'], expect='fail'),
    'buggy_sort': dict(title='Buggy sort', blurb='Sorts four numbers with bubble sort, but stops one pass too early: four numbers need three passes and it makes two.',
                       bug_keywords=['pass'],
                       property='the output is sorted', labels=['a[0]', 'a[1]', 'a[2]', 'a[3]'], expect='fail'),
    'pair_sum': dict(title='Pair sum', blurb='A deliberately false claim: the sum of two numbers is always below 10.',
                     property='a + b < 10', labels=['a', 'b'], expect='fail'),
    'bank_sequence': dict(title='Bank sequence', blurb='A tiny bank with three accounts. After an account is drained to zero, its next deposit is credited twice, so the books stop adding up. One command can never show it: it takes a whole sequence.',
                          bug_keywords=['drained', 'twice'], property='after every command: deposited == balances + withdrawn',
                          labels=['kind', 'a', 'b', 'amount'], seq=True, expect='fail'),
    'panic_overflow': dict(title='Overflow panic', blurb='The code multiplies by 1000 in 64-bit arithmetic and overflows for large inputs: the property panics instead of returning false. The page catches the panic, finds the first panicking case by bisecting the case limit, and shrinks by replaying candidates.',
                           bug_keywords=['overflow', 'panic'], property='x * 1000 / 1000 == x (a panic counts as a failure)', labels=['x'], panic=True, expect='fail'),
    'saturating_add': dict(title='Saturating add', blurb='A property that holds: saturating addition never goes below its left operand.',
                           property='saturating_add(x, y) >= x', labels=['x', 'y'], expect='pass'),
}

# 1. wasm
out = tempfile.mkdtemp()
run(['fe', 'build', '--backend', 'wasm', '--emit', 'wasm', '--out-dir', out], cwd='demo-wasm')
os.makedirs('web', exist_ok=True)
shutil.copy(os.path.join(out, 'demo_wasm.wasm'), 'web/demo_wasm.wasm')
manifest = json.load(open(os.path.join(out, 'demo_wasm.manifest.json')))
wasm_bytes = open('web/demo_wasm.wasm', 'rb').read()

# 2. sources
src = open('props/src/demo.fe').read()
sources = {}
for m in re.finditer(r'// @demo (\w+)\n(.*?)// @end', src, re.S):
    sources[m.group(1)] = m.group(2).rstrip() + '\n'
missing = set(SEEDS) - set(sources)
if missing:
    sys.exit(f'no // @demo block for: {missing}')

# 4. native results
exe_dir = tempfile.mkdtemp()
run(['fe', 'build', '--backend', 'native', '--emit', 'executable', '--out-dir', exe_dir], cwd='xcheck-native')
nat = run([os.path.join(exe_dir, 'xcheck_native')]).stdout.splitlines()
native = {}
for i, l in enumerate(nat):
    m = re.match(r'XC demo_(\w+) failed=(\d) case=(\d+) steps=(\d+)', l)
    if m:
        shr = [int(x) for x in nat[i + 2].split('=')[1].split(',')]
        native[m.group(1)] = dict(failed=int(m.group(2)), case_index=int(m.group(3)), steps=int(m.group(4)), shrunk=shr)

for i, l in enumerate(nat):
    m = re.match(r'XW demo_(\w+) failed=(\d) case=(\d+) steps=(\d+)', l)
    if m:
        shr = [int(x) for x in nat[i + 2].split('=')[1].split(',')]
        native[m.group(1)] = dict(failed=int(m.group(2)), case_index=int(m.group(3)), steps=int(m.group(4)), shrunk=shr)

# native result of the panic property: scripts/find-panic.sh drives the native replay driver (bisect + replay shrink)
fp = run(['scripts/find-panic.sh', 'overflow', str(SEEDS['panic_overflow']), '256']).stdout
m = re.search(r'RESULT prop=overflow seed=(\d+) case=(\d+) steps=(\d+) original="([^"]*)" shrunk="([^"]*)" reason="([^"]*)"', fp)
if not m:
    sys.exit('find-panic.sh gave no RESULT line:\n' + fp)
native['panic_overflow'] = dict(failed=1, case_index=int(m.group(2)) - 1, steps=int(m.group(3)), original=m.group(4).split(), shrunk=m.group(5).split(), reason=m.group(6))  # decimal STRINGS: u64 values exceed 2^53 and JSON.parse would round them

props = []
for pid in ['capped_mint', 'buggy_sort', 'pair_sum', 'saturating_add', 'bank_sequence', 'panic_overflow']:
    # the BUG comment: the line starting `// BUG:` plus its `//` continuation lines
    lines = sources[pid].splitlines()
    bug_lines = []
    for k, l in enumerate(lines):
        if l.lstrip().startswith('// BUG:'):
            bug_lines.append(l.lstrip()[len('// BUG:'):].strip())
            for l2 in lines[k + 1:]:
                if l2.lstrip().startswith('//') and not l2.lstrip().startswith('// Property'):
                    bug_lines.append(l2.lstrip()[2:].strip())
                else:
                    break
    props.append(dict(id=pid, seed=SEEDS[pid], cases=256, source=sources[pid], bug=' '.join(bug_lines), native=native[pid], **META[pid]))

doc = dict(
    wasm=dict(file='demo_wasm.wasm', bytes=len(wasm_bytes), sha256=hashlib.sha256(wasm_bytes).hexdigest(),
              imports=[f"{i['module']}.{i['name']}" for i in manifest['imports']],
              exports=[e['name'] for e in manifest['exports']]),
    props=props)
json.dump(doc, open('web/props.json', 'w'), indent=2)
open('web/props.json', 'a').write('\n')
print(f"web/demo_wasm.wasm {len(wasm_bytes)} bytes; web/props.json: {len(props)} props")

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
SEEDS = {'capped_mint': 11, 'buggy_sort': 22, 'pair_sum': 33, 'saturating_add': 44}
META = {
    'capped_mint': dict(title='Capped mint', blurb='A token must never exceed its supply cap of 1000. The cap is checked against the supply before minting, so the last mint can overshoot.',
                        bug_keywords=['before minting', 'overshoot'],
                        property='supply never exceeds CAP', labels=['supply', 'amount'], expect='fail'),
    'buggy_sort': dict(title='Buggy sort', blurb='Sorts four numbers with bubble sort, but stops one pass too early: four numbers need three passes and it makes two.',
                       bug_keywords=['pass'],
                       property='the output is sorted', labels=['a[0]', 'a[1]', 'a[2]', 'a[3]'], expect='fail'),
    'pair_sum': dict(title='Pair sum', blurb='A deliberately false claim: the sum of two numbers is always below 10.',
                     property='a + b < 10', labels=['a', 'b'], expect='fail'),
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

props = []
for pid in ['capped_mint', 'buggy_sort', 'pair_sum', 'saturating_add']:
    # the BUG comment: the line starting `// BUG:` plus its `//` continuation lines
    lines = sources[pid].splitlines()
    bug_lines = []
    for k, l in enumerate(lines):
        if l.startswith('// BUG:'):
            bug_lines.append(l[len('// BUG:'):].strip())
            for l2 in lines[k + 1:]:
                if l2.startswith('//') and not l2.startswith('// Property'):
                    bug_lines.append(l2[2:].strip())
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

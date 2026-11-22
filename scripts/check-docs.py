#!/usr/bin/env python3
"""Checks the documentation against the code.
  - every ```fe block in docs/API.md is compiled and run as a test body; ```fe-item blocks are top-level items; ```fe-native blocks run on the native backend
  - every ```fe-excerpt block in README.md must appear verbatim in examples/quickstart/src/lib.fe (the README quickstart is the tested code)
Exits non-zero on any failure."""
import os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env = dict(os.environ, PATH=os.path.expanduser('~/.fe/bin') + ':' + os.environ['PATH'])
failed = False

def blocks(path):
    text = open(os.path.join(ROOT, path)).read()
    return re.findall(r'```(fe-excerpt|fe-native|fe-item|fe)\n(.*?)```', text, re.S)

# ---- README excerpts must be verbatim code from the quickstart ingot
quick = open(os.path.join(ROOT, 'examples/quickstart/src/lib.fe')).read()
ex = [b for k, b in blocks('README.md') if k == 'fe-excerpt']
for i, b in enumerate(ex, 1):
    if b.strip('\n') not in quick:
        print(f'README fe-excerpt block {i} is not verbatim code from examples/quickstart/src/lib.fe:\n{b}')
        failed = True
print(f'README: {len(ex)} fe-excerpt blocks checked against examples/quickstart/src/lib.fe')

# ---- API.md examples
bl = blocks('docs/API.md')
evm_header = '''use std::evm::{Evm, Address}
use std::abi::DynArray
use core::ptr::MemVec
use sparktest::{Rng, Xorshift, Arbitrary, Shrink, Encode, Checked, Config, Outcome, check, Summary, summarize, Full, full, Index, Seq, MAX, one_word, append_words}
use sparktest::widths::bits_value
use sparktest::composite::count_candidates
use sparktest_evm::{assert_holds, runtime_seed, fixed_seed}
'''
native_header = '''use sparktest_native::{opaque_zero, fixed_seed, ticks}
'''
def indent(b): return ''.join('    ' + l if l.strip() else l for l in b.splitlines(True))
evm_src, nat_src, n_evm, n_nat = [evm_header], [native_header], 0, 0
for kind, b in bl:
    if kind == 'fe-item':
        evm_src.append(b)
    elif kind == 'fe':
        n_evm += 1
        evm_src.append(f'#[test]\nfn doc_example_{n_evm}() uses (evm: mut Evm) {{\n{indent(b)}}}\n')
    elif kind == 'fe-native':
        n_nat += 1
        nat_src.append(f'#[test]\nfn doc_native_{n_nat}() {{\n{indent(b)}}}\n')

def run_ingot(name, target, src, count):
    global failed
    # dependency paths must be relative, so the generated ingots live inside the repo (git-ignored)
    d = os.path.join(ROOT, '.docs-check', name)
    os.makedirs(os.path.join(d, 'src'), exist_ok=True)
    tgt = f'target = "{target}"\n' if target else ''
    deps = 'sparktest = { path = "../../sparktest" }\n' + ('sparktest_evm = { path = "../../sparktest-evm" }\n' if not target else 'sparktest_native = { path = "../../sparktest-native" }\n')
    open(os.path.join(d, 'fe.toml'), 'w').write(f'[ingot]\nname = "{name}"\nversion = "0.1.0"\n{tgt}\n[dependencies]\n{deps}')
    open(os.path.join(d, 'src/lib.fe'), 'w').write('\n'.join(src))
    r = subprocess.run(['fe', 'test'], cwd=d, env=env, capture_output=True, text=True)
    m = re.search(r'test result: (\w+)\. (\d+) passed; (\d+) failed', r.stdout)
    ok = r.returncode == 0 and m and int(m.group(2)) == count and int(m.group(3)) == 0
    print(f'API.md {name}: {count} example(s) ' + ('compiled and passed' if ok else 'FAILED'))
    if not ok:
        failed = True
        print(r.stdout[-3000:] + r.stderr[-2000:])
        print('generated source kept at', d)
    else:
        pass

run_ingot('docs_evm', None, evm_src, n_evm)
run_ingot('docs_native', 'native', nat_src, n_nat)
sys.exit(1 if failed else 0)

"""L9 std hunt section of docs/PROOF.md: HashMap, core::fixed, core::text on sonatina and native, std::evm::random on sonatina. Imported by proof.py."""
import re

AREAS = {'a': 'core::map::HashMap (stateful model)', 'b': 'core::fixed (widened u256 model)', 'c': 'core::text (round trips and length laws)', 'd': 'std::evm::random (sonatina only)'}

def _results(run, cwd):
    out = run(['fe', 'test', '--filter', 'hunt_'], cwd=cwd).stdout
    res = {}
    for line in out.splitlines():
        m = re.match(r'(PASS|FAIL)\s+\[[^\]]*\]\s+(hunt_[a-d]_\S+)', line)
        if m:
            res[m.group(2)] = m.group(1)
    return res

def section(run, problems):
    evm = _results(run, 'tests-evm')
    nat = _results(run, 'tests-native')
    s = ['## Std hunt (L9): properties over std and core, looking for Fe bugs', '',
         'Expected results were written before the runs (docs/EXPECTATIONS.md, section "L9"): every property is expected to pass. 64 cases per property; the reference models are plain integer or array code.',
         'Sources: `props/src/hunt_*.fe` (shared), `tests-evm/src/hunt.fe`, `tests-native/src/hunt.fe`. Rerun: `cd tests-evm && fe test --filter hunt_`, `cd tests-native && fe test --filter hunt_`.', '',
         '| area | property | sonatina | native |', '|---|---|---|---|']
    bad = 0
    for name in sorted(evm):
        area = name[5]
        prop = name[7:].replace('_', ' ')
        e = evm[name]
        n = nat.get(name, 'n/a (no native std::evm)' if area == 'd' else 'MISSING')
        if e != 'PASS' or n not in ('PASS', 'n/a (no native std::evm)'):
            bad += 1
            problems.append(f'std hunt: {name}: sonatina {e}, native {n}')
        s.append(f"| {AREAS[area]} | {prop} | {e} | {n} |")
    s += ['', f"{len(evm)} properties on sonatina, {sum(1 for v in nat.values() if v == 'PASS')} on native; {'no divergence found, so no Fe bug found by this hunt' if bad == 0 else '**' + str(bad) + ' failing: see the problems list**'}.",
          'Sanity checks made while writing (the property failed against a corrupted model, so these can fail): the HashMap model (a wrong stored value; a variant that failed once the capacity exceeded 14, so the table does grow), `mul` (a wrong divisor), the digit count of `decimal`, the `uniform` bound and the shuffle multiset. The other properties were not corrupted one by one.',
          'Limit found while writing it: a `Seq` cannot be a component of a tuple input, because tuple shrinking needs `Decode` and `Seq` has none; growth of the map is therefore a command (`bulk insert`) instead of a separate prefill input.', '']
    return s

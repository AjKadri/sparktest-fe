"""Rewards section of docs/PROOF.md (sonatina only): the same property through try_call vs a direct call. Imported by proof.py."""
import json, os, re

def section(run, problems):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    hist = json.load(open(os.path.join(root, 'proof/history.json')))['rewards']
    out = run(['fe', 'test', '--show-logs'], cwd='tests-rewards').stdout
    res = {}
    for line in out.splitlines():
        m = re.search(r'data: (0x[0-9a-f]*) \}', line)
        if m:
            h = m.group(1)[2:]
            w = [int(h[i:i + 64], 16) for i in range(0, len(h), 64)]
            if len(w) == 13:
                res[w[0]] = dict(failed=w[1], case=w[2], steps=w[3], original=w[4:8], shrunk=w[8:12], gas=w[12])
    direct_ok = bool(re.search(r'PASS\s+\[[^\]]*\]\s+rewards_buggy_direct_call_reverts_the_whole_test', out))
    b, f = res.get(501), res.get(502)
    if not direct_ok:
        problems.append('rewards: the direct-call test did not revert the whole test with Panic(0x11)')
    expected = 18446744073709552
    if b is None or f is None:
        problems.append('rewards: missing results'); return []
    if b['failed'] != 1 or b['shrunk'][0] != expected:
        problems.append(f"rewards buggy: expected stake {expected}, found {b}")
    if f['failed'] != 0 or f['case'] != 128:
        problems.append(f'rewards fixed did not pass 128 cases: {f}')
    seed = 7001
    s = [f"## A contract that really panics: `examples/rewards` ({hist['date']}, commit {hist['commit']})", '',
         'A small staking-rewards contract written for this proof (not a Fe example): `claim` returns `stake * 1000 / 10000` and computes `stake * 1000` in `u64`.',
         'The planted overflow (Panic 0x11) starts at stake 18446744073709552 (`18446744073709552 * 1000 >= 2^64`). Property: "stake, then claim, succeeds and returns stake / 10 for every stake <= 2^63".',
         'The same property is written twice and run on sonatina; the difference is the call API.', '',
         '| how the property calls the contract | what happens when the contract panics | shrunk stake | seed | case | shrink steps | pre-registered minimum | as expected | gas | rerun |',
         '|---|---|---|---|---|---|---|---|---|---|',
         f"| `evm.call` (direct) | the callee's Panic(0x11) bubbles up and the **whole test reverts**: no Outcome, no shrinking, no seed. Asserted by `#[test(should_revert, panic = 0x11)]` `rewards_buggy_direct_call_reverts_the_whole_test`; the same effect for a pure overflow is `probe_overflow_in_property_reverts_whole_run` in `tests-evm/src/lib.fe` | none | none | none | none | - | {'yes (reverts with Panic 0x11)' if direct_ok else '**NO**'} | - | `cd tests-rewards && fe test --filter direct` |",
         f"| `evm.try_call` | the failed call is a value; the property returns false; Sparktest reports and shrinks it | {b['shrunk'][0]} | {seed} | {b['case'] + 1} | {b['steps']} | {expected} | {'yes: exact' if b['shrunk'][0] == expected else '**NO**'} | {b['gas']:,} | `cd tests-rewards && fe test --filter buggy_through --show-logs` |",
         f"| `evm.try_call`, RewardsFixed (divides first) | no panic | passes {f['case']} cases | {seed + 1} | - | - | passes | {'yes' if f['failed'] == 0 else '**NO**'} | {f['gas']:,} | `cd tests-rewards && fe test --filter fixed --show-logs` |", '']
    return s

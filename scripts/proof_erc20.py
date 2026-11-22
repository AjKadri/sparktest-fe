"""ERC20 section of docs/PROOF.md (sonatina only). Imported by scripts/proof.py."""
import re

PROPS = {
    1: ('transfer(amount <= balance) succeeds and moves exactly amount', '(sender, receiver, amount)'),
    2: ('transfer(amount > balance) does not succeed and changes nothing', '(sender, receiver, amount over balance)'),
    3: ('transfers never change totalSupply', '(sender, receiver, amount)'),
    4: ('approve, then transferFrom(amount <= allowance) lowers the allowance by exactly amount', '(owner, spender, to, packed allowance/amount)'),
    5: ('transferFrom(amount > allowance) does not succeed', '(owner, spender, to, packed allowance/amount)'),
    6: ('balances of the 4 actors always sum to totalSupply', '(sender, receiver, amount)'),
}
BUGGY_FAIL = {1, 6}
CMD = 'cd tests-erc20 && fe test --show-logs   (or ./scripts/proof.sh)'

def section(run, problems):
    out = run(['fe', 'test', '--show-logs'], cwd='tests-erc20').stdout
    res = {}
    for line in out.splitlines():
        m = re.search(r'data: (0x[0-9a-f]*) \}', line)
        if m:
            h = m.group(1)[2:]
            w = [int(h[i:i + 64], 16) for i in range(0, len(h), 64)]
            if len(w) == 16:   # 3 original + 5 shrunk words and the counters (4 + 4 words before L7c)
                res[w[0]] = dict(failed=w[1], case=w[2], steps=w[3], original=w[4:7], shrunk=w[7:12], gas=w[12], attempted=w[13], accepted=w[14], vacuous=w[15])
    s = ['## ERC20 through contract calls (sonatina only)', '',
         'Contract: the ERC20 test fixture from the Fe compiler repo (`crates/fe/tests/fixtures/fe_test/erc20.fe` at e6e6342), vendored unchanged in `examples/erc20` (Apache-2.0).',
         'It is a compiler test fixture, not a documented or audited token example. Observations about it (not bugs): `transfer` and `transferFrom` return `false` instead of reverting',
         'on insufficient balance/allowance, so "reverts" is checked as "does not succeed"; and `mint` is open to anyone.',
         'Four actor proxy contracts make the calls, so the token sees four different senders; each case deploys a fresh token (supply 1000 to actor 0, which sends 250 to each other actor).',
         '64 cases per property. Views are read with the plain typed `evm.call`; state-changing calls go through the actors using the non-reverting `try_*` helpers',
         '(`CallOutcome::decode` also returns view data from `try_call`).', '',
         '**Other ERC20 or token sources in Fe v26.7.0 (searched 2026-11-22):** the documentation sources (`docs/`, `docs/language/*.md`, `docs/architecture/*.md`, `examples/`) contain no ERC20 or token',
         'example contract. The only match is a four-field storage-layout illustration (`pub contract Token { mut owner: Address, ... }` in `docs/language/contract-storage.md`), which has no behaviour to test, so',
         'nothing was vendored as `examples/erc20-docs/`. The other ERC20-like files in the clone are compiler test fixtures (for example `crates/codegen/tests/fixtures/erc20.fe`,',
         '`crates/fe/tests/fixtures/build_foundry/erc20.fe`, `crates/fe/tests/fixtures/fe_test/coin.fe`, `crates/fe/tests/evm_compiler_bench/erc20_minimal.fe`) and the std client helper',
         '`ingots/std/src/evm/erc20.fe` (a library for calling tokens, not a token). Search: `grep -rniE "erc ?20|token" docs README.md CLI.md` and `grep -rliE "erc20|contract .*(Token|Coin)" --include=*.fe`.', '']
    import json, os
    hist = json.load(open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'proof/history.json')))
    h0, h1 = hist['erc20_original'], hist['erc20_index_amendment']
    runs = (
        (f"Unchanged contract, actors picked with a raw `u8 % 4` (original run {h0['date']}, commit {h0['commit']}; live re-run since L7c)", 100, False, 'u8'),
        (f"Planted bug, actors picked with a raw `u8 % 4` (original run {h0['date']}, commit {h0['commit']}; live re-run since L7c: the original results are frozen in the table below)", 200, True, 'u8'),
        (f"AMENDMENT {h1['date']} (commit {h1['commit']}; live re-run since L7c): unchanged contract, actors picked with `Index<4>`", 300, False, 'Index<4>'),
        (f"AMENDMENT {h1['date']} (commit {h1['commit']}; live re-run since L7c): planted bug, actors picked with `Index<4>`", 400, True, 'Index<4>'),
    )
    for title, base, buggy, mode in runs:
        s += [f'### {title}', '', '| # | property | input | expected | found | as expected | cases | case | shrink steps | calls accepted / attempted | vacuous? | gas | backend | rerun |',
              '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|']
        for pid, (text, inp) in PROPS.items():
            r = res.get(base + pid)
            if r is None:
                problems.append(f'erc20 property {base + pid}: no result')
                continue
            if mode == 'Index<4>':
                inp = inp.replace('(sender, receiver', '(Index<4> sender, Index<4> receiver').replace('(owner, spender, to,', '(Index<4> owner, spender, to,')
            if buggy and pid in BUGGY_FAIL:
                expected = 'fails; minimum (0, 0, 1)' + (' (honest prediction: (a, a, 1))' if mode == 'Index<4>' else '')
                if r['failed'] != 1:
                    problems.append(f'buggy erc20 P{pid} did not fail'); ok = 'NO'; found = f"passed {r['case']} cases"
                else:
                    w = r['shrunk']
                    found = f'(sender={w[0]}, receiver={w[1]}, amount={w[2]})'
                    same = (w[0] % 4 == w[1] % 4) and w[2] == 1
                    exact = w[:3] == [0, 0, 1]
                    if exact:
                        ok = 'yes: exactly (0, 0, 1)'
                    elif same and mode == 'Index<4>':
                        ok = 'partly: a self-transfer of amount 1; the indices stopped at a local minimum (changing one index alone ends the failure), as predicted'
                    elif same:
                        ok = 'partly: a self-transfer of amount 1, but raw indices are not minimal (both map to the same actor)'
                    else:
                        ok = 'NO'
                        problems.append(f'buggy erc20 P{pid}: unexpected shrunk value {w}')
            else:
                expected = 'passes'
                found = f"passed {r['case']} cases" if r['failed'] == 0 else f"FAILED, shrunk {r['shrunk']}"
                ok = 'yes' if r['failed'] == 0 and r['case'] == 64 and r['vacuous'] == 0 else 'NO'
                if ok == 'NO':
                    problems.append(f"erc20 base {base} P{pid} expected to pass but: {r}")
            case = '-' if r['failed'] == 0 else str(r['case'] + 1)
            steps = '-' if r['failed'] == 0 else str(r['steps'])
            s.append(f"| P{pid} | {text} | {inp} | {expected} | {found} | {ok} | 64 | {case} | {steps} | {r['accepted']} / {r['attempted']} | {'no' if r['vacuous'] == 0 else 'VACUOUS (reason ' + str(r['vacuous']) + ')'} | {r['gas']:,} | sonatina | `{CMD}` |")
        s.append('')
    f0 = hist['erc20_before_l7c']
    s += ['### Frozen: the same planted-bug runs before joint shrinking (commit ' + f0['commit'] + ', frozen from docs/PROOF.md at that commit)', '',
          'The tables above are live re-runs. These are the values they showed before L7c (docs/EXPECTATIONS.md, section "L7c", lists the prediction and the result for each).', '',
          '| actors | property | found (sender, receiver, amount) | case | shrink steps | gas |', '|---|---|---|---|---|---|']
    for lab, key in (('raw `u8 % 4`', 'raw_u8'), ('`Index<4>`', 'index4')):
        for pk in ('P1', 'P6'):
            v = f0[key][pk]
            s.append(f"| {lab} | {pk} | {tuple(v['found'])} | {v['case']} | {v['steps']} | {v['gas']:,} |")
    s.append('')
    d = res.get(701)
    if d is None:
        problems.append('vacuity demo: no result')
    else:
        if not (d['failed'] == 0 and d['attempted'] == 64 and d['accepted'] == 0 and d['vacuous'] == 2):
            problems.append(f'vacuity demo did not behave as expected: {d}')
        s += ['### Vacuity guard demo (sonatina)', '',
              'A conditional property, "if the transfer succeeds it moves exactly the amount", written so that every amount exceeds the balance. The transfer never succeeds, so the property can never fail.', '',
              '| run | result | calls accepted / attempted | verdict |', '|---|---|---|---|',
              f"| unguarded `check` | **Pass** ({d['case']} cases) | not looked at | passes silently |",
              f"| with the guard (`vacuity` / `guard`) | passed, but vacuously | {d['accepted']} / {d['attempted']} | **VACUOUS, reason 2: no call succeeded** |", '',
              'Reasons: 1 = no call attempted, 2 = calls attempted but none succeeded where success is expected, 3 + k = no command of kind k executed across the whole run. Rerun: `cd tests-erc20 && fe test --filter vacuous --show-logs`.', '']
    return s

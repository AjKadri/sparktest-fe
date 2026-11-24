"""CoolCoin (the Fe Guide ERC-20) section of docs/PROOF.md: the unchanged contract and the 10-mutant mutation test (sonatina only). Imported by proof.py."""
import re

PROP_NAMES = {1: 'P1 transfer moves exactly amount', 2: 'P2 transfer over balance changes nothing', 3: 'P3 transfer keeps totalSupply',
              4: 'P4 transferFrom lowers the allowance exactly', 5: 'P5 transferFrom over allowance fails', 6: 'P6 balances sum to totalSupply', 7: 'stateful model check'}
SHORT = {1: 'P1', 2: 'P2', 3: 'P3', 4: 'P4', 5: 'P5', 6: 'P6', 7: 'stateful'}

# (mutant, single change, expected caught?, expected catching properties, explanation shown for a miss), mirroring docs/EXPECTATIONS.md (L7a), written before the runs
MUTANTS = [
 ('M01', '`transfer` credits the receiver `amount + 1`', True, ['P1', 'P6', 'stateful'], ''),
 ('M02', 'the `from_balance >= amount` assert in `transfer` is removed', False, [], 'm02'),
 ('M03', '`transferFrom` swaps `from` and `to` in the inner transfer', True, ['P4', 'stateful'], ''),
 ('M04', '`spend_allowance` no longer lowers the allowance', True, ['P4', 'stateful'], ''),
 ('M05', '`transfer` credits the receiver first, then debits from the stale sender balance (a self-transfer destroys `amount`)', True, ['P1', 'P6', 'stateful'], ''),
 ('M06', 'balance check `>=` becomes `>` (the full balance cannot be sent)', True, ['P1', 'stateful'], ''),
 ('M07', 'allowance check `>=` becomes `>` (the full allowance cannot be spent)', True, ['P4', 'stateful'], ''),
 ('M08', 'the Transfer event is no longer emitted in `transfer`', False, [], 'm08'),
 ('M09', '`mint` no longer increases `total_supply`', True, ['stateful'], 'only'),
 ('M10', '`mint` no longer requires the MINTER role (L7a: missed; L7c: expected caught by the adversarial Mint command)', True, ['stateful'], 'only'),
]

def blocks(out):
    """[(test name, status, [log data words...])] from `fe test --show-logs` output"""
    res, cur = [], None
    for line in out.splitlines():
        m = re.match(r'(PASS|FAIL)\s+\[[^\]]*\]\s+(\S+)', line)
        if m:
            cur = [m.group(2), m.group(1), []]
            res.append(cur)
            continue
        m = re.search(r'data: (0x[0-9a-f]*) \}', line)
        if m and cur is not None:
            h = m.group(1)[2:]
            cur[2].append([int(h[i:i + 64], 16) for i in range(0, len(h), 64)])
    return res

def parse(out):
    """prefix ('guide', 'm01', ..) -> {1..7: result}"""
    res = {}
    for name, status, logs in blocks(out):
        m = re.match(r'(guide|[mh]\d\d)_p(\d)_', name)
        if m and status == 'PASS':
            for w in logs:
                if len(w) == 16:
                    res.setdefault(m.group(1), {})[int(m.group(2))] = dict(failed=w[1], case=w[2], steps=w[3], shrunk=w[7:12], original=w[4:7], gas=w[12], attempted=w[13], accepted=w[14], vacuous=w[15])
            continue
        m = re.match(r'stateful_(guide|[mh]\d\d)_stateful$', name)
        if m and status == 'PASS':
            for w in logs:
                # the token's own events (one word) are in the same list; the stateful result has 15 head words (14 before L7c's kind 4)
                if len(w) > 14 and w[4] in (14 * 32, 15 * 32, 16 * 32):
                    head = w[4] // 32
                    def arr(off):
                        i = off // 32
                        return w[i + 1:i + 1 + w[i]]
                    res.setdefault(m.group(1), {})[7] = dict(failed=w[1], case=w[2], steps=w[3], original=arr(w[4]), shrunk=arr(w[5]), gas=w[6],
                                                               attempted=w[7], accepted=w[8], vacuous=w[9], kinds=w[10:15] if head >= 15 else w[10:head], early=w[15] if head >= 16 else 0)
    return res

def counterexample(pid, r):
    w = r['shrunk']
    if pid in (1, 6):
        return f"(sender {w[0]}, receiver {w[1]}, amount {w[2]})"
    if pid == 2:
        return f"(sender {w[0]}, receiver {w[1]}, amount input {w[2]}: amount = balance + 1 + input = {4 + w[2]})"
    if pid == 3:
        return f"(sender {w[0]}, receiver {w[1]}, amount {w[2]})"
    if pid in (4, 5):
        if pid == 4:
            return f"(owner {w[0]}, spender {w[1]}, to {w[2]}, allowance {w[3]}, amount {w[4]})"
        return f"(owner {w[0]}, spender {w[1]}, to {w[2]}, packed {w[3]}: allowance {w[3] % 65536}, amount input {w[3] // 65536})"
    n = w[0]
    cmds = []
    for i in range(n):
        k, a, b, c, amt = w[1 + 5 * i:6 + 5 * i]
        cmds.append([f'Transfer(actor {a} -> actor {b}, {amt})', f'Approve(owner {a}, spender {b}, {amt})', f'TransferFrom(spender {a}, owner {b}, to {c}, {amt})', f'Mint(to {a}, {amt}, by the owner)', f'Mint(actor {a} -> to {b}, {amt}, NOT the owner)'][k])
    return f'{n} command(s): ' + ' ; '.join(cmds)

def section(run, problems):
    out = run(['fe', 'test', '--show-logs'], cwd='tests-coolcoin').stdout
    if 'test result: ok' not in out:
        problems.append('tests-coolcoin did not pass:\n' + out[-1500:])
    res = parse(out)
    bl = {n: (st, logs) for n, st, logs in blocks(out)}
    s = ['## The Fe Guide ERC-20 (CoolCoin) and a mutation test (sonatina only)', '',
         'Contract: the "Complete ERC20" example from the Fe Guide, https://fe-lang.org/examples/erc20/ (fetched 2026-11-22), vendored unchanged in `examples/coolcoin`. It compiled and passed its own 3 tests unchanged on Fe 26.7.0.',
         'The page states no licence; its repository links point to github.com/argotorg/fe (Apache-2.0); see the header of `examples/coolcoin/src/lib.fe` for the exact status. Differences from the compiler-repo ERC20 test fixture:',
         '`transfer`/`transferFrom` revert on a shortfall (the fixture returns `false`), and `mint` needs the MINTER role.',
         'Setup per case: the test contract is the owner (it holds MINTER) with supply 13; it sends 3 to each of 4 actor contracts and keeps 1 (the conservation checks include the owner). 64 cases per property; stateful runs use 8-command sequences',
         'over Transfer, Approve, TransferFrom, Mint by the owner and Mint by an actor that is not the owner (the token must refuse it) with `Index<4>` actors, an `Index<5>` command kind and an `Index<9>` amount. Every row shows calls accepted / attempted: the vacuity guard fails a passing run that never succeeded or never ran a command kind.', '',
         '### Unchanged CoolCoin', '', '| property | result | calls accepted / attempted | vacuous? | gas | rerun |', '|---|---|---|---|---|---|']
    for _name, _r in res.items():
        if _r.get(7, {}).get('early'):
            problems.append(f'{_name}: shrinking of the stateful run was stopped early (gas)')
    g = res.get('guide', {})
    for pid in range(1, 8):
        r = g.get(pid)
        if r is None:
            problems.append(f'CoolCoin: no result for property {pid}'); continue
        ok = r['failed'] == 0 and r['vacuous'] == 0
        if not ok:
            problems.append(f'CoolCoin (unchanged) {SHORT[pid]}: failed or vacuous: {r}')
        s.append(f"| {PROP_NAMES[pid]} | {'passed ' + str(r['case']) + ' cases' if r['failed'] == 0 else 'FAILED, shrunk ' + counterexample(pid, r)} | {r['accepted']} / {r['attempted']} | {'no' if r['vacuous'] == 0 else 'VACUOUS (reason ' + str(r['vacuous']) + ')'} | {r['gas']:,} | `cd tests-coolcoin && fe test --filter guide_ --show-logs` |")
    if 7 in g and 'kinds' in g[7]:
        s += ['', f"Stateful run, commands executed (Transfer, Approve, TransferFrom, owner Mint, adversarial Mint): {', '.join(str(x) for x in g[7]['kinds'])}.", '']

    s += ['### Mutation test: 10 single-change mutants (`examples/coolcoin-mutants`, generated by `scripts/gen_mutants.py`)', '',
          'Expected results were committed before the results commit (docs/EXPECTATIONS.md, section "L7a"). A mutant is CAUGHT when any of P1 to P6 or the stateful check fails. "Shrunk counterexample" is the first failing property in the order P1 to P6, then stateful.', '',
          '| mutant | single change | expected | by | actual | caught by | shrunk counterexample | as expected | calls accepted / attempted (first failing run) |', '|---|---|---|---|---|---|---|---|---|']
    caught_n = missed_n = matched = 0
    notes = []
    for mid, change, exp_caught, exp_by, why in MUTANTS:
        r = res.get(mid.lower(), {})
        failing = [p for p in range(1, 8) if p in r and r[p]['failed'] == 1]
        by = [SHORT[p] for p in failing]
        vac = [SHORT[p] for p in range(1, 8) if p in r and r[p]['vacuous'] not in (0,) and r[p]['failed'] == 0]
        if len(r) != 7:
            problems.append(f'{mid}: results for {sorted(r)} only'); continue
        caught = bool(failing)
        caught_n += caught
        missed_n += (not caught)
        if exp_caught:
            if caught and why == 'only' and any(b not in exp_by for b in by):
                extra = ', '.join(b for b in by if b not in exp_by)
                ok = f'partly: caught, but NOT only by {", ".join(exp_by)}: also by {extra}'
            elif caught and all(e in by for e in exp_by):
                ok = 'yes' + (f' (also caught by {", ".join(b for b in by if b not in exp_by)})' if any(b not in exp_by for b in by) else '')
            elif caught:
                ok = f'partly: caught, but not by {", ".join(e for e in exp_by if e not in by)}'
            else:
                ok = '**NO: missed**'
        else:
            ok = 'yes (missed, as predicted)' if not caught else f'**NO: caught by {", ".join(by)}**'
        matched += ok.startswith('yes')
        if ok.startswith('**NO'):
            problems.append(f'{mid}: expectation not met: expected caught={exp_caught} by {exp_by}; actual by {by}')
        first = failing[0] if failing else None
        ce = counterexample(first, r[first]) if first else '-'
        cnt = f"{r[first]['accepted']} / {r[first]['attempted']}" if first else '-'
        s.append(f"| {mid} | {change} | {'caught' if exp_caught else 'missed'} | {', '.join(exp_by) if exp_by else '-'} | {'**caught**' if caught else '**missed**'} | {', '.join(by) if by else '-'} | {ce} | {ok} | {cnt} |")
        if vac:
            notes.append(f'{mid}: passing properties flagged vacuous: {", ".join(vac)}')

    def logs_of(name):
        return len(bl.get(name, (None, []))[1]) if name in bl else None
    probe = lambda n: bl.get(n, ('MISSING', []))[0] == 'PASS'
    partly = [m[0] for m in MUTANTS if any(('partly' in line) and line.startswith(f'| {m[0]} ') for line in s)]
    s += ['', f'Caught {caught_n} of 10, missed {missed_n} of 10; {matched} of 10 matched the pre-registered expectation' + (f' exactly and {len(partly)} partly ({", ".join(partly)})' if partly else '') + '.', '', '#### Why the misses are misses (each backed by a probe test in `tests-coolcoin/src/probes.fe`)', '']
    l1, l2 = logs_of('probe_log_original_one_transfer'), logs_of('probe_log_m08_one_transfer')
    for mid, change, exp_caught, exp_by, why in MUTANTS:
        r = res.get(mid.lower(), {})
        if any(p in r and r[p]['failed'] == 1 for p in range(1, 8)):
            continue
        if why == 'm02':
            ok = probe('probe_m02_original_over_balance_reverts_with_an_error_string') and probe('probe_m02_mutant_over_balance_reverts_with_panic_0x11')
            s.append(f"- **M02 (equivalent mutant).** Fe's checked subtraction still reverts when the balance is too small, so removing the explicit assert changes only the revert reason: the original reverts with `Error(string)` (selector 0x08c379a0), the mutant with `Panic(0x11)`. Properties see only whether a call succeeded, which is identical. Probes: {'both pass' if ok else '**FAILED**'}.")
            if not ok: problems.append('M02 probes failed')
        elif why == 'm08':
            s.append(f"- **M08 (invisible to state properties).** The mutant keeps balances, allowances and supply identical and only drops a log. In the probe, one `transfer` emits {l1} log(s) on the original and {l2} on the mutant (`--show-logs`). The properties read balances, allowances and supply, so they cannot see a missing event. Catching it needs an event assertion.")
            if not (l1 is not None and l2 is not None and l2 == l1 - 1): problems.append(f'M08 log probe: original {l1}, mutant {l2}')
        elif why == 'm10':
            ok = probe('probe_nonowner_mint_is_rejected_by_the_original') and probe('probe_nonowner_mint_is_accepted_by_mutant_m10')
            s.append(f"- **M10 (needs a non-owner caller).** In every property and stateful run only the owner calls `mint`, and the owner holds MINTER, so the missing access check never matters. A non-owner actor's `mint` is rejected by the original and accepted by the mutant (two probes: {'both pass' if ok else '**FAILED**'}). Adding an adversarial caller to the Mint command would catch it.")
            if not ok: problems.append('M10 probes failed')
    m9 = res.get('m09', {})
    if any(p in m9 and m9[p]['failed'] == 1 for p in (1, 2, 3, 4, 5, 6)):
        s += ['#### An expectation that was only partly right', '',
              '- **M09** was pre-registered as caught only by the stateful run (P1 to P6 never call `mint`). It is also caught by P2 and P6 because I overlooked that the constructor mints the initial supply through the same `mint` function, so `total_supply` is already wrong (0 instead of 13) at deployment. The stateful run is still the only one that catches it through the `Mint` command.', '']
    lost = [m for m in ('m03', 'm04') if res.get(m, {}).get(7, {}).get('failed') == 0]
    if lost:
        s += ['#### A change in power that L7c caused', '',
              f"- **{' and '.join(m.upper() for m in lost)}** were caught by P4 and by the stateful check (L7a). Since L7c the stateful check no longer catches them in 64 cases: adding the adversarial Mint made the command kind an `Index<5>`, so a sequence needs a TransferFrom with a prior matching Approve less often. P4 still catches both, so the score is unchanged, but the stateful run alone has become weaker per case. The planted ERC20 bug of the same kind needed 128 cases instead of 64 (found at case 21 before, case 102 now).", '']
    if notes:
        s += [''] + [f'- {n}' for n in notes]
    s += heldout_rows(res, bl, problems)
    s += ['', 'Not exercised by any command, so no claim is made about them: `burn`, `burnFrom`, `increaseAllowance`, `decreaseAllowance`, `name`, `symbol`, `decimals`. The mutants are a hand-picked sample of single changes, not a measured mutation score. Rerun: `./scripts/proof.sh`.', '']
    return s


# ---- held-out mutants (L9): five NEW single changes written after the ten above and after the test templates were frozen
HELDOUT = [
 ('H01', '`spend_allowance` RAISES the allowance (`current + amount`) instead of lowering it', True, ['P4'], ''),
 ('H02', '`transferFrom` debits the spender (`ctx.caller()`) instead of the owner', True, ['P4'], ''),
 ('H03', '`mint` credits the receiver `amount + 1` (off by one)', True, ['P6', 'stateful'], ''),
 ('H04', '`approve` stores the allowance under `(owner, owner)` instead of `(owner, spender)`', True, ['P4', 'P5'], ''),
 ('H05', '`burn` no longer lowers `total_supply`', False, [], 'h05'),
]

def heldout_rows(res, bl, problems):
    import json, os
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    h = json.load(open(os.path.join(root, 'proof/history.json')))['heldout']
    s = ['', f"### Held-out mutants: 5 NEW single changes (`examples/coolcoin-heldout`, generated by `scripts/gen_heldout_mutants.py`; run {h['date']}, expectations committed in {h['commit']} before any of them ran)", '',
         'Written after the test templates and the ten mutants above were frozen, so they measure what the suite catches on changes it was not tuned for. Reported separately from M01 to M10; the score above is NOT mixed with this one.', '',
         '| mutant | single change | expected | by | actual | caught by | shrunk counterexample | as expected | calls accepted / attempted (first failing run) |', '|---|---|---|---|---|---|---|---|---|']
    caught_n = matched = 0
    misses = []
    for mid, change, exp_caught, exp_by, why in HELDOUT:
        r = res.get(mid.lower(), {})
        if len(r) != 7:
            problems.append(f'{mid}: results for {sorted(r)} only'); continue
        failing = [p for p in range(1, 8) if p in r and r[p]['failed'] == 1]
        by = [SHORT[p] for p in failing]
        caught = bool(failing)
        caught_n += caught
        if exp_caught:
            if caught and all(e in by for e in exp_by):
                ok = 'yes' + (f' (also caught by {", ".join(b for b in by if b not in exp_by)})' if any(b not in exp_by for b in by) else '')
            elif caught:
                ok = f'partly: caught, but not by {", ".join(e for e in exp_by if e not in by)}'
            else:
                ok = '**NO: missed**'
        else:
            ok = 'yes (missed, as predicted)' if not caught else f'**NO: caught by {", ".join(by)}**'
        matched += ok.startswith('yes')
        first = failing[0] if failing else None
        ce = counterexample(first, r[first]) if first else '-'
        cnt = f"{r[first]['accepted']} / {r[first]['attempted']}" if first else '-'
        s.append(f"| {mid} | {change} | {'caught' if exp_caught else 'missed'} | {', '.join(exp_by) if exp_by else '-'} | {'**caught**' if caught else '**missed**'} | {', '.join(by) if by else '-'} | {ce} | {ok} | {cnt} |")
        if not caught:
            misses.append(mid)
    s += ['', f'Held-out score: caught {caught_n} of 5, missed {5 - caught_n} of 5; {matched} of 5 matched the pre-registered expectation.', '']
    probe = lambda n: bl.get(n, ('MISSING', []))[0] == 'PASS'
    for mid in misses:
        if mid == 'H05':
            ok = probe('probe_burn_lowers_total_supply_on_the_original') and probe('probe_burn_leaves_total_supply_on_mutant_h05')
            s.append(f"- **H05 (no command burns).** Neither P1 to P6 nor the stateful command set ever calls `burn`, so a `burn` that leaves `total_supply` alone is invisible. It is a real difference, not an equivalent mutant: after a burn of 3 the original's `total_supply` drops by 3 and the mutant's does not (two probes in `tests-coolcoin/src/probes_heldout.fe`: {'both pass' if ok else '**FAILED**'}). Catching it needs a Burn command in the stateful set.")
            if not ok: problems.append('H05 probes failed')
        else:
            problems.append(f'{mid}: missed and no explanation written')
    return s

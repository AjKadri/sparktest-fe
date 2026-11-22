"""ERC20 stateful rows for the Stateful section of docs/PROOF.md (sonatina only). Imported by proof_stateful."""
import proof_stateful

def cmds(w):
    n = w[0]
    out = []
    for i in range(n):
        k, a, b, c, amt = w[1 + 5 * i:6 + 5 * i]
        if k == 0: out.append(f'Transfer(actor {a} -> actor {b}, {amt})')
        elif k == 1: out.append(f'Approve(owner {a}, spender {b}, {amt})')
        elif k == 2: out.append(f'TransferFrom(spender {a}, owner {b}, to {c}, {amt})')
        else: out.append(f'Mint(to {a}, {amt})')
    return out

def rows(run, problems):
    out = run(['fe', 'test', '--filter', 'stateful_', '--show-logs'], cwd='tests-erc20').stdout
    res = proof_stateful.parse_evm(out)
    s = ['### Stateful ERC20 (sonatina only): the ERC20 test fixture from the Fe compiler repo vs a pure reference model', '',
         'Each case deploys a fresh token (supply 16: every actor of four holds 4) plus four actor proxies, replays up to 8 commands through contract calls, and after every call compares the',
         'contract with a reference model (all four balances, totalSupply, the touched allowance) and checks that the balances sum to totalSupply. A command is `((kind, a, b), (c, amount))`',
         'with `Index<4>` actors and an `Index<9>` amount (0..8): Transfer(a to b), Approve(owner a, spender b), TransferFrom(spender a, owner b, to c), Mint(to a). 64 cases per run.',
         'History: the first encoding packed the amount and the third actor into one `u32` (`% 9`, `/ 16 % 4`). It found the same 2-call shape (amounts 4 and 1 after the modulo) but left the raw packed numbers',
         'unshrunk (for example 407994619, which is 4 mod 9), so the amount became an `Index<9>` and the third actor an `Index<4>`, which shrink to real values.', '',
         '| scenario | expected | found (shrunk) sequence | length | as expected | case | shrink steps | gas | backend | rerun |', '|---|---|---|---|---|---|---|---|---|---|']
    for rid, title, expect in ((601, 'unchanged fixture', 'passes 64 cases'),
                               (602, 'examples/erc20-stateful-bug (PLANTED: after a transfer takes a holder to 0, the next transfer into it credits twice)',
                                'length 2: Transfer(a -> b, 4), Transfer(c -> a, 1), b != a, c != a')):
        r = res.get(rid)
        if r is None:
            problems.append(f'erc20 stateful {rid}: no result'); continue
        if rid == 601:
            ok = 'yes' if r['failed'] == 0 and r['case'] == 64 else 'NO'
            if ok == 'NO': problems.append(f'unchanged ERC20 failed the stateful model check: {r}')
            s.append(f"| {title} | {expect} | passed {r['case']} cases | - | {ok} | - | - | {r['gas']:,} | sonatina | `cd tests-erc20 && fe test --filter stateful_orig --show-logs` |")
        else:
            if r['failed'] != 1:
                problems.append(f'planted ERC20 stateful bug not found: {r}'); continue
            w = r['shrunk']
            c = [w[1 + 5 * i:6 + 5 * i] for i in range(w[0])]
            shape = (w[0] == 2 and c[0][0] == 0 and c[1][0] == 0 and c[0][4] == 4 and c[1][4] == 1
                     and c[1][2] == c[0][1] and c[0][2] != c[0][1] and c[1][1] != c[1][2])
            ok = 'yes: length 2, amounts exactly 4 and 1' + (', all indices minimal (a = 0)' if c[0][1] == 0 else f', a = {c[0][1]} (local minimum)') if shape else 'NO'
            if not shape:
                problems.append(f'planted ERC20 stateful bug: pre-registered shape not met: {w}')
            s.append(f"| {title} | {expect} | {' ; '.join(cmds(w))} | {w[0]} | {ok} | {r['case'] + 1} | {r['steps']} | {r['gas']:,} | sonatina | `cd tests-erc20 && fe test --filter stateful_bug --show-logs` |")
    s.append('')
    return s

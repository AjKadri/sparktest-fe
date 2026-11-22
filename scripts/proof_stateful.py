"""Stateful section of docs/PROOF.md. Imported by scripts/proof.py.
Pure sequence scenarios run on sonatina (events) and native (println) and must agree on the COMPLETE words; the ERC20
stateful suite (sonatina only) is added by proof_erc20_stateful (optional)."""
import json, os, re, subprocess, sys, tempfile

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KINDS = ['deposit', 'withdraw', 'transfer']

def decode_words(w):
    """[len, cmd words...] -> list of commands (lists of ints)"""
    return w[0], w[1:]

def bank_cmds(w):
    n, rest = decode_words(w)
    out = []
    for i in range(n):
        k, a, b, amt = rest[4 * i:4 * i + 4]
        if k == 0: out.append(f'deposit(acct {a}, {amt})')
        elif k == 1: out.append(f'withdraw(acct {a}, {amt})')
        else: out.append(f'transfer(acct {a} -> acct {b}, {amt})')
    return out

def adj_cmds(w):
    n, rest = decode_words(w)
    return [f'cmd {x}' for x in rest[:n]]

def parse_evm(out):
    res = {}
    for line in out.splitlines():
        m = re.search(r'data: (0x[0-9a-f]*) \}', line)
        if not m:
            continue
        h = m.group(1)[2:]
        w = [int(h[i:i + 64], 16) for i in range(0, len(h), 64)]
        if len(w) < 7:
            continue
        head = w[4] // 32    # the first dynamic array starts right after the head words
        def arr(off):
            i = off // 32
            return w[i + 1:i + 1 + w[i]]
        r = dict(failed=w[1], case=w[2], steps=w[3], original=arr(w[4]), shrunk=arr(w[5]), gas=w[6])
        if head >= 14:   # counters added in L7a: attempted, accepted, vacuous, commands executed per kind (0..3 until L7c, 0..4 since the adversarial Mint)
            r.update(attempted=w[7], accepted=w[8], vacuous=w[9], kinds=w[10:head])
        res[w[0]] = r
    return res

def parse_native(lines):
    res = {}
    for i, l in enumerate(lines):
        m = re.match(r'XW (\w+) failed=(\d) case=(\d+) steps=(\d+)', l)
        if m:
            def arr(s):
                s = s.split('=', 1)[1]
                return [int(x) for x in s.split(',')] if s else []
            res[m.group(1)] = dict(failed=int(m.group(2)), case=int(m.group(3)), steps=int(m.group(4)),
                                   original=arr(lines[i + 1]), shrunk=arr(lines[i + 2]))
    return res

def section(run, problems):
    sreg = json.load(open(os.path.join(ROOT, 'proof/stateful.json')))
    evm = parse_evm(run(['fe', 'test', '--filter', 'stateful_', '--show-logs'], cwd='tests-evm').stdout)
    out = tempfile.mkdtemp()
    b = run(['fe', 'build', '--backend', 'native', '--emit', 'executable', '--out-dir', out], cwd='proof-native')
    if b.returncode != 0:
        sys.exit('proof-native build failed:\n' + b.stdout + b.stderr)
    native = parse_native(run([os.path.join(out, 'proof_native')]).stdout.splitlines())
    s = ['## Stateful testing: random command sequences, shortest failing sequence (sonatina and native)', '',
         'A property is run over a `Seq<C, 8>` of commands; the invariant is checked after every command. Shrinking: halve the length, drop one command, then shrink single commands.',
         'Expected sequences were committed first (`docs/EXPECTATIONS.md`, section "L6"). Case numbers are 1-based. "found" lists the shrunk sequence; sonatina and native must agree on every word.', '',
         '| scenario | expected minimal sequence | found (shrunk) sequence | length | as expected | case | shrink steps | seed | sonatina = native | gas (sonatina) | rerun |',
         '|---|---|---|---|---|---|---|---|---|---|---|']
    for r in sreg:
        e, n = evm.get(r['id']), native.get(r['name'])
        if e is None or n is None:
            problems.append(f"{r['name']}: no stateful result (evm={e is not None}, native={n is not None})"); continue
        same = all(e[k] == n[k] for k in ('failed', 'case', 'steps', 'original', 'shrunk'))
        if not same:
            problems.append(f"{r['name']}: sonatina and native disagree: {e} vs {n}")
        cmds = adj_cmds if r['name'] == 'seq_adjacent' else bank_cmds
        if e['failed'] == 0:
            found, length, ok = f"passed {r['cases']} cases", '-', 'yes' if r['check'] == 'pass' and e['case'] == r['cases'] else 'NO'
        else:
            w = e['shrunk']
            found = ' ; '.join(cmds(w)); length = str(w[0])
            if r['check'] == 'seq_adjacent':
                ok = 'yes' if w[0] == 2 and w[1] == w[2] else 'NO'
            elif r['check'] == 'bank':
                c = [w[1 + 4 * i:5 + 4 * i] for i in range(w[0])]
                exact_len = w[0] == 3
                shape = exact_len and [x[0] for x in c] == [0, 1, 0] and all(x[3] == 1 and x[2] == 0 for x in c) and len({x[1] for x in c}) == 1
                ok = ('yes: exactly the pre-registered shape' + ('' if c[0][1] != 0 else ' (account 0)') if shape else 'NO')
                if shape and c[0][1] != 0:
                    ok = f'yes: length 3, kinds deposit/withdraw/deposit, amounts 1, one account (a = {c[0][1]}; a local minimum, as pre-registered)'
            else:
                ok = 'NO'
            if not ok.startswith('yes'):
                problems.append(f"{r['name']}: pre-registered expectation not met: {e['shrunk']}")
        if r['check'] == 'pass' and e['failed'] != 0:
            problems.append(f"{r['name']}: expected to pass")
        case = '-' if e['failed'] == 0 else str(e['case'] + 1)
        steps = '-' if e['failed'] == 0 else str(e['steps'])
        s.append(f"| {r['title']} | {r['expected']} | {found} | {length} | {ok} | {case} | {steps} | {r['seed']} | {'identical' if same else '**DIFFERENT**'} | {e['gas']:,} | `cd tests-evm && fe test --filter stateful_{r['name']} --show-logs`; native: `./scripts/proof.sh` |")
    s.append('')
    try:
        sys.path.insert(0, os.path.join(ROOT, 'scripts'))
        import proof_erc20_stateful
        s += proof_erc20_stateful.rows(run, problems)
    except ImportError:
        pass
    return s

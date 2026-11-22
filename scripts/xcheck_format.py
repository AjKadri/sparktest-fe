#!/usr/bin/env python3
"""Reads `fe test --show-logs` output (EVM), formats each Xc event like xcheck-native's println output."""
import re, sys
names = {1: "u256_below_1000", 2: "pair_u8_sum", 3: "arr_u64x4_sum", 4: "addr_below_0x1000", 5: "transfer_amount", 6: "late_fail", 7: "digest"}
for line in sys.stdin:
    m = re.search(r"data: (0x[0-9a-f]*) \}", line)
    if not m:
        continue
    h = m.group(1)[2:]
    w = [int(h[i:i + 64], 16) for i in range(0, len(h), 64)]
    if len(w) != 12:
        continue
    print(f"XC {names[w[0]]} failed={w[1]} case={w[2]} steps={w[3]}")
    print("XC original=" + ",".join(map(str, w[4:8])))
    print("XC shrunk=" + ",".join(map(str, w[8:12])))

import sys
# usage: fe test --show-logs | python3 -I scripts/decode_logs.py   -> prints PASS/FAIL lines and log data as 32-byte words (decimal)
import re
for l in sys.stdin:
    l = l.rstrip()
    m = re.search(r"data: (0x[0-9a-f]*) \}", l)
    if m:
        h = m.group(1)[2:]
        print("   log words:", [int(h[i:i+64], 16) for i in range(0, len(h), 64)])
    elif l.startswith(("PASS", "FAIL", "test result", "error", "    Test")):
        print(l)

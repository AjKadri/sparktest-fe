#!/usr/bin/env bash
# Runs the 1,000,000-case native test and prints its wall time.
set -eu
export PATH="$HOME/.fe/bin:$PATH"
cd "$(dirname "$0")/../tests-native"
fe test --filter million_cases
start=$(python3 -c 'import time; print(time.time())')
fe test --filter million_cases >/dev/null
end=$(python3 -c 'import time; print(time.time())')
python3 -c "print('wall time of whole fe test run (compile + 1M cases): %.2fs' % ($end - $start))"

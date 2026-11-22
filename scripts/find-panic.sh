#!/usr/bin/env bash
# Finds, shrinks and reports a failing (returned false) or PANICKING property on the native backend.
# A panic aborts a native process, so the property cannot be caught inside one run. Instead this script drives the replay executable
# (replay-native/): it bisects the case limit to the first case that aborts, then shrinks by replaying candidates as single-case runs,
# with the same greedy rule as check() (first candidate that still fails, repeat; at most 1000 accepted steps).
#
#   scripts/find-panic.sh <prop> <seed> <max_cases>        props: overflow | divzero | false
set -u
export PATH="$HOME/.fe/bin:$PATH"
cd "$(dirname "$0")/.."
prop="${1:?usage: find-panic.sh <overflow|divzero|false> <seed> <max_cases>}"; seed="${2:?seed}"; max="${3:?max_cases}"

exe="${REPLAY_NATIVE_EXE:-}"
if [ -z "$exe" ]; then
  out="$(mktemp -d)"
  ( cd replay-native && fe build --backend native --emit executable --out-dir "$out" >/dev/null 2>&1 ) || { echo "build of replay-native failed"; exit 2; }
  exe="$out/replay_native"
fi

runs=0
# run a command with all output discarded; the subshell does not exec it, so bash does not print "Abort trap" job messages for a panic
quiet() { ( "$@"; exit $? ) >/dev/null 2>&1; }
fails() {   # fails <cases>: true when `run` over cases 0..cases-1 fails (returned false, or the process aborted on a panic)
  runs=$((runs + 1))
  quiet "$exe" run "$prop" "$seed" "$1"
  [ $? -ne 0 ]
}

echo "property: $prop   seed: $seed   case limit: $max"
if ! fails "$max"; then
  echo "no failure in $max cases"; echo "native runs: $runs"; exit 0
fi

# bisect: smallest N such that cases 0..N-1 fail; then the first failing case has index N-1
lo=1; hi="$max"
while [ "$lo" -lt "$hi" ]; do
  mid=$(( (lo + hi) / 2 ))
  if fails "$mid"; then hi="$mid"; r="fails"; else lo=$((mid + 1)); r="ok"; fi
  echo "  bisect: cases=$mid -> $r   (window $lo..$hi)"
done
case_index=$((lo - 1))
words="$("$exe" gen "$prop" "$seed" "$case_index")"
errf="$(mktemp)"; trap 'rm -f "$errf"; [ -n "${out:-}" ] && rm -rf "$out"' EXIT
reason_of() {  # reason_of <words>: the process's own stderr text (a panic prints "panicked: ..."), or "returned false"
  { "$exe" eval "$prop" $1 >/dev/null 2>"$errf"; } 2>/dev/null
  if [ -s "$errf" ]; then tr -d '\n' < "$errf"; else echo "returned false"; fi
}
original_reason="$(reason_of "$words")"
echo "first failing case: $((case_index + 1)) (index $case_index)   input: $words   reason: $original_reason"

# shrink by replay: candidates come from the executable (the same Shrink code), each evaluated as a single-case run
cur="$words"; steps=0
while [ "$steps" -lt 1000 ]; do
  i=0; accepted=0
  while :; do
    cand="$("$exe" cand "$prop" "$i" $cur)"
    [ "$cand" = "NONE" ] && break
    runs=$((runs + 1))
    quiet "$exe" eval "$prop" $cand
    if [ $? -ne 0 ]; then cur="$cand"; steps=$((steps + 1)); accepted=1; break; fi
    i=$((i + 1))
  done
  [ "$accepted" = 1 ] || break
done
reason="$(reason_of "$cur")"
echo "shrunk: $cur   after $steps shrink steps   reason: $reason"
echo "RESULT prop=$prop seed=$seed case=$((case_index + 1)) steps=$steps original=\"$words\" shrunk=\"$cur\" reason=\"$reason\" native_runs=$runs"

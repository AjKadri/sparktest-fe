#!/bin/zsh
# run every repro and save output next to it
export PATH=$HOME/.fe/bin:$PATH
cd "$(dirname "$0")"
for f in e7a_static_trait_call e7a_workaround_and_controls; do
  { echo "\$ fe test repros/$f.fe"; fe test $f.fe 2>&1; } > $f.out
done
for f in e7b_println_untyped_literal e7b_workaround; do
  { echo "\$ fe test --backend native repros/$f.fe"; fe test --backend native $f.fe 2>&1; } > $f.out
done

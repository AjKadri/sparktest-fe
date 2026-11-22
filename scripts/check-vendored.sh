#!/usr/bin/env bash
# Verifies examples/erc20 is the unchanged upstream file (body below the header matches the recorded sha256) and that
# examples/erc20-buggy differs from it by exactly the one planted change.
set -eu
cd "$(dirname "$0")/.."
want=e583441a24ce20b27145331d1d06e11127614a30a0bfd26e5b3087e41931121d   # crates/fe/tests/fixtures/fe_test/erc20.fe @ e6e6342b252082f3fd8af5b9f763cb13296bf0a1
body() { awk '/^\/\/ ----- BEGIN (UPSTREAM )?FILE -----$/ {f=1; next} f' "$1"; }
got=$(body examples/erc20/src/lib.fe | shasum -a 256 | cut -d' ' -f1)
[ "$got" = "$want" ] || { echo "examples/erc20 differs from upstream (sha256 $got, want $want)"; exit 1; }
echo "examples/erc20 body is byte-identical to upstream ($want)"
changed=$(diff <(body examples/erc20/src/lib.fe) <(body examples/erc20-buggy/src/lib.fe) | grep -c '^[<>]' || true)
[ "$changed" = 4 ] || { echo "examples/erc20-buggy should differ by exactly one planted change (1 line removed, 3 added); diff lines: $changed"; exit 1; }
echo "examples/erc20-buggy differs from upstream by exactly the one planted change"

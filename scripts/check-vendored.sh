#!/usr/bin/env bash
# Verifies examples/erc20 is the unchanged upstream file (body below the header matches the recorded sha256) and that
# examples/erc20-buggy differs from it by exactly the one planted change.
set -eu
cd "$(dirname "$0")/.."
want=e583441a24ce20b27145331d1d06e11127614a30a0bfd26e5b3087e41931121d   # crates/fe/tests/fixtures/fe_test/erc20.fe @ e6e6342b252082f3fd8af5b9f763cb13296bf0a1
# sha-256 of stdin: sha256sum on Linux, shasum on macOS
sha() { if command -v sha256sum >/dev/null 2>&1; then sha256sum; else shasum -a 256; fi; }
body() { awk '/^\/\/ ----- BEGIN (UPSTREAM )?FILE -----$/ {f=1; next} f' "$1"; }
got=$(body examples/erc20/src/lib.fe | sha | cut -d' ' -f1)
[ "$got" = "$want" ] || { echo "examples/erc20 differs from upstream (sha256 $got, want $want)"; exit 1; }
echo "examples/erc20 body is byte-identical to upstream ($want)"
changed=$(diff <(body examples/erc20/src/lib.fe) <(body examples/erc20-buggy/src/lib.fe) | grep -c '^[<>]' || true)
[ "$changed" = 4 ] || { echo "examples/erc20-buggy should differ by exactly one planted change (1 line removed, 3 added); diff lines: $changed"; exit 1; }
echo "examples/erc20-buggy differs from upstream by exactly the one planted change"
changed2=$(diff <(body examples/erc20/src/lib.fe) <(body examples/erc20-stateful-bug/src/lib.fe) | grep -c '^[<>]' || true)
[ "$changed2" = 12 ] || { echo "examples/erc20-stateful-bug should differ from upstream only by the planted lines ($changed2 diff lines, want 12)"; exit 1; }
echo "examples/erc20-stateful-bug differs from upstream only by the planted change (12 diff lines)"

guide=16dd64484717dff0a225998176ff66a24e4704dfc903d8901b8d1ec1f1c57e4b   # the Fe Guide's "Complete ERC20" listing (https://fe-lang.org/examples/erc20/, fetched 2026-11-22)
gotg=$(body examples/coolcoin/src/lib.fe | sha | cut -d' ' -f1)
[ "$gotg" = "$guide" ] || { echo "examples/coolcoin differs from the Guide listing (sha256 $gotg, want $guide)"; exit 1; }
echo "examples/coolcoin body is byte-identical to the Fe Guide listing ($guide)"

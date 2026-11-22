#!/bin/zsh
# E0: compare ~/.fe/bin/fe against the sha256 digest GitHub publishes for the v26.7.0 asset
want=$(curl -s https://api.github.com/repos/argotorg/fe/releases/tags/v26.7.0 | grep -A12 '"name": "fe_mac_arm64"' | grep -o 'sha256:[0-9a-f]*' | head -1 | cut -d: -f2)
got=$(shasum -a 256 ~/.fe/bin/fe | cut -d' ' -f1)
echo "published: $want"; echo "local:     $got"; [ "$want" = "$got" ] && echo MATCH || echo MISMATCH

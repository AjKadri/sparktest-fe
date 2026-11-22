#!/bin/zsh
# E0: compare ~/.fe/bin/fe against the sha256 digest GitHub publishes for the v26.7.0 asset
want=$(curl -s https://api.github.com/repos/argotorg/fe/releases/tags/v26.7.0 | python3 -I -c 'import json,sys; [print(a["digest"].split(":")[1]) for a in json.load(sys.stdin)["assets"] if a["name"]=="fe_mac_arm64"]')
got=$(shasum -a 256 ~/.fe/bin/fe | cut -d' ' -f1)
echo "published: $want"; echo "local:     $got"; [ "$want" = "$got" ] && echo MATCH || echo MISMATCH

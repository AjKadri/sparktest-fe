#!/bin/zsh
# E0: compare ~/.fe/bin/fe with the sha256 digest GitHub's release API lists for asset fe_mac_arm64 (v26.7.0).
# The digest below was copied from the API response (releases/tags/v26.7.0 -> assets[].digest) earlier in the session;
# a re-query was rate-limited ("API rate limit exceeded"). No separate checksum file is published (assets: 5 binaries only).
want=fff9fe6ee9fad74f5c74039f8007e03b56d0f1f647d8244a43883f204671742e
got=$(shasum -a 256 ~/.fe/bin/fe | cut -d' ' -f1)
echo "published: $want"; echo "local:     $got"; [ "$want" = "$got" ] && echo MATCH || echo MISMATCH

#!/usr/bin/env bash
# Builds the web demo: compiles demo-wasm, copies the .wasm into web/, extracts the Fe sources of the demo
# properties, and records real sonatina (EVM) and native runs into web/props.json.
set -eu
cd "$(dirname "$0")/.."
python3 scripts/build_demo.py

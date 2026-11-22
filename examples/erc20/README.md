# examples/erc20 (vendored, unchanged)

`src/lib.fe` is the ERC20 contract `CoolCoin` (and its own `#[test]`) from the Fe repository, vendored unchanged to run
Sparktest against a contract we did not write.

- Source: `crates/fe/tests/fixtures/fe_test/erc20.fe`, https://github.com/argotorg/fe, commit `e6e6342b252082f3fd8af5b9f763cb13296bf0a1` (Fe v26.7.0).
- License: Apache License 2.0 (the Fe repository's `LICENSE-APACHE`, copied here as `LICENSE-APACHE`).
- The only addition is the comment header at the top of `src/lib.fe`; `scripts/check-vendored.sh` verifies that the rest is byte-identical to upstream.
- Behaviour worth knowing: `transfer` and `transferFrom` return `false` on insufficient balance/allowance (they do not revert), and `mint` is open to anyone.

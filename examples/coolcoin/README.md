# examples/coolcoin (vendored, unchanged)

`src/lib.fe` is the "Complete ERC20" example (contract `CoolCoin`, with its own three `#[test]`s) from the Fe Guide, https://fe-lang.org/examples/erc20/, fetched 2026-11-22.

- It compiles and passes its own tests unchanged on Fe 26.7.0 (e6e6342); no fix was needed.
- The only addition is the comment header at the top of `src/lib.fe`; `scripts/check-vendored.sh` verifies that the rest is byte-identical to the page's listing (sha256 `16dd6448…c57e4b`).
- Licence: the page states none. Its repository links point to https://github.com/argotorg/fe (Apache-2.0). The website's own source repository was not found, so it is not known whether the page code is covered by that licence; it is vendored unchanged with attribution, for testing.
- Differences from the compiler-repo ERC20 test fixture (`examples/erc20`): `transfer`/`transferFrom` revert on a shortfall instead of returning `false`, `mint` needs the MINTER role (granted to the `owner` init argument), and it has `burn`, `burnFrom`, `increaseAllowance`, `decreaseAllowance`, `name`, `symbol`, `decimals`.

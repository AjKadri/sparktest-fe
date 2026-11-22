# examples/erc20-buggy (PLANTED BUG, not a real example)

A copy of `examples/erc20` with ONE deliberate bug: in `Transfer`, when `to == sender` the debit is skipped but the credit
is applied, so a self-transfer mints tokens. It exists to show Sparktest catching and shrinking a real contract bug.
Apache-2.0, derived from the Fe repository (see `examples/erc20/README.md`).

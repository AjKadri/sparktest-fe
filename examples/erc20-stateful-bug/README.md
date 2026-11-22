# examples/erc20-stateful-bug (PLANTED BUG, not a real example)

A copy of `examples/erc20` (the ERC20 test fixture from the Fe compiler repo) with one deliberate bug that needs two calls to show: once a transfer takes a holder
to exactly 0, the next `transfer` into that holder is credited twice. It exists to show stateful testing finding and shrinking it. Apache-2.0, derived from the Fe repository.

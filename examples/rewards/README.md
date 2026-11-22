# examples/rewards (written for the Sparktest proof, not a Fe example)

`RewardsBuggy` has a planted overflow in `claim` (`stake * RATE` in `u64`); `RewardsFixed` does not. See `docs/PROOF.md`
for how Sparktest finds, through `evm.try_call`, the smallest stake that makes `claim` panic. Not audited; not for production.

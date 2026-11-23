#!/usr/bin/env bash
# Checks the git dependency shown in the README Quickstart: builds a throw-away ingot that depends on sparktest and sparktest_evm
# through source = "https://github.com/AjKadri/sparktest-fe", rev = "fa9695c036dd35a5ae4644fd8b512ea38154740f" (a full commit hash: Fe 26.7.0 rejects tag names), and runs one property with `fe test`.
# Needs network access and that commit on GitHub. Not part of test-all.sh.
#   ./scripts/check-git-dep.sh                 uses the URL and rev below
#   REPO_URL=file:///path/to/clone REV=<commit> ./scripts/check-git-dep.sh     tests the same syntax against a local clone
set -eu
export PATH="$HOME/.fe/bin:$PATH"
REPO_URL="${REPO_URL:-https://github.com/AjKadri/sparktest-fe}"
REV="${REV:-fa9695c036dd35a5ae4644fd8b512ea38154740f}"
dir="$(mktemp -d)"
trap 'rm -rf "$dir"' EXIT
mkdir -p "$dir/src"
cat > "$dir/fe.toml" <<TOML
[ingot]
name = "git_dep_check"
version = "0.1.0"

[dependencies]
sparktest = { source = "$REPO_URL", rev = "$REV", path = "sparktest" }
sparktest_evm = { source = "$REPO_URL", rev = "$REV", path = "sparktest-evm" }
TOML
cat > "$dir/src/lib.fe" <<'FE'
use std::evm::Evm
use sparktest::{check, Config, Outcome}
use sparktest_evm::fixed_seed

#[test]
fn a_property_runs_through_the_git_dependency() uses (evm: mut Evm) {
    match check(Config::new(fixed_seed(1)), |x: u8| x != 255) {
        Outcome::Pass { cases: _ } => { assert!(false) }
        Outcome::Fail { original: _, shrunk, case: _, seed: _, steps: _, early: _ } => { assert!(shrunk == 255) }
    }
}
FE
cd "$dir"
fe test
echo "git dependency OK: $REPO_URL @ $REV"

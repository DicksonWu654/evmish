#!/bin/sh
set -eu

repo_root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$repo_root"
evm_version=${EVM_VERSION:-cancun}
exec solc --evm-version "$evm_version" --base-path . --bin examples/*.sol >/dev/null

#!/usr/bin/env sh
set -eu

demo_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
solc_path=${SOLC_PATH:-$(command -v solc)}
if [ -z "$solc_path" ]; then
    echo "solc is required (set SOLC_PATH to a local compiler)" >&2
    exit 1
fi
cd "$demo_dir"
exec forge test --offline --use "$solc_path" -vv

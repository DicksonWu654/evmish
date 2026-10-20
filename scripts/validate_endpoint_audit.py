#!/usr/bin/env python3
"""Validate the dated chain-ID and mainnet endpoint audit."""

from __future__ import annotations

import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
REGISTRY = ROOT / "probes" / "chains.json"
AUDIT = ROOT / "docs" / "endpoint-audit.md"
DATE = "2026-10-18"


def main() -> int:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    text = AUDIT.read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if line.startswith("| ") and not line.startswith("|---") and "Chain |" not in line]
    if len(rows) != len(registry):
        raise SystemExit(f"endpoint audit has {len(rows)} rows; registry has {len(registry)} chains")
    for name, config in registry.items():
        match = next((line for line in rows if line.startswith(f"| {name} |")), None)
        if not match:
            raise SystemExit(f"missing endpoint audit row for {name}")
        cells = [cell.strip() for cell in match.strip("|").split("|")]
        expected = str(config["chain_id"])
        if cells[1] != expected:
            raise SystemExit(f"{name}: expected ID {expected}, audit has {cells[1]}")
        result_path = ROOT / DATE / "noop"
        if name == "megaeth":
            if "mainnet.megaeth.com/rpc" not in match or "mainnet-id-match" not in match:
                raise SystemExit("MegaETH audit does not record the mainnet endpoint and matching ID")
            if "carrot.megaeth.com/rpc" not in text or "6343" not in text:
                raise SystemExit("MegaETH preserved testnet correction is missing")
        if name == "evmos" and "no-public-mainnet-rpc" not in match:
            raise SystemExit("Evmos public-RPC gap is not recorded")
    if "shemnon/evm-directory MegaETH" in (ROOT / "CATALOG.md").read_text(encoding="utf-8"):
        raise SystemExit("obsolete MegaETH prior-art conflict remains in the catalog")
    if "chain ID 6343" not in text:
        raise SystemExit("endpoint audit does not explain the preserved testnet fact")
    print(f"endpoint audit validation passed: {len(rows)} registry chains")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

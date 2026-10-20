#!/usr/bin/env python3
"""Validate the E17 chain-specific fee-oracle comparison."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FOLLOWUP = ROOT / "results" / "2026-10-18" / "fee-oracle-followup"
EXPECTED_ORACLES = {
    "op-mainnet": {"op-gaspriceoracle-l1BaseFee", "op-gaspriceoracle-getL1Fee"},
    "arbitrum-one": {"arb-gasinfo-l1-base-fee-estimate", "arb-gasinfo-l1-gas-price-estimate"},
}
ALLOWED = {"match", "rpc-rejected", "oracle-disagreement"}


def load(path: str) -> dict:
    full = ROOT / path
    if not full.exists():
        raise SystemExit(f"missing evidence file: {path}")
    try:
        return json.loads(full.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON evidence {path}: {exc}") from exc


def main() -> int:
    report = load("results/2026-10-18/fee-oracle-followup/COMPARISON.json")
    if report.get("schema") != 1 or set(report.get("chains", {})) != set(EXPECTED_ORACLES):
        raise SystemExit("fee-oracle report has the wrong schema or chain set")
    if "catalog labels" not in report.get("purpose", ""):
        raise SystemExit("report does not state that catalog labels are unchanged")

    for chain, expected_oracles in EXPECTED_ORACLES.items():
        item = report["chains"][chain]
        for role in ("primary", "secondary"):
            endpoint = item.get(role, {})
            result_path = endpoint.get("result")
            if not result_path:
                raise SystemExit(f"{chain}/{role}: missing result path")
            result = load(result_path)
            if result.get("chain") != chain or result.get("probe_count") != 0:
                raise SystemExit(f"{chain}/{role}: result metadata mismatch")
            if set(result.get("oracles", {})) != expected_oracles:
                raise SystemExit(f"{chain}/{role}: oracle set mismatch")
            if endpoint.get("rpc") != result.get("rpc") or endpoint.get("block_number") != result.get("block_number"):
                raise SystemExit(f"{chain}/{role}: endpoint metadata does not match result")
            raw_dir = endpoint.get("raw_evidence_dir")
            if not raw_dir or not (ROOT / raw_dir / "raw").is_dir():
                raise SystemExit(f"{chain}/{role}: missing raw evidence directory")
            for name in expected_oracles:
                interpretation = result["oracles"][name].get("interpretation", {})
                if interpretation.get("status") not in {"ok", "rpc-rejected", "execution-failure"}:
                    raise SystemExit(f"{chain}/{role}/{name}: invalid status")
                if interpretation.get("status") == "ok" and not {"raw_return", "uint256"} <= set(interpretation):
                    raise SystemExit(f"{chain}/{role}/{name}: successful oracle lacks decoded return")

        comparison = item.get("comparison", {})
        if comparison.get("classification") not in ALLOWED:
            raise SystemExit(f"{chain}: invalid comparison classification")
        if comparison.get("moving_block_values_compared") is not False:
            raise SystemExit(f"{chain}: moving values were incorrectly compared")
        if set(comparison.get("oracles", {})) != expected_oracles:
            raise SystemExit(f"{chain}: comparison oracle set mismatch")
        for name, oracle in comparison["oracles"].items():
            if oracle.get("classification") not in ALLOWED:
                raise SystemExit(f"{chain}/{name}: invalid oracle classification")
            if not isinstance(oracle.get("all_differences"), list):
                raise SystemExit(f"{chain}/{name}: differences were not retained")

    if not (FOLLOWUP / "SUMMARY.md").exists():
        raise SystemExit("missing fee-oracle summary")
    print("fee-oracle follow-up validation passed: 2 chains, 4 endpoints, 4 direct oracle pairs, raw evidence present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

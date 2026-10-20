#!/usr/bin/env python3
"""Validate the E18 block-context and BLOCKHASH comparison."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FOLLOWUP = ROOT / "results" / "2026-10-18" / "block-context-followup"
EXPECTED_CHAINS = {"ethereum", "arbitrum-one", "op-mainnet"}
EXPECTED_PROBES = {
    "number",
    "timestamp",
    "blockhash-n-minus-1",
    "blockhash-n-minus-256",
    "blockhash-n-minus-257",
}
ALLOWED = {"match", "rpc-rejected", "header-disagreement", "probe-disagreement"}


def load(path: str) -> dict:
    full = ROOT / path
    if not full.exists():
        raise SystemExit(f"missing evidence file: {path}")
    try:
        return json.loads(full.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON evidence {path}: {exc}") from exc


def main() -> int:
    report = load("results/2026-10-18/block-context-followup/COMPARISON.json")
    if report.get("schema") != 1 or set(report.get("chains", {})) != EXPECTED_CHAINS:
        raise SystemExit("block-context report has the wrong schema or chain set")
    if set(report.get("probe_set", [])) != EXPECTED_PROBES:
        raise SystemExit("block-context report has the wrong probe set")
    if "catalog labels" not in report.get("purpose", ""):
        raise SystemExit("report does not state that catalog labels are unchanged")

    for chain, item in report["chains"].items():
        for role in ("primary", "secondary"):
            endpoint = item.get(role, {})
            result_path = endpoint.get("result")
            if not result_path:
                raise SystemExit(f"{chain}/{role}: missing result path")
            result = load(result_path)
            if result.get("chain") != chain or result.get("probe_count") != len(EXPECTED_PROBES):
                raise SystemExit(f"{chain}/{role}: result metadata mismatch")
            if set(result.get("probes", {})) != EXPECTED_PROBES:
                raise SystemExit(f"{chain}/{role}: probe set mismatch")
            if endpoint.get("rpc") != result.get("rpc") or endpoint.get("block_number") != result.get("block_number"):
                raise SystemExit(f"{chain}/{role}: endpoint metadata does not match result")
            if endpoint.get("block") != result.get("block"):
                raise SystemExit(f"{chain}/{role}: block context does not match result")
            raw_dir = endpoint.get("raw_evidence_dir")
            if not raw_dir or not (ROOT / raw_dir / "raw").is_dir():
                raise SystemExit(f"{chain}/{role}: missing raw evidence directory")
            for name in EXPECTED_PROBES:
                interpretation = result["probes"][name].get("interpretation", {})
                status = interpretation.get("status")
                if status not in {"ok", "rpc-rejected", "execution-failure"}:
                    raise SystemExit(f"{chain}/{role}/{name}: invalid status")
                if status == "ok" and not {"raw_return", "uint256"} <= set(interpretation):
                    raise SystemExit(f"{chain}/{role}/{name}: successful probe lacks decoded return")
                if name in {"number", "timestamp"} and status == "ok" and not {"header_value", "header_matches"} <= set(interpretation):
                    raise SystemExit(f"{chain}/{role}/{name}: missing header comparison")
                if name == "blockhash-n-minus-257" and status == "ok" and not {"expected_zero_by_evm_depth_rule", "matches_expected_zero"} <= set(interpretation):
                    raise SystemExit(f"{chain}/{role}/{name}: missing depth boundary comparison")

        comparison = item.get("comparison", {})
        if comparison.get("classification") not in ALLOWED:
            raise SystemExit(f"{chain}: invalid overall comparison classification")
        if comparison.get("moving_block_values_compared") is not False:
            raise SystemExit(f"{chain}: moving values were incorrectly compared")
        if set(comparison.get("probes", {})) != EXPECTED_PROBES:
            raise SystemExit(f"{chain}: comparison probe set mismatch")
        for name, probe in comparison["probes"].items():
            if probe.get("classification") not in ALLOWED:
                raise SystemExit(f"{chain}/{name}: invalid probe classification")
            if probe.get("moving_block_values_compared") is not False:
                raise SystemExit(f"{chain}/{name}: moving values were incorrectly compared")
            if not isinstance(probe.get("all_differences"), list) or not isinstance(probe.get("stable_differences"), list):
                raise SystemExit(f"{chain}/{name}: differences were not retained")

    if not (FOLLOWUP / "SUMMARY.md").exists():
        raise SystemExit("missing block-context summary")
    print("block-context follow-up validation passed: 3 chains, 6 endpoints, 15 probes, header and depth-boundary evidence present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

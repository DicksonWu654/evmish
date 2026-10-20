#!/usr/bin/env python3
"""Validate the focused E16 PREVRANDAO endpoint comparison."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
FOLLOWUP = ROOT / "results" / "2026-10-18" / "entropy-followup"
EXPECTED_CHAINS = {"ethereum", "zksync-era"}
ALLOWED_CLASSIFICATIONS = {"match", "rpc-rejected", "header-disagreement"}
REQUIRED_FIELDS = {"status", "error_class"}


def load_relative(path: str) -> dict:
    full = ROOT / path
    if not full.exists():
        raise SystemExit(f"missing evidence file: {path}")
    try:
        return json.loads(full.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON evidence {path}: {exc}") from exc


def main() -> int:
    report_path = FOLLOWUP / "COMPARISON.json"
    report = load_relative("results/2026-10-18/entropy-followup/COMPARISON.json")
    if report.get("schema") != 1 or report.get("probe") != "prevrandao":
        raise SystemExit("unexpected entropy follow-up schema or probe")
    if set(report.get("chains", {})) != EXPECTED_CHAINS:
        raise SystemExit("entropy follow-up must contain Ethereum and zkSync Era")
    if "catalog labels" not in report.get("purpose", ""):
        raise SystemExit("report does not state that catalog labels are unchanged")

    for chain, item in report["chains"].items():
        for role in ("primary", "secondary"):
            endpoint = item.get(role, {})
            result_path = endpoint.get("result")
            if not result_path:
                raise SystemExit(f"{chain}/{role}: missing result path")
            result = load_relative(result_path)
            if result.get("chain") != chain or result.get("probe_count") != 1:
                raise SystemExit(f"{chain}/{role}: result metadata mismatch")
            probe = result.get("probes", {}).get("prevrandao")
            if not probe:
                raise SystemExit(f"{chain}/{role}: missing PREVRANDAO probe")
            interpretation = probe.get("interpretation", {})
            if not REQUIRED_FIELDS <= set(interpretation):
                raise SystemExit(f"{chain}/{role}: incomplete PREVRANDAO interpretation")
            if interpretation.get("status") == "ok":
                for field in ("uint256", "header_value", "header_matches", "raw_return"):
                    if field not in interpretation:
                        raise SystemExit(f"{chain}/{role}: successful PREVRANDAO result lacks {field}")
            raw_dir = endpoint.get("raw_evidence_dir")
            if not raw_dir or not (ROOT / raw_dir / "raw").is_dir():
                raise SystemExit(f"{chain}/{role}: missing raw evidence directory")
            if endpoint.get("rpc") != result.get("rpc"):
                raise SystemExit(f"{chain}/{role}: endpoint RPC does not match result")
            if endpoint.get("block_number") != result.get("block_number"):
                raise SystemExit(f"{chain}/{role}: endpoint block does not match result")

        comparison = item.get("comparison", {})
        if comparison.get("classification") not in ALLOWED_CLASSIFICATIONS:
            raise SystemExit(f"{chain}: invalid comparison classification")
        if comparison.get("moving_block_values_compared") is not False:
            raise SystemExit(f"{chain}: moving block values must not be compared")
        for side in ("primary", "secondary"):
            if set(comparison.get(side, {})) < {"status", "error_class", "uint256", "header_value", "header_matches"}:
                raise SystemExit(f"{chain}: comparison missing {side} fields")

    if not (FOLLOWUP / "SUMMARY.md").exists():
        raise SystemExit("missing entropy follow-up summary")
    print("entropy follow-up validation passed: 2 chains, 4 endpoints, PREVRANDAO raw evidence and classifications present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

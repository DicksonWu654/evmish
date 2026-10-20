#!/usr/bin/env python3
"""Rerun OP and Arbitrum chain-specific fee oracles on two endpoints."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "probes"))

from run_creation_probes import ORACLE_CALLS, run_endpoint, write_json  # noqa: E402


REGISTRY = ROOT / "probes" / "chains.json"
DEFAULT_DATE = "2026-10-18"
DEFAULT_OUTPUT = "fee-oracle-followup"
CHAINS = ("op-mainnet", "arbitrum-one")


def oracle_fields(result: dict, name: str) -> dict:
    oracle = result.get("oracles", {}).get(name, {})
    interpretation = oracle.get("interpretation", {})
    return {
        "status": interpretation.get("status"),
        "error_class": interpretation.get("error_class"),
        "uint256": interpretation.get("uint256"),
        "raw_return": interpretation.get("raw_return"),
    }


def endpoint_record(result: dict, result_path: pathlib.Path, oracle_names: list[str]) -> dict:
    return {
        "rpc": result.get("rpc"),
        "rpc_source": result.get("rpc_source"),
        "rpc_source_accessed": result.get("rpc_source_accessed"),
        "chain_id_expected": result.get("chain_id_expected"),
        "chain_id_observed": result.get("chain_id_observed"),
        "status": result.get("status"),
        "block_number": result.get("block_number"),
        "block": result.get("block"),
        "observed_at": result.get("observed_at"),
        "result": str(result_path.relative_to(ROOT)),
        "raw_evidence_dir": result.get("evidence_dir"),
        "oracles": {name: oracle_fields(result, name) for name in oracle_names},
    }


def compare(primary: dict, secondary: dict, oracle_names: list[str]) -> dict:
    oracle_comparisons = {}
    classifications = []
    for name in oracle_names:
        primary_values = primary["oracles"][name]
        secondary_values = secondary["oracles"][name]
        stable_differences = []
        all_differences = []
        for field in ("status", "error_class", "uint256", "raw_return"):
            if primary_values.get(field) != secondary_values.get(field):
                difference = {
                    "field": field,
                    "primary": primary_values.get(field),
                    "secondary": secondary_values.get(field),
                }
                all_differences.append(difference)
                if field in {"status", "error_class"}:
                    stable_differences.append(difference)

        statuses = {primary_values.get("status"), secondary_values.get("status")}
        if "rpc-rejected" in statuses:
            classification = "rpc-rejected"
        elif stable_differences:
            classification = "oracle-disagreement"
        else:
            classification = "match"
        classifications.append(classification)
        oracle_comparisons[name] = {
            "classification": classification,
            "primary": primary_values,
            "secondary": secondary_values,
            "stable_differences": stable_differences,
            "all_differences": all_differences,
            "value_changed_at_moving_block": any(
                difference["field"] in {"uint256", "raw_return"} for difference in all_differences
            ),
        }

    if "rpc-rejected" in classifications:
        classification = "rpc-rejected"
    elif "oracle-disagreement" in classifications:
        classification = "oracle-disagreement"
    else:
        classification = "match"
    return {
        "classification": classification,
        "oracles": oracle_comparisons,
        "moving_block_values_compared": False,
        "note": "Fee-oracle uint256 and raw values may differ because each endpoint was queried at its own latest block; status and error class are the stable comparison signals.",
    }


def markdown_summary(report: dict, output_root: pathlib.Path) -> str:
    def link(path: str) -> str:
        return os.path.relpath(ROOT / path, output_root).replace(os.sep, "/")

    lines = [
        "# Chain-specific fee-oracle follow-up (2026-10-18)",
        "",
        "This pass reran the OP Mainnet GasPriceOracle and Arbitrum ArbGasInfo read calls on their primary and independent secondary public RPC endpoints. Every endpoint retains its block context and raw request/response files.",
        "",
        "| Chain | Primary | Secondary | Blocks | Comparison | Oracle observations | Raw evidence |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for chain, item in report["chains"].items():
        primary = item["primary"]
        secondary = item["secondary"]
        comparison = item["comparison"]
        statuses = []
        for name, oracle in comparison["oracles"].items():
            statuses.append(f"`{name}`={oracle['classification']}")
        lines.append(
            f"| {chain} | [{primary['rpc']}]({link(primary['result'])}) | [{secondary['rpc']}]({link(secondary['result'])}) | {primary['block_number'] or '—'} / {secondary['block_number'] or '—'} | **{comparison['classification']}** | {'; '.join(statuses)} | [{chain} primary]({link(primary['raw_evidence_dir'])}) / [{chain} secondary]({link(secondary['raw_evidence_dir'])}) |"
        )
    lines.extend(
        [
            "",
            "`match` means both endpoints returned the same oracle status and error class. Raw return values and decoded integers are retained even when they differ at moving latest blocks; those changes are reported as `value_changed_at_moving_block`, not promoted to a portability claim. RPC rejection remains distinct from VM execution failure.",
            "",
            "The catalog labels remain unchanged by this follow-up.",
            "",
        ]
    )
    return "\n".join(lines)


def run(date: str, output_name: str, chains: list[str]) -> dict:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    output_root = ROOT / "results" / date / output_name
    report = {
        "schema": 1,
        "date": date,
        "purpose": "independent endpoint follow-up for chain-specific fee oracles; catalog labels are not changed automatically",
        "chains": {},
    }
    for chain in chains:
        if chain not in CHAINS:
            raise ValueError(f"unsupported fee-oracle follow-up chain: {chain}")
        config = registry[chain]
        primary_entries = [entry for entry in config.get("rpcs", []) if entry.get("role") != "secondary"]
        secondary_entries = [entry for entry in config.get("rpcs", []) if entry.get("role") == "secondary"]
        if not primary_entries or not secondary_entries:
            raise ValueError(f"{chain}: primary and secondary endpoints are required")
        oracle_names = [oracle["name"] for oracle in ORACLE_CALLS[chain]]
        chain_dir = output_root / chain
        endpoint_results = {}
        observed_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        for role, rpc_entry in (("primary", primary_entries[0]), ("secondary", secondary_entries[0])):
            # An empty probe selection keeps this pass focused on direct fee
            # oracle calls while retaining the runner's block/context evidence.
            result = run_endpoint(chain, config, rpc_entry, chain_dir / role, observed_at, [])
            result_path = chain_dir / role / f"{chain}.json"
            write_json(result_path, result)
            endpoint_results[role] = endpoint_record(result, result_path, oracle_names)
        report["chains"][chain] = {
            "primary": endpoint_results["primary"],
            "secondary": endpoint_results["secondary"],
            "comparison": compare(endpoint_results["primary"], endpoint_results["secondary"], oracle_names),
        }

    write_json(output_root / "COMPARISON.json", report)
    (output_root / "SUMMARY.md").write_text(markdown_summary(report, output_root), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=DEFAULT_DATE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    parser.add_argument("--chains", default=",".join(CHAINS))
    args = parser.parse_args()
    chains = [name.strip() for name in args.chains.split(",") if name.strip()]
    if not chains:
        parser.error("at least one chain is required")
    report = run(args.date, args.output, chains)
    counts = {}
    for item in report["chains"].values():
        label = item["comparison"]["classification"]
        counts[label] = counts.get(label, 0) + 1
    print(
        f"fee-oracle follow-up complete: {len(report['chains'])} chains, "
        + ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

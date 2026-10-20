#!/usr/bin/env python3
"""Rerun block-context and BLOCKHASH boundary probes on paired endpoints."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import os
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "probes"))

from run_creation_probes import run_endpoint, write_json  # noqa: E402


REGISTRY = ROOT / "probes" / "chains.json"
DEFAULT_DATE = "2026-10-18"
DEFAULT_OUTPUT = "block-context-followup"
CHAINS = ("ethereum", "arbitrum-one", "op-mainnet")
PROBES = (
    "number",
    "timestamp",
    "blockhash-n-minus-1",
    "blockhash-n-minus-256",
    "blockhash-n-minus-257",
)
HEADER_PROBES = {"number", "timestamp"}
BOUNDARY_PROBE = "blockhash-n-minus-257"


def probe_fields(result: dict, name: str) -> dict:
    interpretation = result.get("probes", {}).get(name, {}).get("interpretation", {})
    return {
        "status": interpretation.get("status"),
        "error_class": interpretation.get("error_class"),
        "uint256": interpretation.get("uint256"),
        "raw_return": interpretation.get("raw_return"),
        "header_value": interpretation.get("header_value"),
        "header_matches": interpretation.get("header_matches"),
        "expected_zero_by_evm_depth_rule": interpretation.get("expected_zero_by_evm_depth_rule"),
        "matches_expected_zero": interpretation.get("matches_expected_zero"),
    }


def endpoint_record(result: dict, result_path: pathlib.Path) -> dict:
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
        "probes": {name: probe_fields(result, name) for name in PROBES},
    }


def compare_probe(primary: dict, secondary: dict, name: str) -> dict:
    primary_values = primary["probes"][name]
    secondary_values = secondary["probes"][name]
    stable_fields = {"status", "error_class"}
    if name in HEADER_PROBES:
        stable_fields.add("header_matches")
    if name == BOUNDARY_PROBE:
        stable_fields.add("matches_expected_zero")
    all_differences = []
    stable_differences = []
    for field in (
        "status",
        "error_class",
        "uint256",
        "raw_return",
        "header_value",
        "header_matches",
        "expected_zero_by_evm_depth_rule",
        "matches_expected_zero",
    ):
        if primary_values.get(field) != secondary_values.get(field):
            difference = {
                "field": field,
                "primary": primary_values.get(field),
                "secondary": secondary_values.get(field),
            }
            all_differences.append(difference)
            if field in stable_fields:
                stable_differences.append(difference)

    statuses = {primary_values.get("status"), secondary_values.get("status")}
    if "rpc-rejected" in statuses:
        classification = "rpc-rejected"
    elif name in HEADER_PROBES and False in {primary_values.get("header_matches"), secondary_values.get("header_matches")}:
        classification = "header-disagreement"
    elif name == BOUNDARY_PROBE and False in {primary_values.get("matches_expected_zero"), secondary_values.get("matches_expected_zero")}:
        classification = "header-disagreement"
    elif stable_differences:
        classification = "header-disagreement" if name in HEADER_PROBES or name == BOUNDARY_PROBE else "probe-disagreement"
    else:
        classification = "match"
    return {
        "classification": classification,
        "primary": primary_values,
        "secondary": secondary_values,
        "stable_differences": stable_differences,
        "all_differences": all_differences,
        "moving_block_values_compared": False,
        "value_changed_at_moving_block": any(
            difference["field"] in {"uint256", "raw_return", "header_value"} for difference in all_differences
        ),
    }


def compare(primary: dict, secondary: dict) -> dict:
    probes = {name: compare_probe(primary, secondary, name) for name in PROBES}
    classifications = [item["classification"] for item in probes.values()]
    if "rpc-rejected" in classifications:
        classification = "rpc-rejected"
    elif "header-disagreement" in classifications:
        classification = "header-disagreement"
    elif "probe-disagreement" in classifications:
        classification = "probe-disagreement"
    else:
        classification = "match"
    return {
        "classification": classification,
        "probes": probes,
        "moving_block_values_compared": False,
        "note": "NUMBER and TIMESTAMP header values, and BLOCKHASH returns, can differ at moving latest blocks; status, header_matches, and the depth-257 zero rule are the stable semantic comparisons.",
    }


def markdown_summary(report: dict, output_root: pathlib.Path) -> str:
    def link(path: str) -> str:
        return os.path.relpath(ROOT / path, output_root).replace(os.sep, "/")

    lines = [
        "# Block-context boundary follow-up (2026-10-18)",
        "",
        "This pass reran `NUMBER`, `TIMESTAMP`, and `BLOCKHASH(NUMBER-1/256/257)` on the primary and independent secondary endpoints for Ethereum, Arbitrum One, and OP Mainnet. Raw requests and block headers are retained for every endpoint.",
        "",
        "| Chain | Primary | Secondary | Blocks | Overall | Probe classifications | Evidence |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for chain, item in report["chains"].items():
        primary = item["primary"]
        secondary = item["secondary"]
        comparison = item["comparison"]
        probe_statuses = "; ".join(f"`{name}`={probe['classification']}" for name, probe in comparison["probes"].items())
        lines.append(
            f"| {chain} | [{primary['rpc']}]({link(primary['result'])}) | [{secondary['rpc']}]({link(secondary['result'])}) | {primary['block_number'] or '—'} / {secondary['block_number'] or '—'} | **{comparison['classification']}** | {probe_statuses} | [{chain} primary raw]({link(primary['raw_evidence_dir'])}) / [{chain} secondary raw]({link(secondary['raw_evidence_dir'])}) |"
        )
    lines.extend(
        [
            "",
            "`rpc-rejected` preserves an endpoint-level rejection and does not imply an unsupported opcode. `header-disagreement` records a probe result that does not match its captured `NUMBER`/`TIMESTAMP` header, a different header relationship between endpoints, or a different depth-257 zero result. Dynamic block values are retained but are not compared as drift signals across moving latest blocks.",
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
        "probe_set": list(PROBES),
        "purpose": "independent endpoint follow-up for block context and BLOCKHASH boundaries; catalog labels are not changed automatically",
        "chains": {},
    }
    for chain in chains:
        if chain not in CHAINS:
            raise ValueError(f"unsupported block-context follow-up chain: {chain}")
        config = registry[chain]
        primary_entries = [entry for entry in config.get("rpcs", []) if entry.get("role") != "secondary"]
        secondary_entries = [entry for entry in config.get("rpcs", []) if entry.get("role") == "secondary"]
        if not primary_entries or not secondary_entries:
            raise ValueError(f"{chain}: primary and secondary endpoints are required")
        chain_dir = output_root / chain
        endpoint_results = {}
        observed_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        for role, rpc_entry in (("primary", primary_entries[0]), ("secondary", secondary_entries[0])):
            result = run_endpoint(chain, config, rpc_entry, chain_dir / role, observed_at, list(PROBES))
            result_path = chain_dir / role / f"{chain}.json"
            write_json(result_path, result)
            endpoint_results[role] = endpoint_record(result, result_path)
        report["chains"][chain] = {
            "primary": endpoint_results["primary"],
            "secondary": endpoint_results["secondary"],
            "comparison": compare(endpoint_results["primary"], endpoint_results["secondary"]),
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
        f"block-context follow-up complete: {len(report['chains'])} chains, "
        + ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

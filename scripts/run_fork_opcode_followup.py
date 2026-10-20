#!/usr/bin/env python3
"""Rerun fork-gated opcode probes on Base's paired public endpoints."""

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
DEFAULT_OUTPUT = "fork-opcode-followup"
CHAIN = "base"
PROBES = ("push0", "tstore-tload", "mcopy")


def probe_fields(result: dict, name: str) -> dict:
    interpretation = result.get("probes", {}).get(name, {}).get("interpretation", {})
    return {
        "status": interpretation.get("status"),
        "error_class": interpretation.get("error_class"),
        "uint256": interpretation.get("uint256"),
        "raw_return": interpretation.get("raw_return"),
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
    differences = []
    for field in ("status", "error_class", "uint256", "raw_return"):
        if primary_values.get(field) != secondary_values.get(field):
            differences.append(
                {
                    "field": field,
                    "primary": primary_values.get(field),
                    "secondary": secondary_values.get(field),
                }
            )
    statuses = {primary_values.get("status"), secondary_values.get("status")}
    if "rpc-rejected" in statuses:
        classification = "rpc-rejected"
    elif "execution-failure" in statuses:
        classification = "execution-failure"
    elif differences:
        classification = "opcode-disagreement"
    else:
        classification = "match"
    return {
        "classification": classification,
        "primary": primary_values,
        "secondary": secondary_values,
        "differences": differences,
        "execution_failure_is_distinct_from_rpc_rejection": True,
    }


def compare(primary: dict, secondary: dict) -> dict:
    probes = {name: compare_probe(primary, secondary, name) for name in PROBES}
    classifications = [item["classification"] for item in probes.values()]
    if "rpc-rejected" in classifications:
        classification = "rpc-rejected"
    elif "execution-failure" in classifications:
        classification = "execution-failure"
    elif "opcode-disagreement" in classifications:
        classification = "opcode-disagreement"
    else:
        classification = "match"
    return {
        "classification": classification,
        "probes": probes,
        "note": "Execution failures are retained separately from RPC rejection; both endpoint statuses and raw returns remain available per probe.",
    }


def markdown_summary(report: dict, output_root: pathlib.Path) -> str:
    def link(path: str) -> str:
        return os.path.relpath(ROOT / path, output_root).replace(os.sep, "/")

    primary = report["primary"]
    secondary = report["secondary"]
    comparison = report["comparison"]
    probes = "; ".join(f"`{name}`={item['classification']}" for name, item in comparison["probes"].items())
    return "\n".join(
        [
            "# Fork-opcode coverage follow-up (2026-10-18)",
            "",
            "This pass reran `PUSH0`, `TSTORE/TLOAD`, and `MCOPY` on Base's primary and registered independent secondary public endpoint. Raw responses, block context, and endpoint-level errors are retained.",
            "",
            "| Chain | Primary | Secondary | Blocks | Overall | Probe classifications | Raw evidence |",
            "| --- | --- | --- | --- | --- | --- | --- |",
            f"| base | [{primary['rpc']}]({link(primary['result'])}) | [{secondary['rpc']}]({link(secondary['result'])}) | {primary['block_number'] or '—'} / {secondary['block_number'] or '—'} | **{comparison['classification']}** | {probes} | [primary]({link(primary['raw_evidence_dir'])}) / [secondary]({link(secondary['raw_evidence_dir'])}) |",
            "",
            "`execution-failure` means the RPC accepted the call but the VM returned an execution error; `rpc-rejected` means the endpoint rejected the request before VM execution. The catalog label remains unchanged.",
            "",
        ]
    )


def run(date: str, output_name: str) -> dict:
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    config = registry[CHAIN]
    primary_entries = [entry for entry in config.get("rpcs", []) if entry.get("role") != "secondary"]
    secondary_entries = [entry for entry in config.get("rpcs", []) if entry.get("role") == "secondary"]
    if not primary_entries or not secondary_entries:
        raise ValueError("base: primary and secondary endpoints are required")

    output_root = ROOT / "results" / date / output_name
    report = {
        "schema": 1,
        "date": date,
        "chain": CHAIN,
        "probe_set": list(PROBES),
        "purpose": "independent endpoint follow-up for fork-gated opcodes; catalog labels are not changed automatically",
    }
    endpoint_results = {}
    observed_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    for role, rpc_entry in (("primary", primary_entries[0]), ("secondary", secondary_entries[0])):
        result = run_endpoint(CHAIN, config, rpc_entry, output_root / role, observed_at, list(PROBES))
        result_path = output_root / role / f"{CHAIN}.json"
        write_json(result_path, result)
        endpoint_results[role] = endpoint_record(result, result_path)
    report["primary"] = endpoint_results["primary"]
    report["secondary"] = endpoint_results["secondary"]
    report["comparison"] = compare(endpoint_results["primary"], endpoint_results["secondary"])
    write_json(output_root / "COMPARISON.json", report)
    (output_root / "SUMMARY.md").write_text(markdown_summary(report, output_root), encoding="utf-8")
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=DEFAULT_DATE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    report = run(args.date, args.output)
    print(f"fork-opcode follow-up complete: {report['comparison']['classification']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Rerun the PREVRANDAO probe on primary and independent secondary RPCs.

This is a focused follow-up to the catalog's Ethereum/zkSync Era row.  It
keeps each endpoint's block and raw responses, compares only the observable
entropy semantics, and never edits catalog labels.
"""

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
DEFAULT_OUTPUT = "entropy-followup"
CHAINS = ("ethereum", "zksync-era")
PROBE = "prevrandao"


def observed_fields(result: dict) -> dict:
    """Return the fields needed to audit RPC and header semantics."""

    probe = result.get("probes", {}).get(PROBE, {})
    interpretation = probe.get("interpretation", {})
    return {
        "status": interpretation.get("status"),
        "error_class": interpretation.get("error_class"),
        "uint256": interpretation.get("uint256"),
        "header_value": interpretation.get("header_value"),
        "header_matches": interpretation.get("header_matches"),
        "raw_return": interpretation.get("raw_return"),
    }


def endpoint_record(result: dict, result_path: pathlib.Path) -> dict:
    """Keep endpoint metadata and a repository-relative result path."""

    return {
        "rpc": result.get("rpc"),
        "rpc_source": result.get("rpc_source"),
        "rpc_source_accessed": result.get("rpc_source_accessed"),
        "chain_id_expected": result.get("chain_id_expected"),
        "chain_id_observed": result.get("chain_id_observed"),
        "status": result.get("status"),
        "block_number": result.get("block_number"),
        "observed_at": result.get("observed_at"),
        "result": str(result_path.relative_to(ROOT)),
        "raw_evidence_dir": str((ROOT / result.get("evidence_dir", "")).relative_to(ROOT)),
        "prevrandao": observed_fields(result),
    }


def compare(primary: dict, secondary: dict) -> dict:
    """Classify endpoint observations without comparing moving values."""

    primary_values = primary["prevrandao"]
    secondary_values = secondary["prevrandao"]
    differences = []
    for field in ("status", "error_class", "uint256", "header_value", "header_matches"):
        if primary_values.get(field) != secondary_values.get(field):
            differences.append(
                {
                    "field": field,
                    "primary": primary_values.get(field),
                    "secondary": secondary_values.get(field),
                }
            )

    primary_status = primary_values.get("status")
    secondary_status = secondary_values.get("status")
    if "rpc-rejected" in {primary_status, secondary_status}:
        classification = "rpc-rejected"
    elif False in {primary_values.get("header_matches"), secondary_values.get("header_matches")}:
        classification = "header-disagreement"
    elif primary_values.get("header_matches") != secondary_values.get("header_matches"):
        classification = "header-disagreement"
    else:
        classification = "match"

    return {
        "classification": classification,
        "primary": primary_values,
        "secondary": secondary_values,
        "differences": differences,
        "moving_block_values_compared": False,
        "note": "uint256, header_value, and raw_return may differ because each endpoint was queried at its own latest block; header_matches is the compared semantic result.",
    }


def markdown_summary(report: dict) -> str:
    summary_root = ROOT / report["_output_root"]

    def link(path: str) -> str:
        return os.path.relpath(ROOT / path, summary_root).replace(os.sep, "/")

    lines = [
        "# PREVRANDAO entropy follow-up (2026-10-18)",
        "",
        "This focused pass reran the `PREVRANDAO` creation probe on the primary and independent secondary endpoint for Ethereum and zkSync Era. Each endpoint was queried at its own latest block. Raw requests and responses are retained below the linked result paths.",
        "",
        "| Chain | Primary | Secondary | Primary block | Secondary block | Primary VM status | Secondary VM status | Header semantics | Result evidence |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for chain, item in report["chains"].items():
        primary = item["primary"]
        secondary = item["secondary"]
        comparison = item["comparison"]
        primary_link = f"[{primary['rpc']}]({link(primary['result'])})"
        secondary_link = f"[{secondary['rpc']}]({link(secondary['result'])})"
        lines.append(
            f"| {chain} | {primary_link} | {secondary_link} | {primary['block_number'] or '—'} | {secondary['block_number'] or '—'} | {primary['prevrandao']['status']} | {secondary['prevrandao']['status']} | **{comparison['classification']}** | [{chain} raw evidence]({link(primary['raw_evidence_dir'])}) / [{chain} secondary raw evidence]({link(secondary['raw_evidence_dir'])}) |"
        )
        if comparison["differences"]:
            lines.append(
                f"| ↳ differences | — | — | — | — | — | — | `{json.dumps(comparison['differences'], sort_keys=True)}` | — |"
            )
    lines.extend(
        [
            "",
            "`match` means both endpoints reached the probe successfully and each opcode result matched its captured header. `rpc-rejected` records an endpoint-level rejection without treating it as an unsupported VM opcode. `header-disagreement` records a successful probe whose opcode result does not match the endpoint's captured header, or a disagreement between endpoints. Dynamic values are retained in `COMPARISON.json` but are not compared as drift signals across moving latest blocks.",
            "",
            "The catalog label is unchanged by this follow-up; review the raw evidence before making any claim upgrade.",
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
        "probe": PROBE,
        "purpose": "independent endpoint follow-up for PREVRANDAO; catalog labels are not changed automatically",
        "_output_root": str(output_root.relative_to(ROOT)),
        "chains": {},
    }

    for chain in chains:
        if chain not in CHAINS:
            raise ValueError(f"unsupported entropy follow-up chain: {chain}")
        config = registry[chain]
        primary_entries = [entry for entry in config.get("rpcs", []) if entry.get("role") != "secondary"]
        secondary_entries = [entry for entry in config.get("rpcs", []) if entry.get("role") == "secondary"]
        if not primary_entries:
            raise ValueError(f"{chain}: no primary endpoint in probes/chains.json")
        if not secondary_entries:
            raise ValueError(f"{chain}: no secondary endpoint in probes/chains.json")

        chain_dir = output_root / chain
        endpoint_results = {}
        observed_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        for role, rpc_entry in (("primary", primary_entries[0]), ("secondary", secondary_entries[0])):
            # Run endpoints sequentially so each endpoint's rate limit is
            # respected and the comparison remains easy to reproduce.
            result = run_endpoint(chain, config, rpc_entry, chain_dir / role, observed_at, [PROBE])
            result_path = chain_dir / role / f"{chain}.json"
            write_json(result_path, result)
            endpoint_results[role] = endpoint_record(result, result_path)

        report["chains"][chain] = {
            "primary": endpoint_results["primary"],
            "secondary": endpoint_results["secondary"],
            "comparison": compare(endpoint_results["primary"], endpoint_results["secondary"]),
        }

    write_json(output_root / "COMPARISON.json", {key: value for key, value in report.items() if key != "_output_root"})
    (output_root / "SUMMARY.md").write_text(markdown_summary(report), encoding="utf-8")
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
        f"entropy follow-up complete: {len(report['chains'])} chains, "
        + ", ".join(f"{key}={counts[key]}" for key in sorted(counts))
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

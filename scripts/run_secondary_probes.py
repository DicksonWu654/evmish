#!/usr/bin/env python3
"""Run selected headline probes on the registry's secondary endpoints.

The primary matrix is never overwritten. Each endpoint response is written
under results/<date>/secondary/<chain>/ and compared only on stable probe
semantics; moving block values remain observations rather than drift errors.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "probes"))

from run_creation_probes import endpoint_slug, run_endpoint, write_json  # noqa: E402


REGISTRY = ROOT / "probes" / "chains.json"
DEFAULT_DATE = "2026-10-18"
DEFAULT_OUTPUT = "secondary"
HEADLINE_PROBES = {
    "ethereum": [
        "blobbasefee",
        "number",
        "cold-warm-extcodesize",
        "extcode-delegated-7702",
        "precompile-0x03-ripemd160",
    ],
    "arbitrum-one": ["blobbasefee", "number"],
    "op-mainnet": ["blobbasefee", "number"],
    "base": ["blobbasefee"],
    "monad": ["cold-warm-extcodesize"],
    "megaeth": ["extcode-delegated-7702"],
    "zksync-era": ["extcode-delegated-7702", "precompile-0x03-ripemd160"],
}
STABLE_FIELDS = (
    "status",
    "error_class",
    "formula_matches",
    "header_matches",
    "matches_expected_zero",
    "expected_zero_by_evm_depth_rule",
    "precompile_call_status",
    "precompile_output_hex",
    "extcodesize",
    "extcodehash",
    "gas_delta",
    "warm_gas_delta",
)


def stable(entry: dict | None) -> dict:
    if not entry:
        return {}
    interpretation = entry.get("interpretation", {})
    return {key: interpretation[key] for key in STABLE_FIELDS if key in interpretation}


def compare_probe(primary: dict | None, secondary: dict | None, chain_id_match: bool) -> dict:
    primary_values = stable(primary)
    secondary_values = stable(secondary)
    differences = []
    for key in sorted(set(primary_values) | set(secondary_values)):
        if primary_values.get(key) != secondary_values.get(key):
            differences.append(
                {
                    "field": key,
                    "primary": primary_values.get(key),
                    "secondary": secondary_values.get(key),
                }
            )
    return {
        "status": (
            "uncomparable-chain-id"
            if not chain_id_match
            else "match"
            if not differences
            else "disagreement"
        ),
        "primary": primary_values,
        "secondary": secondary_values,
        "differences": differences,
    }


def markdown_summary(report: dict) -> str:
    lines = [
        "# Secondary endpoint probe comparison (2026-10-18)",
        "",
        "This pass used the secondary registry endpoint for each headline chain. Raw requests and responses are under the linked secondary result path. `match` compares stable probe semantics only; block values and raw dynamic returns are deliberately not compared.",
        "",
        "| Chain | Chain IDs | Primary RPC | Secondary RPC | Probes | Matches | Disagreements | Uncomparable | Primary evidence | Secondary evidence |",
        "| --- | --- | --- | --- | ---: | ---: | ---: | ---: | --- | --- |",
    ]
    for chain, item in report["chains"].items():
        comparisons = item["probes"]
        matches = sum(c["status"] == "match" for c in comparisons.values())
        disagreements = sum(c["status"] == "disagreement" for c in comparisons.values())
        uncomparable = sum(c["status"] == "uncomparable-chain-id" for c in comparisons.values())
        primary = item["primary_result"]
        secondary = item["secondary_result"]
        primary_link = f"../{primary.removeprefix('results/2026-10-18/')}"
        secondary_link = f"{chain}/{chain}.json"
        lines.append(
            f"| {chain} | {item['primary_chain_id'] or '—'} / {item['secondary_chain_id'] or '—'} | {item['primary_rpc'] or '—'} | {item['secondary_rpc'] or '—'} | {len(comparisons)} | {matches} | {disagreements} | {uncomparable} | [{primary}]({primary_link}) | [{secondary}]({secondary_link}) |"
        )
        for probe, comparison in comparisons.items():
            if comparison["status"] == "disagreement":
                lines.append(
                    f"| ↳ `{probe}` | disagreement | — | — | — | — | `{json.dumps(comparison['differences'], sort_keys=True)}` | — |"
                )
    lines.extend(
        [
            "",
            "A disagreement is retained as evidence and does not change a catalog label. Investigate the raw RPC responses and rerun a surprising result on another independent endpoint before publishing a claim.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=DEFAULT_DATE)
    parser.add_argument("--chains", default=",".join(HEADLINE_PROBES))
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    chains = [name.strip() for name in args.chains.split(",") if name.strip()]
    unknown = sorted(set(chains) - set(HEADLINE_PROBES))
    if unknown:
        parser.error(f"unknown headline chain(s): {', '.join(unknown)}")

    date_root = ROOT / "results" / args.date
    output_root = date_root / DEFAULT_OUTPUT
    report = {
        "schema": 1,
        "date": args.date,
        "purpose": "independent secondary endpoint check; no catalog labels are upgraded",
        "chains": {},
    }
    for chain in chains:
        config = registry[chain]
        secondary_entries = [entry for entry in config.get("rpcs", []) if entry.get("role") == "secondary"]
        if not secondary_entries:
            raise SystemExit(f"{chain}: no secondary endpoint in probes/chains.json")
        secondary_entry = secondary_entries[0]
        primary_path = date_root / chain / f"{chain}.json"
        if not primary_path.exists():
            raise SystemExit(f"{chain}: primary result missing at {primary_path}")
        primary = json.loads(primary_path.read_text(encoding="utf-8"))
        selected = HEADLINE_PROBES[chain]
        observed_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        chain_dir = output_root / chain
        secondary = run_endpoint(chain, config, secondary_entry, chain_dir, observed_at, selected)
        secondary_path = chain_dir / f"{chain}.json"
        write_json(secondary_path, secondary)
        report["chains"][chain] = {
            "primary_rpc": primary.get("rpc"),
            "secondary_rpc": secondary.get("rpc"),
            "primary_chain_id": primary.get("chain_id_observed"),
            "secondary_chain_id": secondary.get("chain_id_observed"),
            "chain_id_match": primary.get("chain_id_observed") == secondary.get("chain_id_observed"),
            "primary_status": primary.get("status"),
            "secondary_status": secondary.get("status"),
            "primary_result": str(primary_path.relative_to(ROOT)),
            "secondary_result": str(secondary_path.relative_to(ROOT)),
            "secondary_raw_evidence_dir": secondary.get("evidence_dir"),
            "probes": {
                probe: compare_probe(
                    primary.get("probes", {}).get(probe),
                    secondary.get("probes", {}).get(probe),
                    primary.get("chain_id_observed") == secondary.get("chain_id_observed"),
                )
                for probe in selected
            },
        }

    write_json(output_root / "COMPARISON.json", report)
    (output_root / "SUMMARY.md").write_text(markdown_summary(report), encoding="utf-8")
    disagreements = sum(
        comparison["status"] == "disagreement"
        for item in report["chains"].values()
        for comparison in item["probes"].values()
    )
    print(f"wrote secondary evidence for {len(report['chains'])} chains; stable disagreements={disagreements}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

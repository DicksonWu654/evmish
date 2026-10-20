#!/usr/bin/env python3
"""Run the follow-up focused creation and code-size probes."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "probes"))

from run_creation_probes import oversized_create_probe, run_endpoint, write_json  # noqa: E402


REGISTRY = ROOT / "probes" / "chains.json"
DEFAULT_DATE = "2026-10-18"
DEFAULT_OUTPUT = "followup/headline-probes"
FORMULA_CHAINS = ("ethereum", "zksync-era", "arbitrum-one", "tron")
CODE_SIZE_CHAINS = ("ethereum", "monad")
FORMULA_PROBES = ("create", "create2")
CODE_SIZE_PROBES = ("oversized-runtime-create-24576", "oversized-runtime-create-24577")
MONAD_LIMIT_PROBE = "oversized-runtime-create-131072"
MONAD_ABOVE_LIMIT_PROBE = "oversized-runtime-create-131073"


def extra_specs(sizes: tuple[int, ...]) -> dict[str, dict]:
    specs = {}
    for size in sizes:
        name = f"oversized-runtime-create-{size}"
        specs[name] = {
            "data": "0x" + oversized_create_probe(size).hex(),
            "meaning": f"CREATE attempts a {size}-byte runtime; zero means the size limit rejected it.",
            "decode": "uint256",
            "vector": f"runtime_bytes={size}",
            "gas": "0x989680",
        }
    return specs


def fields(result: dict, name: str) -> dict:
    interpretation = result.get("probes", {}).get(name, {}).get("interpretation", {})
    return {
        "status": interpretation.get("status"),
        "error_class": interpretation.get("error_class"),
        "uint256": interpretation.get("uint256"),
        "raw_return": interpretation.get("raw_return"),
        "formula_matches": interpretation.get("formula_matches"),
        "size_rejected": interpretation.get("uint256") == 0 if interpretation.get("status") == "ok" else None,
    }


def run_endpoint_group(registry: dict, group: str, chain: str, role: str, entry: dict, output_root: pathlib.Path, names: list[str], extras: dict[str, dict], observed_at: str) -> dict:
    config = registry[chain]
    result = run_endpoint(chain, config, entry, output_root / group / chain / role, observed_at, names, extras)
    result_path = output_root / group / chain / role / f"{chain}.json"
    write_json(result_path, result)
    return {
        "rpc": result.get("rpc"),
        "status": result.get("status"),
        "chain_id_observed": result.get("chain_id_observed"),
        "block_number": result.get("block_number"),
        "observed_at": result.get("observed_at"),
        "result": str(result_path.relative_to(ROOT)),
        "raw_evidence_dir": result.get("evidence_dir"),
        "probes": {name: fields(result, name) for name in names},
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=DEFAULT_DATE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    output_root = ROOT / "results" / args.date / args.output
    report = {
        "schema": 1,
        "date": args.date,
        "purpose": "follow-up focused CREATE/CREATE2 and code-size probes; RPC/VM failures remain distinct",
        "formula_chains": {},
        "code_size_chains": {},
        "recorded_reasons": {},
    }
    observed_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

    for chain in FORMULA_CHAINS:
        config = registry[chain]
        primary = next((entry for entry in config.get("rpcs", []) if entry.get("role") != "secondary"), None)
        secondary = next((entry for entry in config.get("rpcs", []) if entry.get("role") == "secondary"), None)
        if not primary:
            report["recorded_reasons"][f"{chain}/formula"] = "No primary endpoint was registered."
            continue
        extras = {}
        primary_record = run_endpoint_group(registry, "formula", chain, "primary", primary, output_root, list(FORMULA_PROBES), extras, observed_at)
        record = {"primary": primary_record}
        if secondary:
            record["secondary"] = run_endpoint_group(registry, "formula", chain, "secondary", secondary, output_root, list(FORMULA_PROBES), extras, observed_at)
        else:
            record["secondary"] = None
            record["secondary_reason"] = "No independent endpoint is registered; the primary RPC result and its raw rejection are retained."
        report["formula_chains"][chain] = record

    for chain in CODE_SIZE_CHAINS:
        config = registry[chain]
        primary = next((entry for entry in config.get("rpcs", []) if entry.get("role") != "secondary"), None)
        if not primary:
            report["recorded_reasons"][f"{chain}/code-size"] = "No primary endpoint was registered."
            continue
        sizes = CODE_SIZE_PROBES + ((MONAD_LIMIT_PROBE, MONAD_ABOVE_LIMIT_PROBE) if chain == "monad" else ())
        size_values = tuple(int(name.rsplit("-", 1)[1]) for name in sizes)
        extras = extra_specs(size_values)
        names = list(sizes)
        primary_record = run_endpoint_group(registry, "code-size", chain, "primary", primary, output_root, names, extras, observed_at)
        report["code_size_chains"][chain] = {"primary": primary_record}

    write_json(output_root / "REPORT.json", report)
    lines = [
        "# follow-up focused creation and code-size probes (2026-10-18)",
        "",
        "The report covers CREATE/CREATE2 formula checks on Ethereum, zkSync Era, Arbitrum One, and TRON; 24,576/24,577-byte boundaries on Ethereum and Monad; and 128 KiB candidates on Monad. Every endpoint result retains the block tag and raw request/response evidence.",
        "",
        "`rpc-rejected` means the endpoint rejected the read before VM execution. `execution-failure` means the RPC accepted the creation call and the VM returned an execution error. A nonzero CREATE return is recorded as a successful child address, not as proof of an exact maximum code limit.",
        "",
        "Machine-readable evidence: `REPORT.json`.",
        "",
    ]
    (output_root / "SUMMARY.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"followup headline probes complete: {len(report['formula_chains'])} formula chains, {len(report['code_size_chains'])} code-size chains")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

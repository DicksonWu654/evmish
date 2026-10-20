#!/usr/bin/env python3
"""Build a compact, stable probe baseline for CI drift checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_RESULTS = ROOT / "results" / "2026-10-18"
DEFAULT_OUTPUT = DEFAULT_RESULTS / "CI_BASELINE.json"

# These fields describe capability or known-answer behavior. Moving block
# values (NUMBER, TIMESTAMP, BASEFEE, PREVRANDAO, and raw returns) are omitted.
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


def stable_interpretation(entry: dict) -> dict:
    interpretation = entry.get("interpretation", {})
    return {key: interpretation[key] for key in STABLE_FIELDS if key in interpretation}


def load_chain(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def build(results_dir: Path) -> dict:
    chains = {}
    for path in sorted(results_dir.glob("*/**/*.json")):
        if path.name in {"SUMMARY.json", "KNOWN_ANSWERS.json", "CI_BASELINE.json"}:
            continue
        if path.parent.parent != results_dir or path.stem != path.parent.name:
            continue
        result = load_chain(path)
        name = result.get("chain")
        if not name:
            continue
        chains[name] = {
            "chain_id_expected": result.get("chain_id_expected"),
            "chain_id_observed": result.get("chain_id_observed"),
            "status": result.get("status"),
            "probe_count": result.get("probe_count", 0),
            "probes": {
                probe: stable_interpretation(entry)
                for probe, entry in sorted(result.get("probes", {}).items())
            },
        }
    if not chains:
        raise SystemExit(f"no chain result files found below {results_dir}")
    return {
        "schema": 1,
        "source_results": str(results_dir.relative_to(ROOT)),
        "stable_fields": list(STABLE_FIELDS),
        "chains": chains,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--results", type=Path, default=DEFAULT_RESULTS)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    results_dir = args.results if args.results.is_absolute() else ROOT / args.results
    output = args.output if args.output.is_absolute() else ROOT / args.output
    payload = build(results_dir)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(payload['chains'])} chain baselines to {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

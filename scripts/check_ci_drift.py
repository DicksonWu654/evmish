#!/usr/bin/env python3
"""Compare a selected probe run with the committed stable baseline."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BASELINE = ROOT / "results" / "2026-10-18" / "CI_BASELINE.json"


def parse_chains(value: str, available: set[str]) -> list[str]:
    names = [name.strip() for name in value.split(",") if name.strip()]
    if not names:
        raise ValueError("chain list is empty")
    unknown = sorted(set(names) - available)
    if unknown:
        raise ValueError(f"chain(s) missing from baseline: {', '.join(unknown)}")
    return list(dict.fromkeys(names))


def stable_interpretation(entry: dict, fields: list[str]) -> dict:
    interpretation = entry.get("interpretation", {})
    return {key: interpretation[key] for key in fields if key in interpretation}


def compare_chain(name: str, baseline: dict, result: dict, fields: list[str]) -> list[str]:
    differences: list[str] = []
    for key in ("chain_id_expected", "chain_id_observed", "status", "probe_count"):
        if result.get(key) != baseline.get(key):
            differences.append(f"{name}.{key}: baseline={baseline.get(key)!r} current={result.get(key)!r}")
    baseline_probes = baseline.get("probes", {})
    current_probes = result.get("probes", {})
    missing = sorted(set(baseline_probes) - set(current_probes))
    extra = sorted(set(current_probes) - set(baseline_probes))
    if missing:
        differences.append(f"{name}.probes missing: {', '.join(missing)}")
    if extra:
        differences.append(f"{name}.probes extra: {', '.join(extra)}")
    for probe in sorted(set(baseline_probes) & set(current_probes)):
        expected = baseline_probes[probe]
        actual = stable_interpretation(current_probes[probe], fields)
        if actual != expected:
            differences.append(f"{name}.{probe}: baseline={expected!r} current={actual!r}")
    return differences


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--baseline", type=Path, default=DEFAULT_BASELINE)
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--chains", required=True, help="comma-separated registry names")
    args = parser.parse_args()
    baseline_path = args.baseline if args.baseline.is_absolute() else ROOT / args.baseline
    results_dir = args.results if args.results.is_absolute() else ROOT / args.results
    baseline = json.loads(baseline_path.read_text(encoding="utf-8"))
    fields = baseline.get("stable_fields", [])
    try:
        chains = parse_chains(args.chains, set(baseline.get("chains", {})))
    except ValueError as exc:
        parser.error(str(exc))

    differences: list[str] = []
    for name in chains:
        result_path = results_dir / name / f"{name}.json"
        if not result_path.exists():
            differences.append(f"{name}: missing result file {result_path}")
            continue
        result = json.loads(result_path.read_text(encoding="utf-8"))
        differences.extend(compare_chain(name, baseline["chains"][name], result, fields))

    if differences:
        print("probe drift detected:")
        print("\n".join(f"- {difference}" for difference in differences))
        return 1
    print(f"probe drift check passed for {len(chains)} chain(s)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

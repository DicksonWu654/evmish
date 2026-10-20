#!/usr/bin/env python3
"""Reconfirm every non-rejected primary probe difference at a later block."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "probes"))

from differential_common import DATE, RESULTS, chain_names, confirmation_candidates, load_result  # noqa: E402
from run_creation_probes import run_endpoint, write_json  # noqa: E402


REGISTRY = ROOT / "probes" / "chains.json"
DEFAULT_OUTPUT = "differential-confirmation"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=DATE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    results_root = ROOT / "results" / args.date
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    candidates = confirmation_candidates(results_root)
    output_root = results_root / args.output
    request = {
        "schema": 1,
        "date": args.date,
        "purpose": "later-block confirmation of differential probe cells; rejected and unavailable cells are not catalog divergences",
        "chains": candidates,
    }
    write_json(output_root / "REQUEST.json", request)
    report = {"schema": 1, "date": args.date, "purpose": request["purpose"], "chains": {}}
    for chain in chain_names(results_root):
        names = candidates.get(chain, [])
        if not names:
            continue
        config = registry[chain]
        primary_entries = [entry for entry in config.get("rpcs", []) if entry.get("role") != "secondary"]
        if not primary_entries:
            report["chains"][chain] = {"status": "no-primary-endpoint", "probes": names}
            continue
        observed_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        chain_dir = output_root / chain
        try:
            result = run_endpoint(chain, config, primary_entries[0], chain_dir, observed_at, names)
            result_path = chain_dir / f"{chain}.json"
            write_json(result_path, result)
            report["chains"][chain] = {
                "status": result.get("status"),
                "rpc": result.get("rpc"),
                "block_number": result.get("block_number"),
                "observed_at": result.get("observed_at"),
                "probes": names,
                "result": str(result_path.relative_to(ROOT)),
                "raw_evidence_dir": result.get("evidence_dir"),
            }
        except Exception as exc:
            report["chains"][chain] = {
                "status": "runner-error",
                "probes": names,
                "error": f"{type(exc).__name__}: {exc}",
            }
    write_json(output_root / "REPORT.json", report)
    print(f"differential confirmation complete: {len(candidates)} chains, {sum(len(v) for v in candidates.values())} probe cells")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

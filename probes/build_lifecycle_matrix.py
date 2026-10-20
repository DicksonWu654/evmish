#!/usr/bin/env python3
"""Build E31 chain-by-case matrix from saved read-only lifecycle evidence."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path

from keccak import keccak256
from run_creation_probes import rlp_list
from run_gas_schedule import REGISTRY, ROOT
from run_lifecycle_sweep import CASES


def load(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


def cell(run: dict | None, name: str) -> dict | None:
    return run.get("cases", {}).get(name) if run else None


def expected_nonce2(creator: int) -> int:
    return int.from_bytes(keccak256(rlp_list([creator.to_bytes(20, "big"), 2]))[-20:], "big")


def semantic(name: str, entry: dict | None) -> dict | None:
    if entry is None:
        return None
    result = entry["interpretation"]
    status = result["status"]
    if name.startswith("runtime-"):
        measured = result.get("words") if status == "observed" else None
        high_attempts = entry.get("higher_gas_attempts", [])
        for attempt in high_attempts:
            high = attempt["interpretation"]
            if high["status"] == "observed" and high["words"]["child"] != 0:
                measured = high["words"]
                break
        if measured is None or (measured["child"] == 0 and high_attempts):
            return {"status": "resource-inconclusive" if high_attempts else status}
        return {"status": "observed", "created": measured["child"] != 0,
                "code_size": measured["code_size"]}
    if status != "observed":
        return {"status": status}
    w = result["words"]
    if name.startswith("init-"):
        value = {"status": status, "created": w["child"] != 0,
                 "code_size": w["code_size"]}
        if w["child"] != 0:
            value["create_gas"] = w["create_gas"]
        return value
    if name == "returndata-revert":
        return {"status": status, "child_created": w["child"] != 0,
                **{key: w[key] for key in ("return_status", "return_length", "return_marker",
                                          "revert_status", "revert_length", "revert_marker")}}
    if name == "failed-create-nonce":
        return {"status": status, "failed_child_zero": w["failed_child"] == 0,
                "next_child_nonce2": w["next_child"] == expected_nonce2(w["creator"]),
                "next_child_nonzero": w["next_child"] != 0}
    if name.startswith("selfdestruct-"):
        return {"status": status, "child_created": w["child"] != 0,
                "code_before": w["code_before"], "code_after": w["code_after"],
                "hash_unchanged": w["hash_before"] == w["hash_after"],
                "balance_before": w["balance_before"], "balance_after": w["balance_after"],
                "beneficiary_delta": w["beneficiary_after"] - w["beneficiary_before"],
                "kill_status": w["kill_status"]}
    if name == "precompile-value":
        return {"status": status, "call_status": w["call_status"],
                "output_length": w["output_length"], "first_byte": w["first_byte"],
                "precompile_balance_delta": w["precompile_balance_after"] - w["precompile_balance_before"],
                "caller_value_spent": w["caller_value_spent"]}
    if name.startswith("depth-"):
        # Maximum reported depth below the target reflects EIP-150 gas decay
        # and endpoint allowance, not a demonstrated chain depth limit.
        return {"status": status, "call_status": w["call_status"],
                "reached_target": w["reached_target"]}
    raise ValueError(name)


def compare(primary: dict | None, other: dict | None, phase_status: str) -> str:
    if phase_status == "no-secondary-rpc":
        return "no-listed-endpoint"
    if phase_status != "ok" or other is None:
        return phase_status if phase_status != "ok" else "missing"
    left, right = primary or {}, other
    if left.get("status") == right.get("status") == "resource-inconclusive":
        return "same-resource-bound"
    if left.get("status") != "observed" or right.get("status") != "observed":
        return "same-error-class" if left.get("status") == right.get("status") else "endpoint-or-execution-error"
    return "same" if left == right else "different"


def block_time(run: dict) -> str:
    block = run.get("block")
    value = block.get("timestamp") if isinstance(block, dict) else None
    try:
        return dt.datetime.fromtimestamp(int(value, 16), dt.timezone.utc).isoformat()
    except (ValueError, TypeError, OverflowError):
        return ""


def high_gas_summary(entry: dict) -> list[dict]:
    result = []
    for attempt in entry.get("higher_gas_attempts", []):
        interpretation = attempt["interpretation"]
        result.append({"gas_limit": attempt["gas_limit"], "status": interpretation["status"],
                       "code_size": interpretation.get("words", {}).get("code_size"),
                       "create_gas": interpretation.get("words", {}).get("create_gas")})
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    args = parser.parse_args()
    root = ROOT / "results" / args.date / "lifecycle"
    base = load(root / "initial/ethereum.json")
    if not base or base.get("status") != "ok":
        parser.error("Ethereum initial lifecycle evidence is required")
    fields = ("chain", "case", "block", "block_timestamp_utc", "rpc", "status",
              "outcome", "observed_words", "ethereum_outcome", "versus_ethereum",
              "later_block", "second_endpoint", "higher_gas_attempts",
              "initial_evidence", "case_pointer", "later_evidence", "second_endpoint_evidence")
    rows = []
    for name in REGISTRY:
        first = load(root / "initial" / f"{name}.json")
        later = load(root / "confirm" / f"{name}.json")
        second = load(root / "secondary" / f"{name}.json")
        if not first or first.get("status") != "ok":
            continue
        later_status = later.get("status", "missing") if later else "missing"
        second_status = second.get("status", "missing") if second else "missing"
        if later_status == "ok" and int(later["block"]["number"], 16) <= int(first["block"]["number"], 16):
            later_status = "not-later-block"
        for case_name in CASES:
            entry = cell(first, case_name)
            if not entry:
                raise ValueError(f"missing {name}/{case_name}")
            outcome = semantic(case_name, entry)
            baseline = semantic(case_name, cell(base, case_name))
            if outcome["status"] == "resource-inconclusive":
                comparison = "uncomparable-resource"
            elif outcome["status"] == "observed" and baseline["status"] != "observed":
                comparison = "observed-vs-baseline-error"
            elif outcome["status"] != "observed" and baseline["status"] == "observed":
                comparison = "target-error-vs-baseline-observed"
            elif outcome["status"] != "observed" or baseline["status"] != "observed":
                comparison = "uncomparable-error" if outcome != baseline else "same-error-class"
            else:
                comparison = "same" if outcome == baseline else "different"
            rows.append({
                "chain": name, "case": case_name, "block": first["block"].get("number"),
                "block_timestamp_utc": block_time(first), "rpc": first["rpc"]["url"],
                "status": outcome["status"], "outcome": json.dumps(outcome, sort_keys=True),
                "observed_words": json.dumps(entry["interpretation"].get("words"), sort_keys=True),
                "ethereum_outcome": json.dumps(baseline, sort_keys=True),
                "versus_ethereum": comparison,
                "later_block": compare(outcome, semantic(case_name, cell(later, case_name)), later_status),
                "second_endpoint": compare(outcome, semantic(case_name, cell(second, case_name)), second_status),
                "higher_gas_attempts": json.dumps(high_gas_summary(entry), sort_keys=True),
                "initial_evidence": f"initial/{name}.json", "case_pointer": f"/cases/{case_name}",
                "later_evidence": f"confirm/{name}.json" if later else "",
                "second_endpoint_evidence": f"secondary/{name}.json" if second else "",
            })
    with (root / "MATRIX.csv").open("w", newline="") as stream:
        writer = csv.DictWriter(stream, fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(f"wrote {len(rows)} rows to {root / 'MATRIX.csv'}")


if __name__ == "__main__":
    main()

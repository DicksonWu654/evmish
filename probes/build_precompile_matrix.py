#!/usr/bin/env python3
"""Build the precompile matrix from saved, attributable read-only RPC calls."""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
from pathlib import Path

from run_gas_schedule import REGISTRY, ROOT


def load(path: Path) -> dict | None:
    return json.loads(path.read_text()) if path.exists() else None


def cell(run: dict | None, key: str) -> dict | None:
    return run.get("cases", {}).get(key) if run else None


def comparable(value: dict | None) -> tuple | None:
    if value is None:
        return None
    interpretation = value["interpretation"]
    return tuple(interpretation.get(k) for k in (
        "status", "output", "first_call_gas", "second_call_gas"))


def compare(primary: dict | None, other: dict | None, status: str) -> str:
    if status == "no-secondary-rpc":
        return "no-listed-endpoint"
    if status != "ok" or other is None:
        return status if status != "ok" else "missing"
    error_classes = {"transport-error", "rpc-rejected", "execution-failure"}
    if (primary is None or primary["interpretation"]["status"] in error_classes or
            other["interpretation"]["status"] in error_classes):
        if comparable(primary) != comparable(other):
            return "endpoint-error"
    return "same" if comparable(primary) == comparable(other) else "different"


def timestamp(run: dict) -> str:
    block = run.get("block")
    value = block.get("timestamp") if isinstance(block, dict) else None
    try:
        return dt.datetime.fromtimestamp(int(value, 16), dt.timezone.utc).isoformat()
    except (TypeError, ValueError, OverflowError):
        return ""


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=dt.datetime.now(dt.timezone.utc).date().isoformat())
    args = parser.parse_args()
    root = ROOT / "results" / args.date / "precompile-sweep"
    vectors = json.loads((ROOT / "probes/precompile_vectors.json").read_text())["vectors"]
    base = load(root / "initial/ethereum.json")
    if not base or base.get("status") != "ok":
        parser.error("Ethereum initial evidence must exist")
    fields = ["chain", "address", "name", "block", "block_timestamp_utc", "rpc",
              "valid_status", "valid_output", "valid_expected", "first_call_gas",
              "second_call_gas", "ethereum_first_gas", "first_gas_delta",
              "ethereum_second_gas", "second_gas_delta", "gas_scope",
              "malformed_status", "malformed_output", "malformed_first_gas",
              "malformed_second_gas", "valid_later", "malformed_later",
              "valid_second_endpoint", "malformed_second_endpoint", "valid_source",
              "malformed_source", "initial_evidence", "valid_pointer", "malformed_pointer",
              "later_evidence", "second_endpoint_evidence"]
    rows = []
    for name in REGISTRY:
        first = load(root / "initial" / f"{name}.json")
        later = load(root / "confirm" / f"{name}.json")
        second = load(root / "secondary" / f"{name}.json")
        if first is None:
            continue  # A --chains subset has a deliberately partial matrix.
        if first.get("status") != "ok":
            continue
        later_status = later.get("status", "missing") if later else "missing"
        second_status = second.get("status", "missing") if second else "missing"
        if later_status == "ok" and int(later["block"]["number"], 16) <= int(first["block"]["number"], 16):
            later_status = "not-later-block"
        for address, vector in vectors.items():
            vk, mk = address + ".valid", address + ".malformed"
            valid, malformed = cell(first, vk), cell(first, mk)
            if not valid or not malformed:
                raise ValueError(f"missing {name} {address} vector pair")
            interpretation, control = valid["interpretation"], cell(base, vk)["interpretation"]
            malformed_i = malformed["interpretation"]
            gas1, gas2 = interpretation.get("first_call_gas"), interpretation.get("second_call_gas")
            base1, base2 = control.get("first_call_gas"), control.get("second_call_gas")
            scope = ("observed-price" if interpretation["status"] == "match" else
                     "bounded-failure-not-price" if interpretation["status"] == "call-failed" else
                     "empty-account-or-other" if interpretation["status"] == "empty-success" else
                     "not-priced")
            rows.append({
                "chain": name, "address": address, "name": vector["name"],
                "block": first["block"].get("number"), "block_timestamp_utc": timestamp(first),
                "rpc": first["rpc"]["url"],
                "valid_status": interpretation["status"], "valid_output": interpretation.get("output"),
                "valid_expected": vector["valid"]["expected"],
                "first_call_gas": gas1, "second_call_gas": gas2,
                "ethereum_first_gas": base1, "first_gas_delta": gas1 - base1 if gas1 is not None and base1 is not None else None,
                "ethereum_second_gas": base2, "second_gas_delta": gas2 - base2 if gas2 is not None and base2 is not None else None,
                "gas_scope": scope,
                "malformed_status": malformed_i["status"], "malformed_output": malformed_i.get("output"),
                "malformed_first_gas": malformed_i.get("first_call_gas"),
                "malformed_second_gas": malformed_i.get("second_call_gas"),
                "valid_later": compare(valid, cell(later, vk), later_status),
                "malformed_later": compare(malformed, cell(later, mk), later_status),
                "valid_second_endpoint": compare(valid, cell(second, vk), second_status),
                "malformed_second_endpoint": compare(malformed, cell(second, mk), second_status),
                "valid_source": vector["valid"]["source"],
                "malformed_source": vector["malformed"]["source"],
                "initial_evidence": f"initial/{name}.json", "valid_pointer": f"/cases/{vk}",
                "malformed_pointer": f"/cases/{mk}",
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

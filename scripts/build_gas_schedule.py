#!/usr/bin/env python3
"""Build the E29 chain-by-case matrix from the saved raw RPC records."""

from __future__ import annotations

import argparse
import csv
import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "probes"))
from run_gas_schedule import REGISTRY, build_cases, decode  # noqa: E402


def read(path: pathlib.Path) -> dict:
    return json.loads(path.read_text()) if path.exists() else {}


def raw_interpretation(item: dict, case) -> dict:
    raw = item.get("raw")
    return decode(case, raw["response"]) if isinstance(raw, dict) else {}


def block_number(value: dict) -> int | None:
    block = value.get("block")
    word = block.get("number") if isinstance(block, dict) else None
    return int(word, 16) if isinstance(word, str) else None


def case_cell(data: dict, case_name: str, case) -> dict:
    return raw_interpretation(data.get("cases", {}).get(case_name, {}), case)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default="2026-10-20")
    args = parser.parse_args()
    root = ROOT / "results" / args.date / "gas-schedule"
    cases = build_cases()
    initial = {name: read(root / "initial" / f"{name}.json") for name in REGISTRY}
    confirm = {name: read(root / "confirm" / f"{name}.json") for name in REGISTRY}
    secondary = {name: read(root / "secondary" / f"{name}.json") for name in REGISTRY}
    value_initial = {name: read(root / "value-call/initial" / f"{name}.json") for name in REGISTRY}
    value_confirm = {name: read(root / "value-call/confirm" / f"{name}.json") for name in REGISTRY}
    value_secondary = {name: read(root / "value-call/secondary" / f"{name}.json") for name in REGISTRY}
    baseline = initial["ethereum"]
    if len(baseline.get("cases", {})) != len(cases):
        parser.error("complete Ethereum baseline required")
    rows = []
    for name in REGISTRY:
        data, later, other = initial[name], confirm[name], secondary[name]
        for case_name, case in cases.items():
            base = case_cell(baseline, case_name, case)
            got = case_cell(data, case_name, case)
            checked = case_cell(later, case_name, case)
            second = case_cell(other, case_name, case)
            for label, _ in case.targets:
                eth = base.get("values", {}).get(label)
                value = got.get("values", {}).get(label)
                confirmed_value = checked.get("values", {}).get(label)
                secondary_value = second.get("values", {}).get(label)
                later_block = block_number(later)
                initial_block = block_number(data)
                later_ok = (confirmed_value == value and later_block is not None and
                            initial_block is not None and later_block > initial_block)
                second_ok = secondary_value == value and other.get("status") == "ok"
                if case_name == "call-value-empty":
                    status = "unfunded-control-only"
                elif eth is None:
                    status = "no-ethereum-baseline"
                elif value is None:
                    status = got.get("status", data.get("status", "missing"))
                elif name == "ethereum":
                    status = "ethereum-baseline"
                elif value == eth:
                    status = "same-as-ethereum"
                elif later_ok and second_ok:
                    status = "confirmed-two-endpoints"
                elif later_ok:
                    status = "confirmed-later-block"
                else:
                    status = "unconfirmed-difference"
                item = data.get("cases", {}).get(case_name, {})
                rows.append({
                    "chain": name, "case": case_name, "family": case.family,
                    "phase": label, "ethereum_gas": eth, "chain_gas": value,
                    "delta_gas": value - eth if isinstance(value, int) and isinstance(eth, int) else None,
                    "status": status, "initial_block": initial_block,
                    "confirmation_block": later_block if confirmed_value is not None else None,
                    "confirmation_gas": confirmed_value, "secondary_gas": secondary_value,
                    "context_tag": item.get("block_tag"),
                    "raw_file": f"initial/{name}.json", "raw_pointer": f"/cases/{case_name}/raw",
                    "confirmation_file": f"confirm/{name}.json" if confirmed_value is not None else "",
                    "secondary_file": f"secondary/{name}.json" if secondary_value is not None else "",
                    "note": case.detail,
                })

        # The standard sweep has no value in its creation context, so its
        # CALL-value row is explicitly unqualified. This separately funded
        # read-only simulation proves that the CALL actually succeeded.
        base_funded = value_initial["ethereum"]
        eth = base_funded.get("measurement", {}).get("values", {}).get("operation") if base_funded.get("status") == "measured" else None
        funded = value_initial[name]
        value = funded.get("measurement", {}).get("values", {}).get("operation") if funded.get("status") == "measured" else None
        later = value_confirm[name]
        confirmed_value = later.get("measurement", {}).get("values", {}).get("operation") if later.get("status") == "measured" else None
        other = value_secondary[name]
        secondary_value = other.get("measurement", {}).get("values", {}).get("operation") if other.get("status") == "measured" else None
        later_block, first_block = block_number(later), block_number(funded)
        later_ok = (confirmed_value == value and later_block is not None and
                    first_block is not None and later_block > first_block)
        if eth is None:
            status = "no-ethereum-baseline"
        elif value is None:
            status = funded.get("status", "missing")
        elif name == "ethereum":
            status = "ethereum-baseline"
        elif value == eth:
            status = "same-as-ethereum"
        elif later_ok and secondary_value == value:
            status = "confirmed-two-endpoints"
        elif later_ok:
            status = "confirmed-later-block"
        else:
            status = "unconfirmed-difference"
        rows.append({"chain": name, "case": "funded-call-value-empty", "family": "call-value",
                     "phase": "operation", "ethereum_gas": eth, "chain_gas": value,
                     "delta_gas": value - eth if isinstance(value, int) and isinstance(eth, int) else None,
                     "status": status, "initial_block": first_block,
                     "confirmation_block": later_block if confirmed_value is not None else None,
                     "confirmation_gas": confirmed_value, "secondary_gas": secondary_value,
                     "context_tag": funded.get("records", {}).get("gas_call", {}).get("request", {}).get("params", [None, None])[1] if funded.get("records", {}).get("gas_call") else None,
                     "raw_file": f"value-call/initial/{name}.json", "raw_pointer": "/records/gas_call",
                     "confirmation_file": f"value-call/confirm/{name}.json" if confirmed_value is not None else "",
                     "secondary_file": f"value-call/secondary/{name}.json" if secondary_value is not None else "",
                     "note": "one wei supplied by a funded public account in eth_call; target code empty; CALL status=1" if value is not None else funded.get("status", ""),
                     })

        base_stipend = base_funded.get("stipend", {})
        stipend = funded.get("stipend", {})
        later_stipend = later.get("stipend", {})
        other_stipend = other.get("stipend", {})
        eth = base_stipend.get("child_gasleft") if base_stipend.get("call_status") == 1 else None
        value = stipend.get("child_gasleft") if stipend.get("call_status") == 1 else None
        confirmed_value = later_stipend.get("child_gasleft") if later_stipend.get("call_status") == 1 else None
        secondary_value = other_stipend.get("child_gasleft") if other_stipend.get("call_status") == 1 else None
        later_ok = (confirmed_value == value and later_block is not None and
                    first_block is not None and later_block > first_block)
        if eth is None:
            status = "no-ethereum-baseline"
        elif value is None:
            status = funded.get("status", "missing")
        elif name == "ethereum":
            status = "ethereum-baseline"
        elif value == eth:
            status = "same-as-ethereum"
        elif later_ok and secondary_value == value:
            status = "confirmed-two-endpoints"
        elif later_ok:
            status = "confirmed-later-block"
        else:
            status = "unconfirmed-difference"
        rows.append({"chain": name, "case": "value-call-stipend", "family": "stipend",
                     "phase": "child_gasleft", "ethereum_gas": eth,
                     "chain_gas": value,
                     "delta_gas": value - eth if isinstance(value, int) and isinstance(eth, int) else None,
                     "status": status, "initial_block": first_block,
                     "confirmation_block": later_block if confirmed_value is not None else None,
                     "confirmation_gas": confirmed_value, "secondary_gas": secondary_value,
                     "context_tag": funded.get("records", {}).get("stipend_call", {}).get("request", {}).get("params", [None, None])[1] if funded.get("records", {}).get("stipend_call") else None,
                     "raw_file": f"value-call/initial/{name}.json", "raw_pointer": "/records/stipend_call",
                     "confirmation_file": f"value-call/confirm/{name}.json" if confirmed_value is not None else "",
                     "secondary_file": f"value-call/secondary/{name}.json" if secondary_value is not None else "",
                     "note": "child GAS result after zero-requested-gas CALL with one wei; transient child created inside eth_call",
                     })

    path = root / "MATRIX.csv"
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]), lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    counts = {}
    for row in rows:
        counts[row["status"]] = counts.get(row["status"], 0) + 1
    print(f"{path}: {len(rows)} cells; {counts}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

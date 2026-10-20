#!/usr/bin/env python3
"""Map the E29–E31 evidence matrices into compact site probes and cells."""

from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from urllib.parse import urlparse


ROOT = Path(__file__).resolve().parent.parent
DATE = "2026-10-20"
RESULTS = ROOT / "results" / DATE
sys.path.insert(0, str(ROOT / "probes"))
from run_gas_schedule import build_cases, encode, p, simple  # noqa: E402
from run_precompile_sweep import VECTORS, harness  # noqa: E402
from run_lifecycle_sweep import CASES, creation_data  # noqa: E402
from run_value_call import FORWARDED_GAS, EMPTY_ACCOUNT, stipend_code  # noqa: E402


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(newline="") as stream:
        return list(csv.DictReader(stream))


def number(value: str) -> int | None:
    return int(value) if value else None


def paths(*items: str) -> list[str]:
    result = []
    for item in items:
        if item and item not in result:
            result.append(item)
    return result


def gas_id(case: str, phase: str) -> str:
    return f"gas/{case}/{phase}"


def precompile_id(address: str, kind: str) -> str:
    return f"precompile-vector/{address}/{kind}"


def lifecycle_id(case: str) -> str:
    return f"lifecycle/{case}"


def gas_code(case_name: str) -> str:
    cases = build_cases()
    if case_name in cases:
        return "0x" + encode(cases[case_name]).hex()
    if case_name == "funded-call-value-empty":
        args = (0, 0, 0, 0, 1, EMPTY_ACCOUNT, FORWARDED_GAS)
        return "0x" + encode(simple(case_name, "call-value", 0xf1, args, 1)).hex()
    if case_name == "value-call-stipend":
        return "0x" + stipend_code().hex()
    raise ValueError(f"unknown gas case {case_name}")


def gas_value(row: dict) -> dict:
    return {"status": row["status"], "metric": "child_gasleft" if row["family"] == "stipend" else "gas_used",
            "gas": number(row["chain_gas"]), "ethereum_gas": number(row["ethereum_gas"]),
            "delta_gas": number(row["delta_gas"]), "phase": row["phase"], "family": row["family"],
            "confirmation_gas": number(row["confirmation_gas"]),
            "second_endpoint_gas": number(row["secondary_gas"]), "block_tag": row["context_tag"] or None,
            "note": row["note"] or None}


def gas_class(row: dict) -> str:
    status = row["status"]
    if status in {"ethereum-baseline", "same-as-ethereum"}:
        return "same"
    if status in {"confirmed-two-endpoints", "confirmed-later-block"} and row["delta_gas"] not in ("", "0"):
        return "differs"
    if status == "rpc-rejected":
        return "rpc-rejected"
    if status in {"no-public-rpc", "missing", "no-ethereum-baseline"}:
        return "unavailable"
    return "endpoint-artifact"  # unfunded control, simulation error, or unconfirmed difference


def precompile_value(row: dict, kind: str) -> dict:
    if kind == "valid":
        return {"status": row["valid_status"], "output": row["valid_output"] or None,
                "expected": row["valid_expected"], "first_call_gas": number(row["first_call_gas"]),
                "second_call_gas": number(row["second_call_gas"]), "gas_scope": row["gas_scope"],
                "later_block": row["valid_later"], "second_endpoint": row["valid_second_endpoint"]}
    malformed_gas = (number(row["malformed_first_gas"]), number(row["malformed_second_gas"]))
    at_budget_cap = row["malformed_status"] == "call-failed" and any(
        gas is not None and gas >= 10_000_000 for gas in malformed_gas)
    return {"status": row["malformed_status"], "output": row["malformed_output"] or None,
            "expected": None, "first_call_gas": number(row["malformed_first_gas"]),
            "second_call_gas": number(row["malformed_second_gas"]),
            "gas_scope": ("cap-exhausted-not-price" if at_budget_cap else
                          "length-control" if row["address"] in {"0x02", "0x03", "0x04"} else "malformed-control"),
            "later_block": row["malformed_later"], "second_endpoint": row["malformed_second_endpoint"]}


def precompile_class(row: dict, base: dict, kind: str) -> str:
    value, reference = precompile_value(row, kind), precompile_value(base, kind)
    status = value["status"]
    if status in {"rpc-rejected", "transport-error", "execution-failure", "malformed-return"}:
        return "rpc-rejected" if status == "rpc-rejected" else "endpoint-artifact"
    if row["chain"] == "ethereum":
        return "same"
    if value["later_block"] != "same":
        return "endpoint-artifact"
    if kind == "valid" and value["second_endpoint"] in {"different", "endpoint-error"}:
        # A pricing disagreement or provider failure is not a verified chain price.
        if status == "match":
            return "endpoint-artifact"
    if status != reference["status"] or value["output"] != reference["output"]:
        return "differs"
    if status in {"match", "output-success", "empty-success"} and (
            value["first_call_gas"] != reference["first_call_gas"] or
            value["second_call_gas"] != reference["second_call_gas"]):
        return "differs"
    return "same"


def lifecycle_value(row: dict) -> dict:
    return {"status": row["status"], "outcome": json.loads(row["outcome"]),
            "observed_words": json.loads(row["observed_words"]),
            "higher_gas_attempts": json.loads(row["higher_gas_attempts"]),
            "later_block": row["later_block"], "second_endpoint": row["second_endpoint"]}


def lifecycle_class(row: dict) -> str:
    status = row["versus_ethereum"]
    if row["chain"] == "ethereum" or status == "same":
        return "same"
    if status in {"different", "observed-vs-baseline-error"}:
        if row["case"].startswith("depth-"):
            return "endpoint-artifact"  # fixed gas allowance does not prove a depth limit
        return "differs"
    if row["status"] == "rpc-rejected":
        return "rpc-rejected"
    return "endpoint-artifact"


def build(chains: list[str]) -> tuple[list[dict], list[dict]]:
    probes: list[dict] = []
    cells: list[dict] = []
    gas_rows = rows(RESULTS / "gas-schedule/MATRIX.csv")
    gas_by = {(r["chain"], r["case"], r["phase"]): r for r in gas_rows}
    gas_base = [r for r in gas_rows if r["chain"] == "ethereum"]
    for base in gas_base:
        case, phase = base["case"], base["phase"]
        pid = gas_id(case, phase)
        metric = "child gas left" if base["family"] == "stipend" else "gas used"
        probes.append({"id": pid, "name": f"{case} · {phase}", "label": f"{case} ({phase})",
                       "category": "gas schedule", "sample_date": DATE,
                       "description": f"Measures {metric} for {case} in the {phase} phase with a read-only creation call.",
                       "init_code": gas_code(case), "ethereum_baseline": gas_value(base)})
        for chain in chains:
            r = gas_by[(chain, case, phase)]
            prefix = f"results/{DATE}/gas-schedule/"
            evidence = paths(prefix + r["raw_file"],
                             prefix + base["raw_file"] if chain != "ethereum" else "",
                             prefix + r["confirmation_file"] if r["confirmation_file"] else "",
                             prefix + r["secondary_file"] if r["secondary_file"] else "")
            cells.append({"chain": chain, "probe": pid, "class": gas_class(r),
                          "value": gas_value(r), "evidence": evidence,
                          "block": hex(int(r["initial_block"])) if r["initial_block"] else None,
                          "sample_date": DATE})

    pre_rows = rows(RESULTS / "precompile-sweep/MATRIX.csv")
    pre_by = {(r["chain"], r["address"]): r for r in pre_rows}
    for address, vector in VECTORS["vectors"].items():
        base = pre_by[("ethereum", address)]
        for kind in ("valid", "malformed"):
            pid = precompile_id(address, kind)
            source = vector[kind]
            control = "short-input control" if address in {"0x02", "0x03", "0x04"} and kind == "malformed" else kind + " vector"
            probes.append({"id": pid, "name": f"{vector['name']} · {kind}", "label": f"{vector['name']} {kind}",
                           "category": "precompile vectors", "sample_date": DATE,
                           "description": f"Calls {vector['name']} at {address} with a pinned {control} and records output, CALL status, and gas.",
                           "init_code": "0x" + harness(int(address, 16), bytes.fromhex(source["input"][2:])).hex(),
                           "vector_source": source["source"], "ethereum_baseline": precompile_value(base, kind)})
            for chain in chains:
                r = pre_by.get((chain, address))
                if r is None:
                    evidence = paths(f"results/{DATE}/precompile-sweep/initial/{chain}.json",
                                     f"results/{DATE}/precompile-sweep/initial/ethereum.json")
                    cells.append({"chain": chain, "probe": pid, "class": "unavailable", "value": None,
                                  "evidence": evidence, "block": None, "sample_date": DATE})
                    continue
                prefix = f"results/{DATE}/precompile-sweep/"
                evidence = paths(prefix + r["initial_evidence"],
                                 prefix + base["initial_evidence"] if chain != "ethereum" else "",
                                 prefix + r["later_evidence"] if r["later_evidence"] else "",
                                 prefix + r["second_endpoint_evidence"] if r["second_endpoint_evidence"] else "")
                cells.append({"chain": chain, "probe": pid, "class": precompile_class(r, base, kind),
                              "value": precompile_value(r, kind), "evidence": evidence,
                              "block": r["block"], "sample_date": DATE})

    life_rows = rows(RESULTS / "lifecycle/MATRIX.csv")
    life_by = {(r["chain"], r["case"]): r for r in life_rows}
    for case_name, (mode, arg, _needs_value, _names) in CASES.items():
        base = life_by[("ethereum", case_name)]
        pid = lifecycle_id(case_name)
        probes.append({"id": pid, "name": case_name.replace("-", " ").capitalize(),
                       "label": case_name, "category": "lifecycle", "sample_date": DATE,
                       "description": f"Executes the {case_name} lifecycle boundary inside a read-only creation call and records the returned state.",
                       "init_code": creation_data(mode, arg), "ethereum_baseline": lifecycle_value(base)})
        for chain in chains:
            r = life_by.get((chain, case_name))
            if r is None:
                evidence = paths(f"results/{DATE}/lifecycle/initial/{chain}.json",
                                 f"results/{DATE}/lifecycle/initial/ethereum.json")
                cells.append({"chain": chain, "probe": pid, "class": "unavailable", "value": None,
                              "evidence": evidence, "block": None, "sample_date": DATE})
                continue
            prefix = f"results/{DATE}/lifecycle/"
            evidence = paths(prefix + r["initial_evidence"],
                             prefix + base["initial_evidence"] if chain != "ethereum" else "",
                             prefix + r["later_evidence"] if r["later_evidence"] else "",
                             prefix + r["second_endpoint_evidence"] if r["second_endpoint_evidence"] else "")
            cells.append({"chain": chain, "probe": pid, "class": lifecycle_class(r),
                          "value": lifecycle_value(r), "evidence": evidence,
                          "block": r["block"], "sample_date": DATE})
    return probes, cells

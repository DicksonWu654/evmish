#!/usr/bin/env python3
"""Run E31 limits/lifecycle cases with read-only public eth_call creation code."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import hashlib
import json
import pathlib
import sys
import time

from run_creation_probes import RpcClient, is_evm_execution_error, rpc_body
from run_gas_schedule import REGISTRY, ROOT, TODAY, call_record, write_json


ARTIFACT = json.loads((ROOT / "probes/lifecycle_bytecode.json").read_text())
SOURCE = ROOT / "probes/lifecycle_probe.sol"
if hashlib.sha256(SOURCE.read_bytes()).hexdigest() != ARTIFACT["source_sha256"]:
    raise RuntimeError("lifecycle Solidity source and compiled bytecode disagree")

BURN = "0x000000000000000000000000000000000000dEaD"
CALL_GAS = 30_000_000
CASES = {
    "runtime-24575": (0, 24575, False, ("child", "code_size", "code_hash", "create_gas")),
    "runtime-24576": (0, 24576, False, ("child", "code_size", "code_hash", "create_gas")),
    "runtime-24577": (0, 24577, False, ("child", "code_size", "code_hash", "create_gas")),
    "init-49120": (1, 49120, False, ("child", "code_size", "create_gas")),
    "init-49152": (1, 49152, False, ("child", "code_size", "create_gas")),
    "init-49153": (1, 49153, False, ("child", "code_size", "create_gas")),
    "returndata-revert": (2, 0, False, ("child", "return_status", "return_length", "return_marker",
                                      "revert_status", "revert_length", "revert_marker")),
    "failed-create-nonce": (3, 0, False, ("creator", "failed_child", "next_child")),
    "selfdestruct-zero": (4, 0, False, ("child", "code_before", "hash_before", "balance_before",
                                         "beneficiary_before", "kill_status", "code_after", "hash_after",
                                         "balance_after", "beneficiary_after")),
    "selfdestruct-funded": (4, 1, True, ("child", "code_before", "hash_before", "balance_before",
                                          "beneficiary_before", "kill_status", "code_after", "hash_after",
                                          "balance_after", "beneficiary_after")),
    "precompile-value": (5, 0, True, ("call_status", "output_length", "first_byte",
                                      "precompile_balance_before", "precompile_balance_after", "caller_value_spent")),
    "depth-64": (6, 64, False, ("helper", "call_status", "max_reported_depth", "reached_target", "call_gas")),
    "depth-256": (6, 256, False, ("helper", "call_status", "max_reported_depth", "reached_target", "call_gas")),
    "depth-512": (6, 512, False, ("helper", "call_status", "max_reported_depth", "reached_target", "call_gas")),
    "depth-1024": (6, 1024, False, ("helper", "call_status", "max_reported_depth", "reached_target", "call_gas")),
}


def result_of(record: dict) -> object:
    return (rpc_body(record["response"]) or {}).get("result")


def creation_data(mode: int, arg: int) -> str:
    return ARTIFACT["creation_bytecode"] + mode.to_bytes(32, "big").hex() + arg.to_bytes(32, "big").hex()


def decode(response: dict, names: tuple[str, ...]) -> dict:
    body = rpc_body(response)
    if body is None:
        return {"status": "transport-error", "error": response.get("transport_error")}
    if "error" in body:
        error = body["error"]
        message = str(error.get("message", "")).lower() if isinstance(error, dict) else str(error).lower()
        if any(term in message for term in ("gas cap", "gas limit exceeded", "exceeds allowance",
                                            "request timeout", "free plan", "block gas limit")):
            status = "endpoint-limit"
        elif "out of gas" in message and ("gas required exceeds" in message or
                                             "gas required" in message):
            status = "call-gas-exhausted"
        elif is_evm_execution_error(response) or "createinitcodesizelimit" in message:
            status = "outer-execution-failure"
        else:
            status = "rpc-rejected"
        return {"status": status, "error": error}
    raw = body.get("result")
    if not isinstance(raw, str) or not raw.startswith("0x") or len(raw) != 2 + 64 * len(names):
        return {"status": "malformed-return", "raw": raw}
    words = [int(raw[2 + 64 * i:2 + 64 * (i + 1)], 16) for i in range(len(names))]
    return {"status": "observed", "words": dict(zip(names, words)), "raw_return": raw}


def funded_sender(client: RpcClient, block: dict, tag: str) -> tuple[str | None, list[dict]]:
    candidates = [BURN]
    miner = block.get("miner")
    if isinstance(miner, str) and miner.lower() != BURN.lower():
        candidates.append(miner)
    records = []
    for candidate in candidates:
        raw = call_record(client, "eth_getBalance", [candidate, tag])
        records.append({"address": candidate, **raw})
        value = result_of(raw)
        if isinstance(value, str):
            try:
                if int(value, 16) >= 1:
                    return candidate, records
            except ValueError:
                pass
    return None, records


def run_chain(name: str, phase: str, out: pathlib.Path) -> dict:
    config = REGISTRY[name]
    endpoints = config.get("rpcs", [])
    index = 1 if phase == "secondary" else 0
    path = out / phase / f"{name}.json"
    if len(endpoints) <= index:
        result = {"chain": name, "phase": phase,
                  "status": "no-secondary-rpc" if index else "no-public-rpc",
                  "reason": config.get("rpc_status") if index == 0 else "No second listed endpoint",
                  "cases": {}}
        write_json(path, result)
        return result
    client = RpcClient(endpoints[index]["url"])
    context = {"eth_chainId": call_record(client, "eth_chainId", []),
               "eth_blockNumber": call_record(client, "eth_blockNumber", [])}
    tag = result_of(context["eth_blockNumber"])
    context["eth_getBlockByNumber"] = call_record(client, "eth_getBlockByNumber", [tag, False])
    block = result_of(context["eth_getBlockByNumber"])
    if not isinstance(block, dict):
        context["eth_getBlockByNumber_latest_retry"] = call_record(client, "eth_getBlockByNumber", ["latest", False])
        block = result_of(context["eth_getBlockByNumber_latest_retry"])
        if isinstance(block, dict):
            tag = "latest"
    observed_id = result_of(context["eth_chainId"])
    result = {"chain": name, "phase": phase, "rpc": endpoints[index],
              "expected_chain_id": config["chain_id"], "observed_chain_id": observed_id,
              "block": block, "context": context, "cases": {},
              "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(), "status": "ok"}
    if observed_id != hex(config["chain_id"]) or not isinstance(block, dict):
        result["status"] = "endpoint-context-error"
        write_json(path, result)
        return result
    if phase == "confirm":
        first_path = out / "initial" / f"{name}.json"
        first = json.loads(first_path.read_text()) if first_path.exists() else {}
        old = first.get("block", {}).get("number") if isinstance(first.get("block"), dict) else None
        if not isinstance(old, str) or int(block["number"], 16) <= int(old, 16):
            result["status"] = "no-later-block"
            write_json(path, result)
            return result
    sender, sender_records = funded_sender(client, block, tag)
    result["funded_sender"] = sender
    result["sender_checks"] = sender_records
    for case_name, (mode, arg, needs_value, names) in CASES.items():
        if needs_value and sender is None:
            result["cases"][case_name] = {"status": "no-funded-sender", "interpretation": {"status": "not-run"}}
            continue
        tx = {"data": creation_data(mode, arg), "gas": hex(CALL_GAS)}
        if needs_value:
            tx["from"] = sender
            tx["value"] = "0x1"
        raw = call_record(client, "eth_call", [tx, tag])
        attempts = [raw]
        err = (rpc_body(raw["response"]) or {}).get("error")
        message = str(err.get("message", "")).lower() if isinstance(err, dict) else ""
        if tag != "latest" and any(x in message for x in ("missing trie node", "quantity not supported", "invalid height")):
            raw = call_record(client, "eth_call", [tx, "latest"])
            attempts.append(raw)
        result["cases"][case_name] = {
            "mode": mode, "arg": arg, "needs_value": needs_value,
            "block_tag": raw["request"]["params"][1], "attempts": attempts,
            "raw": raw, "interpretation": decode(raw["response"], names),
        }
    # If even the 24,576-byte control failed at 30M gas, code-size inference
    # is unsafe. Ask the same endpoint for a higher read-only simulation cap;
    # retain its refusal or second result as endpoint evidence.
    anchor = result["cases"]["runtime-24576"]["interpretation"]
    if (anchor["status"] == "call-gas-exhausted" or
            (anchor["status"] == "observed" and anchor["words"]["child"] == 0)):
        for gas_limit in (60_000_000, 120_000_000, 250_000_000):
            control_succeeded = False
            for case_name in ("runtime-24575", "runtime-24576", "runtime-24577"):
                mode, arg, _, names = CASES[case_name]
                tx = {"data": creation_data(mode, arg), "gas": hex(gas_limit)}
                high = call_record(client, "eth_call", [tx, tag])
                high_interpretation = decode(high["response"], names)
                result["cases"][case_name].setdefault("higher_gas_attempts", []).append({
                    "gas_limit": gas_limit, "raw": high,
                    "interpretation": high_interpretation})
                if (case_name == "runtime-24576" and high_interpretation["status"] == "observed" and
                        high_interpretation["words"]["code_size"] == 24576):
                    control_succeeded = True
            if control_succeeded:
                break
    write_json(path, result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=TODAY)
    parser.add_argument("--phase", choices=("initial", "confirm", "secondary"), default="initial")
    parser.add_argument("--chains")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    names = list(REGISTRY) if not args.chains else [x.strip() for x in args.chains.split(",") if x.strip()]
    if set(names) - set(REGISTRY):
        parser.error("unknown chain name")
    out = ROOT / "results" / args.date / "lifecycle"
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.workers, len(names))) as pool:
        for result in pool.map(lambda name: run_chain(name, args.phase, out), names):
            statuses = {}
            for cell in result["cases"].values():
                status = cell["interpretation"]["status"]
                statuses[status] = statuses.get(status, 0) + 1
            print(result["chain"], result["status"], len(result["cases"]), statuses, flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())

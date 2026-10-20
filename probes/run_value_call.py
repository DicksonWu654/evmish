#!/usr/bin/env python3
"""Measure a funded one-wei CALL to an empty account via read-only eth_call."""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import pathlib

from run_creation_probes import RpcClient, push_int, rpc_body
from run_gas_schedule import (EMPTY_ACCOUNT, REGISTRY, ROOT, TODAY,
                              call_record, decode, encode, p, simple, write_json)


BURN = "0x000000000000000000000000000000000000dEaD"
FORWARDED_GAS = 1_000_000


def result_of(record: dict):
    return (rpc_body(record["response"]) or {}).get("result")


def stipend_code() -> bytes:
    """Create a transient child, CALL it with one wei and zero requested gas.

    The child returns GAS in word 0. Words 1 and 2 are CALL status and child
    address. A nonzero gas result proves that the value stipend was forwarded.
    """
    runtime = b"\x5a\x5f\x52\x60\x20\x5f\xf3"
    child_prefix = p(len(runtime)) + push_int(0, 2) + p(0) + b"\x39" + p(len(runtime)) + p(0) + b"\xf3"
    child_init = p(len(runtime)) + push_int(len(child_prefix), 2) + p(0) + b"\x39" + p(len(runtime)) + p(0) + b"\xf3" + runtime

    def parent(source: int) -> bytes:
        copy = p(len(child_init)) + push_int(source, 2) + p(0) + b"\x39"
        create = p(len(child_init)) + p(0) + p(0) + b"\xf0"
        # child address is below five CALL arguments; DUP6 copies it.
        call = p(32) + p(0) + p(0) + p(0) + p(1) + b"\x85" + p(0) + b"\xf1"
        save = p(32) + b"\x52" + p(64) + b"\x52" + p(96) + p(0) + b"\xf3"
        return copy + create + call + save

    prefix = parent(0)
    return parent(len(prefix)) + child_init


def run(name: str, phase: str, root: pathlib.Path) -> dict:
    config = REGISTRY[name]
    endpoints = config.get("rpcs", [])
    index = 1 if phase == "secondary" else 0
    out = root / phase / f"{name}.json"
    if len(endpoints) <= index:
        result = {"chain": name, "phase": phase,
                  "status": "no-secondary-rpc" if index else "no-public-rpc"}
        write_json(out, result)
        return result
    client = RpcClient(endpoints[index]["url"])
    records = {}
    for key, method, params in (
        ("chain_id", "eth_chainId", []),
        ("height", "eth_blockNumber", []),
    ):
        records[key] = call_record(client, method, params)
    tag = result_of(records["height"])
    records["header"] = call_record(client, "eth_getBlockByNumber", [tag, False])
    block = result_of(records["header"])
    if not isinstance(block, dict):
        records["header_latest_retry"] = call_record(client, "eth_getBlockByNumber", ["latest", False])
        block = result_of(records["header_latest_retry"])
        if isinstance(block, dict):
            tag = "latest"
    result = {"chain": name, "phase": phase, "status": "context-error",
              "rpc": endpoints[index], "records": records, "block": block,
              "expected_chain_id": config["chain_id"],
              "observed_chain_id": result_of(records["chain_id"]),
              "observed_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    if result["observed_chain_id"] != hex(config["chain_id"]) or not isinstance(block, dict):
        write_json(out, result)
        return result
    if phase == "confirm":
        first_path = root / "initial" / f"{name}.json"
        if first_path.exists():
            first = json.loads(first_path.read_text())
            old = first.get("block", {}).get("number")
            if isinstance(old, str) and int(block["number"], 16) <= int(old, 16):
                result["status"] = "no-later-block"
                write_json(out, result)
                return result

    target = "0x" + EMPTY_ACCOUNT.to_bytes(20, "big").hex()
    records["target_code"] = call_record(client, "eth_getCode", [target, tag])
    records["target_balance"] = call_record(client, "eth_getBalance", [target, tag])
    records["target_nonce"] = call_record(client, "eth_getTransactionCount", [target, tag])
    target_code = result_of(records["target_code"])
    target_balance = result_of(records["target_balance"])
    target_nonce = result_of(records["target_nonce"])
    if not all(isinstance(value, str) for value in (target_code, target_balance, target_nonce)):
        result["status"] = "target-state-rpc-error"
        write_json(out, result)
        return result
    if name == "tempo" and target_code in ("0x", "0x0") and int(target_nonce, 16) == 0 and int(target_balance, 16) != 0:
        result["status"] = "synthetic-balance-rpc"
        result["reason"] = "Tempo documents eth_getBalance as a synthetic native-balance value"
        write_json(out, result)
        return result
    if target_code not in ("0x", "0x0") or int(target_balance, 16) != 0 or int(target_nonce, 16) != 0:
        result["status"] = "target-not-empty"
        write_json(out, result)
        return result
    candidates = [BURN]
    miner = block.get("miner")
    if isinstance(miner, str) and miner.lower() != BURN.lower():
        candidates.append(miner)
    selected = None
    for candidate in candidates:
        balance = call_record(client, "eth_getBalance", [candidate, tag])
        records.setdefault("candidate_balances", []).append({"address": candidate, **balance})
        value = result_of(balance)
        if isinstance(value, str) and int(value, 16) >= 1:
            selected = candidate
            break
    if selected is None:
        result["status"] = "no-funded-sender"
        write_json(out, result)
        return result
    result["sender"] = selected
    # Somnia requires enough available gas to open a new account. The unused
    # forwarded amount is returned, so this measures successful CALL cost.
    args = (0, 0, 0, 0, 1, EMPTY_ACCOUNT, FORWARDED_GAS)
    case = simple("funded-call-value-empty", "call-value", 0xf1, args, 1)
    tx = {"from": selected, "value": "0x1", "gas": "0x1c9c380",
          "data": "0x" + encode(case).hex()}
    records["gas_call"] = call_record(client, "eth_call", [tx, tag])
    result["measurement"] = decode(case, records["gas_call"]["response"])
    status_code = b"".join(p(x) for x in args) + b"\xf1" + p(0) + b"\x52" + p(32) + p(0) + b"\xf3"
    status_tx = {**tx, "data": "0x" + status_code.hex()}
    records["status_call"] = call_record(client, "eth_call", [status_tx, tag])
    status_word = result_of(records["status_call"])
    result["call_succeeded"] = isinstance(status_word, str) and len(status_word) > 2 and int(status_word, 16) == 1
    stipend_tx = {**tx, "data": "0x" + stipend_code().hex()}
    records["stipend_call"] = call_record(client, "eth_call", [stipend_tx, tag])
    stipend_raw = result_of(records["stipend_call"])
    if isinstance(stipend_raw, str) and len(stipend_raw) == 2 + 64 * 3:
        words = [int(stipend_raw[2 + 64 * i:2 + 64 * (i + 1)], 16) for i in range(3)]
        result["stipend"] = {"child_gasleft": words[0], "call_status": words[1],
                             "child_address": "0x" + words[2].to_bytes(20, "big").hex()}
    else:
        result["stipend"] = {"status": "unavailable", "raw": stipend_raw}
    result["status"] = "measured" if result["measurement"]["status"] == "measured" and result["call_succeeded"] else "call-failed"
    write_json(out, result)
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
    out = ROOT / "results" / args.date / "gas-schedule" / "value-call"
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.workers, len(names))) as pool:
        for result in pool.map(lambda name: run(name, args.phase, out), names):
            print(result["chain"], result["status"], flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

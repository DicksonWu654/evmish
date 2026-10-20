#!/usr/bin/env python3
"""Call real and malformed precompile vectors through read-only creation code.

The init code returns both full 256-byte output buffers, CALL status, return
length, and control-subtracted gas for cold and warm calls. Public chain state
is never changed. Vector provenance lives in precompile_vectors.json.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import pathlib
import sys

from run_creation_probes import RpcClient, is_evm_execution_error, push_int, rpc_body
from run_gas_schedule import REGISTRY, ROOT, TODAY, call_record, p, write_json


VECTORS = json.loads((ROOT / "probes/precompile_vectors.json").read_text())
OUT_BYTES = 256
FIRST_OUT = 0x1000
SECOND_OUT = FIRST_OUT + OUT_BYTES
META = SECOND_OUT + OUT_BYTES
META_NAMES = ("control_delta", "first_delta", "second_delta", "first_status",
              "second_status", "first_return_length", "second_return_length")
TOTAL_BYTES = OUT_BYTES * 2 + 32 * len(META_NAMES)
CALL_CORRECTION = 14  # seven control POPs, each costing 2 gas
FORWARDED_GAS = 10_000_000  # Bound two failing calls so the outer init code can return.


def call_args(address: int, input_size: int, output_offset: int,
              forwarded_gas: int = FORWARDED_GAS) -> bytes:
    return (p(OUT_BYTES) + p(output_offset) + p(input_size) + p(0) +
            p(0) + p(address) + p(forwarded_gas))


def harness(address: int, data: bytes, *, repeat: bool = True,
            forwarded_gas: int = FORWARDED_GAS) -> bytes:
    if len(data) > FIRST_OUT:
        raise ValueError("vector input would overlap the output buffer")
    args_first = call_args(address, len(data), FIRST_OUT, forwarded_gas)
    args_second = call_args(address, len(data), SECOND_OUT, forwarded_gas)
    control = b"\x5a" + args_first + b"\x50" * 7 + b"\x5a\x90\x03" + p(META) + b"\x52"

    def target(args: bytes, gas_offset: int, status_offset: int, size_offset: int) -> bytes:
        return (b"\x5a" + args + b"\xf1\x5a\x90" + p(status_offset) + b"\x52" +
                b"\x90\x03" + p(gas_offset) + b"\x52" +
                b"\x3d" + p(size_offset) + b"\x52")

    first = target(args_first, META + 32, META + 96, META + 160)
    second = target(args_second, META + 64, META + 128, META + 192)
    body = (p(0) + p(META + 192) + b"\x52" + control + first + (second if repeat else b"") +
            p(TOTAL_BYTES) + p(FIRST_OUT) + b"\xf3")
    prefix = p(len(data)) + push_int(0, 2) + p(0) + b"\x39"
    source = len(prefix) + len(body)
    prefix = p(len(data)) + push_int(source, 2) + p(0) + b"\x39"
    return prefix + body + data


def decode(response: dict, expected: str | None, *, repeat: bool = True) -> dict:
    body = rpc_body(response)
    if body is None:
        return {"status": "transport-error", "error": response.get("transport_error")}
    if "error" in body:
        return {"status": "execution-failure" if is_evm_execution_error(response) else "rpc-rejected",
                "error": body["error"]}
    raw = body.get("result")
    if not isinstance(raw, str) or not raw.startswith("0x") or len(raw) != 2 + 2 * TOTAL_BYTES:
        return {"status": "malformed-return", "raw": raw}
    value = bytes.fromhex(raw[2:])
    words = [int.from_bytes(value[OUT_BYTES * 2 + 32 * i:OUT_BYTES * 2 + 32 * (i + 1)], "big")
             for i in range(len(META_NAMES))]
    meta = dict(zip(META_NAMES, words))
    first_size, second_size = meta["first_return_length"], meta["second_return_length"]
    first_data = value[:min(first_size, OUT_BYTES)]
    second_data = value[OUT_BYTES:OUT_BYTES + min(second_size, OUT_BYTES)]
    first_gas = meta["first_delta"] - meta["control_delta"] + CALL_CORRECTION
    second_gas = (meta["second_delta"] - meta["control_delta"] + CALL_CORRECTION
                  if repeat else None)
    if first_size > OUT_BYTES or second_size > OUT_BYTES:
        status = "output-truncated"
    elif meta["first_status"] == 0:
        status = "call-failed"
    elif first_size == 0:
        status = "empty-success"
    elif expected is not None and first_data.hex() == expected.removeprefix("0x"):
        status = "match"
    elif expected is not None:
        status = "mismatch"
    else:
        status = "output-success"
    return {"status": status, "output": "0x" + first_data.hex(),
            "second_output": "0x" + second_data.hex() if repeat else None,
            "first_call_gas": first_gas, "second_call_gas": second_gas,
            "meta": meta, "expected": expected,
            "measurement_mode": "two-calls" if repeat else "single-high-gas"}


def result_of(record: dict):
    return (rpc_body(record["response"]) or {}).get("result")


def run_chain(name: str, phase: str, out: pathlib.Path) -> dict:
    config = REGISTRY[name]
    index = 1 if phase == "secondary" else 0
    endpoints = config.get("rpcs", [])
    path = out / phase / f"{name}.json"
    if len(endpoints) <= index:
        result = {"chain": name, "phase": phase,
                  "status": "no-secondary-rpc" if index else "no-public-rpc",
                  "reason": config.get("rpc_status") if index == 0 else "No second endpoint in registry",
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
              "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(),
              "status": "ok"}
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

    for address, vector in VECTORS["vectors"].items():
        for kind in ("valid", "malformed"):
            chosen = vector[kind]
            bytecode = harness(int(address, 16), bytes.fromhex(chosen["input"][2:]))
            tx = {"data": "0x" + bytecode.hex(), "gas": "0x1c9c380"}
            raw = call_record(client, "eth_call", [tx, tag])
            attempts = [raw]
            err = (rpc_body(raw["response"]) or {}).get("error")
            message = str(err.get("message", "")).lower() if isinstance(err, dict) else ""
            if tag != "latest" and ("quantity not supported" in message or
                                    "missing trie node" in message or "invalid height" in message):
                if "quantity not supported" in message:
                    tag = "latest"
                raw = call_record(client, "eth_call", [tx, "latest"])
                attempts.append(raw)
            interpretation = decode(raw["response"], chosen.get("expected"))
            high_gas_attempt = None
            high_gas_interpretation = None
            # A 10M-gas CALL can make a valid, unusually expensive precompile
            # look like a failed implementation. Retry once with a single
            # 25M-gas CALL; two such calls would exceed the outer eth_call cap.
            if (kind == "valid" and interpretation["status"] == "call-failed" and
                    interpretation.get("first_call_gas", 0) >= FORWARDED_GAS):
                high_code = harness(int(address, 16), bytes.fromhex(chosen["input"][2:]),
                                    repeat=False, forwarded_gas=25_000_000)
                high_tx = {"data": "0x" + high_code.hex(), "gas": "0x1c9c380"}
                high_gas_attempt = call_record(client, "eth_call", [high_tx, tag])
                high_gas_interpretation = decode(
                    high_gas_attempt["response"], chosen.get("expected"), repeat=False)
                if high_gas_interpretation["status"] == "match":
                    interpretation = high_gas_interpretation
            result["cases"][f"{address}.{kind}"] = {
                "address": address, "kind": kind, "vector_name": chosen.get("name"),
                "source": chosen["source"], "description": chosen.get("description"),
                "block_tag": raw["request"]["params"][1], "raw": raw,
                "attempts": attempts,
                "high_gas_attempt": high_gas_attempt,
                "high_gas_interpretation": high_gas_interpretation,
                "interpretation": interpretation,
            }
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
    out = ROOT / "results" / args.date / "precompile-sweep"
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

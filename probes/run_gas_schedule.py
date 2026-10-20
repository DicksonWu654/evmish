#!/usr/bin/env python3
"""Read-only, control-subtracted gas measurements on the chain registry.

Each eth_call executes creation init code without a ``to`` address.  A case
returns the GAS deltas for a no-op control and one or more operations.  The
control has the same argument pushes and discards its inputs; a documented
stack correction removes those POPs.  No public state is changed.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import pathlib
import sys
import time
from dataclasses import dataclass

from run_creation_probes import RpcClient, is_evm_execution_error, push_int, rpc_body


ROOT = pathlib.Path(__file__).resolve().parent.parent
REGISTRY = json.loads((ROOT / "probes/chains.json").read_text())
TODAY = dt.datetime.now(dt.timezone.utc).date().isoformat()
EMPTY_ACCOUNT = int("0x9baeb70184075f3ea43e6e8160ec2f162da8d28b", 16)


@dataclass(frozen=True)
class Case:
    name: str
    family: str
    control: bytes
    targets: tuple[tuple[str, bytes], ...]
    correction: int
    prelude: bytes = b""
    detail: str = ""
    suffix: bytes = b""


def p(value: int) -> bytes:
    return push_int(value)


def simple(name: str, family: str, opcode: int, args: tuple[int, ...] = (),
           outputs: int = 1, prelude: bytes = b"", detail: str = "") -> Case:
    pushes = b"".join(p(arg) for arg in args)
    control = pushes + b"\x50" * len(args)
    target = pushes + bytes([opcode]) + b"\x50" * outputs
    return Case(name, family, control, (("operation", target),),
                2 * (len(args) - outputs), prelude, detail)


def access(name: str, opcode: int, args: tuple[int, ...], outputs: int,
           prelude: bytes = b"", detail: str = "") -> Case:
    base = simple(name, "cold-warm", opcode, args, outputs, prelude, detail)
    body = base.targets[0][1]
    return Case(name, "cold-warm", base.control,
                (("cold", body), ("warm", body)), base.correction, prelude, detail)


def preexpand(words: int) -> bytes:
    if words <= 0:
        return b""
    return p(0) + p(words * 32 - 32) + b"\x52"  # MSTORE before the timers


def build_cases() -> dict[str, Case]:
    cases: dict[str, Case] = {}

    def add(case: Case) -> None:
        if case.name in cases:
            raise ValueError(case.name)
        cases[case.name] = case

    # Representatives span the EVM's simple gas tiers and operand classes.
    # Constants avoid division by zero and signed overflow. STOP/RETURN/REVERT
    # cannot be measured inside a continuing GAS timer.
    simple_specs = [
        ("add", 0x01, (7, 3), 1), ("mul", 0x02, (7, 3), 1),
        ("sub", 0x03, (7, 3), 1), ("div", 0x04, (3, 7), 1),
        ("sdiv", 0x05, (3, 7), 1), ("mod", 0x06, (3, 7), 1),
        ("smod", 0x07, (3, 7), 1), ("addmod", 0x08, (5, 7, 3), 1),
        ("mulmod", 0x09, (5, 7, 3), 1), ("exp-zero", 0x0a, (0, 2), 1),
        ("exp-one-byte", 0x0a, (2, 2), 1),
        ("signextend", 0x0b, (1, 255), 1),
        ("lt", 0x10, (7, 3), 1), ("gt", 0x11, (7, 3), 1),
        ("slt", 0x12, (7, 3), 1), ("sgt", 0x13, (7, 3), 1),
        ("eq", 0x14, (7, 3), 1), ("iszero", 0x15, (7,), 1),
        ("and", 0x16, (7, 3), 1), ("or", 0x17, (7, 3), 1),
        ("xor", 0x18, (7, 3), 1), ("not", 0x19, (7,), 1),
        ("byte", 0x1a, (7, 3), 1),
        ("shl", 0x1b, (7, 3), 1), ("shr", 0x1c, (7, 3), 1),
        ("sar", 0x1d, (7, 3), 1),
        ("address", 0x30, (), 1), ("origin", 0x32, (), 1),
        ("caller", 0x33, (), 1), ("callvalue", 0x34, (), 1),
        ("calldataload", 0x35, (0,), 1),
        ("calldatasize", 0x36, (), 1), ("codesize", 0x38, (), 1),
        ("gasprice", 0x3a, (), 1), ("returndatasize", 0x3d, (), 1),
        ("blockhash", 0x40, (0,), 1),
        ("coinbase", 0x41, (), 1), ("timestamp", 0x42, (), 1),
        ("number", 0x43, (), 1), ("prevrandao", 0x44, (), 1),
        ("gaslimit", 0x45, (), 1), ("chainid", 0x46, (), 1),
        ("selfbalance", 0x47, (), 1), ("basefee", 0x48, (), 1),
        ("blobhash", 0x49, (0,), 1), ("blobbasefee", 0x4a, (), 1),
        ("pop", 0x50, (7,), 0),
        ("pc", 0x58, (), 1), ("msize", 0x59, (), 1),
        ("gas", 0x5a, (), 1), ("jumpdest", 0x5b, (), 0),
        ("push0", 0x5f, (), 1),
        ("push1", 0x60, (), 1), ("dup1", 0x80, (7,), 2),
        ("swap1", 0x90, (7, 3), 2),
    ]
    for name, opcode, args, outputs in simple_specs:
        # PUSH1 has its own immediate byte; generic simple() would leave a
        # stray opcode after the timer. Treat the immediate as part of it.
        if name == "push1":
            add(Case(name, "simple", b"", (("operation", b"\x60\x07\x50"),), -2))
        else:
            add(simple(name, "simple", opcode, args, outputs))

    add(simple("mload-warm-memory", "memory", 0x51, (0,), 1, preexpand(1)))
    add(simple("mstore-warm-memory", "memory", 0x52, (7, 0), 0, preexpand(1)))
    add(simple("mstore8-warm-memory", "memory", 0x53, (7, 0), 0, preexpand(1)))
    for name, opcode, args in (
        ("calldatacopy-32", 0x37, (32, 0, 0)),
        ("codecopy-32", 0x39, (32, 0, 0)),
        ("returndatacopy-0", 0x3e, (0, 0, 0)),
    ):
        add(simple(name, "copy", opcode, args, 0, preexpand(1),
                   "memory pre-expanded; RETURNDATACOPY uses zero bytes"))
    for conditional in (False, True):
        cond = p(1) if conditional else b""
        # The target's JUMPDEST lies four bytes after the target timer starts,
        # plus the optional condition push. The control timer occupies 4 bytes.
        control_len = len(cond) + 3 + 1 + int(conditional)
        target_start = control_len + 5
        destination = target_start + len(cond) + 3 + 1
        control = cond + push_int(destination, 2) + b"\x50" * (1 + int(conditional))
        target = cond + push_int(destination, 2) + (b"\x57" if conditional else b"\x56") + b"\x5b"
        add(Case("jumpi" if conditional else "jump", "flow", control,
                 (("operation", target),), 3 if conditional else 1,
                 detail="JUMPDEST gas removed from the measured branch cost"))
    for words in (1, 32, 1024, 32768):
        add(simple(f"memory-expand-{words}-words", "memory", 0x52,
                   (7, words * 32 - 32), 0, detail="MSTORE cost includes expansion from zero words"))
        size = words * 32
        add(simple(f"mcopy-{words}-words", "mcopy", 0x5e, (size, 0, 0),
                   0, preexpand(words), detail="source and destination pre-expanded"))
    for words in (0, 1, 2, 4, 32):
        add(simple(f"keccak-{words}-words", "keccak", 0x20, (words * 32, 0),
                   1, preexpand(words), detail="input memory pre-expanded"))
    for topics in range(5):
        for size in (0, 1, 32, 64, 256):
            args = (0,) * topics + (size, 0)
            add(simple(f"log{topics}-{size}-bytes", "log", 0xa0 + topics,
                       args, 0, preexpand((size + 31) // 32),
                       detail="payload memory pre-expanded; log discarded by eth_call"))

    add(access("sload-slot0", 0x54, (0,), 1, detail="fresh creation storage slot zero"))
    add(access("balance-empty", 0x31, (EMPTY_ACCOUNT,), 1))
    add(access("extcodehash-empty", 0x3f, (EMPTY_ACCOUNT,), 1))
    add(access("extcodesize-empty", 0x3b, (EMPTY_ACCOUNT,), 1))
    add(access("extcodecopy-empty", 0x3c, (32, 0, 0, EMPTY_ACCOUNT), 0,
               preexpand(1), "32 copied bytes; output memory pre-expanded"))
    # CALL arguments are pushed in reverse stack order. Zero forwarded gas
    # makes the account-access cost measurable without executing code.
    call_args = (0, 0, 0, 0, 0, EMPTY_ACCOUNT, 0)
    add(access("call-empty", 0xf1, call_args, 1,
               detail="zero value, zero forwarded gas; empty account"))
    value_args = (0, 0, 0, 0, 1, EMPTY_ACCOUNT, 0)
    add(simple("call-value-empty", "call-value", 0xf1, value_args, 1,
               detail="one wei from unfunded creation context; failure/status must be checked separately"))

    sstore_control = p(1) + p(0) + b"\x50\x50"
    sstore_targets = tuple((label, p(value) + p(0) + b"\x55") for label, value in (
        ("zero-to-one", 1), ("one-to-two", 2),
        ("two-to-two", 2), ("two-to-zero", 0)))
    add(Case("sstore-transitions", "storage", sstore_control,
             sstore_targets, 4, detail="refunds do not increase GAS; they are not measured"))
    add(access("tload-slot0", 0x5c, (0,), 1, detail="transient slot zero"))
    add(Case("tstore-transitions", "transient", sstore_control,
             (("zero-to-one", p(1) + p(0) + b"\x5d"),
              ("one-to-two", p(2) + p(0) + b"\x5d"),
              ("two-to-zero", p(0) + p(0) + b"\x5d")), 4))

    for create2 in (False, True):
        for size in (0, 1, 32, 33, 256, 1024):
            # Child bytes are STOP followed by STOP padding. The init code
            # itself is copied to memory before GAS. Its execution cost is 0.
            # A PUSH2 offset makes the source location independent of size.
            prefix = p(size) + b"\x61\x00\x00" + p(0) + b"\x39"
            args = ((0,) if create2 else ()) + (size, 0, 0)
            pushes = b"".join(p(x) for x in args)
            op = b"\xf5" if create2 else b"\xf0"
            control = pushes + b"\x50" * len(args)
            target = pushes + op + b"\x50"
            # CODECOPY source offset is the start of the appended child.
            dummy = Case("", "", control, (("operation", target),), 2 * (len(args) - 1))
            timer = encode(dummy)
            source = len(prefix) + len(timer)
            prefix = p(size) + push_int(source, 2) + p(0) + b"\x39"
            name = f"{'create2' if create2 else 'create'}-{size}-bytes"
            add(Case(name, "create", control, (("operation", target),),
                     2 * (len(args) - 1), prefix,
                     "zero-value child; STOP-only init code; zero runtime bytes",
                     b"\x00" * size))
    return cases


def encode(case: Case) -> bytes:
    # Leave each measured delta on the stack until after the last timer. This
    # avoids MSTORE between measurements changing memory-expansion cases.
    code = bytearray(case.prelude)
    for body in (case.control,) + tuple(target for _, target in case.targets):
        code.extend(b"\x5a" + body + b"\x5a\x90\x03")
    count = 1 + len(case.targets)
    for index in reversed(range(count)):
        code.extend(p(index * 32) + b"\x52")
    code.extend(p(count * 32) + p(0) + b"\xf3" + case.suffix)
    return bytes(code)


def decode(case: Case, response: dict) -> dict:
    body = rpc_body(response)
    if body is None:
        return {"status": "transport-error", "raw": response.get("transport_error")}
    if "error" in body:
        error = body["error"]
        return {"status": "execution-failure" if is_evm_execution_error(response) else "rpc-rejected",
                "error": error}
    raw = body.get("result")
    count = 1 + len(case.targets)
    if not isinstance(raw, str) or not raw.startswith("0x") or len(raw) != 2 + 64 * count:
        return {"status": "malformed-return", "raw": raw}
    words = [int(raw[2 + 64 * i:2 + 64 * (i + 1)], 16) for i in range(count)]
    control = words[0]
    if control < 2:
        return {"status": "invalid-control", "raw_words": words}
    return {"status": "measured", "raw_words": words,
            "control_gas": control - 2,
            "values": {label: words[i + 1] - control + case.correction
                       for i, (label, _) in enumerate(case.targets)}}


def write_json(path: pathlib.Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def call_record(client: RpcClient, method: str, params: list[object]) -> dict:
    request, response = client.call(method, params)
    # Response headers can contain Set-Cookie bot tokens. JSON-RPC body and
    # HTTP status are the raw evidence needed here; do not persist headers.
    response.pop("headers", None)
    return {"request": request, "response": response,
            "observed_at": dt.datetime.now(dt.timezone.utc).isoformat()}


def run_chain(name: str, cases: dict[str, Case], out: pathlib.Path,
              phase: str, primary: dict | None) -> dict:
    config = REGISTRY[name]
    entries = config.get("rpcs", [])
    index = 1 if phase == "secondary" else 0
    if len(entries) <= index:
        result = {"chain": name, "phase": phase,
                  "status": "no-secondary-rpc" if index else "no-public-rpc",
                  "reason": config.get("rpc_status") if index == 0 else "No second endpoint in registry",
                  "cases": {}}
        write_json(out / f"{name}.json", result)
        return result
    endpoint = entries[index]
    client = RpcClient(endpoint["url"])
    chain_id = call_record(client, "eth_chainId", [])
    height = call_record(client, "eth_blockNumber", [])
    height_body = rpc_body(height["response"]) or {}
    tag = height_body.get("result", "latest")
    header = call_record(client, "eth_getBlockByNumber", [tag, False])
    block = (rpc_body(header["response"]) or {}).get("result")
    header_retry = None
    if not isinstance(block, dict):
        header_retry = call_record(client, "eth_getBlockByNumber", ["latest", False])
        block = (rpc_body(header_retry["response"]) or {}).get("result")
        if isinstance(block, dict):
            tag = "latest"
    number = int(block["number"], 16) if isinstance(block, dict) and isinstance(block.get("number"), str) else None
    observed_id = (rpc_body(chain_id["response"]) or {}).get("result")
    result = {"chain": name, "phase": phase, "status": "ok", "rpc": endpoint,
              "expected_chain_id": config["chain_id"], "observed_chain_id": observed_id,
              "block": block, "context": {"eth_chainId": chain_id,
              "eth_blockNumber": height, "eth_getBlockByNumber": header,
              "eth_getBlockByNumber_latest_retry": header_retry},
              "cases": {}, "observed_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    if observed_id != hex(config["chain_id"]) or number is None:
        result["status"] = "endpoint-context-error"
        write_json(out / f"{name}.json", result)
        return result
    if phase == "confirm" and primary is not None:
        first_number = primary.get("block", {}).get("number")
        first_height = int(first_number, 16) if isinstance(first_number, str) else None
        if first_height is None or number <= first_height:
            result["status"] = "no-later-block"
            write_json(out / f"{name}.json", result)
            return result
    for case in cases.values():
        tx = {"data": "0x" + encode(case).hex(), "gas": "0x1c9c380"}
        raw = call_record(client, "eth_call", [tx, tag])
        attempts = [raw]
        body = rpc_body(raw["response"]) or {}
        message = str(body.get("error", {}).get("message", "")).lower() if isinstance(body.get("error"), dict) else ""
        if tag != "latest" and ("quantity not supported" in message or "missing trie node" in message):
            # Some public endpoints reject numeric tags or lack state at a
            # recent height. Keep the rejection and mark the retry unpinned.
            if "quantity not supported" in message:
                tag = "latest"
            raw = call_record(client, "eth_call", [tx, "latest"])
            attempts.append(raw)
        result["cases"][case.name] = {"family": case.family, "detail": case.detail,
              "correction": case.correction, "block_tag": raw["request"]["params"][1],
              "bytecode": tx["data"], "raw": raw, "attempts": attempts,
              "interpretation": decode(case, raw["response"])}
    write_json(out / f"{name}.json", result)
    return result


def load_initial(out: pathlib.Path) -> dict[str, dict]:
    first = out / "initial"
    return {name: json.loads((first / f"{name}.json").read_text())
            for name in REGISTRY if (first / f"{name}.json").exists()}


def difference_names(name: str, first: dict[str, dict]) -> list[str]:
    baseline = first["ethereum"]["cases"]
    current = first[name]["cases"]
    selected = []
    for case_name, cell in current.items():
        ours = cell["interpretation"]
        eth = baseline.get(case_name, {}).get("interpretation", {})
        if ours.get("status") == "measured" and eth.get("status") == "measured" and ours["values"] != eth["values"]:
            selected.append(case_name)
    return selected


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=TODAY)
    parser.add_argument("--phase", choices=("initial", "confirm", "secondary"), default="initial")
    parser.add_argument("--chains", help="comma-separated registry names")
    parser.add_argument("--workers", type=int, default=8)
    args = parser.parse_args()
    out = ROOT / "results" / args.date / "gas-schedule"
    names = list(REGISTRY) if not args.chains else [n.strip() for n in args.chains.split(",") if n.strip()]
    unknown = set(names) - set(REGISTRY)
    if unknown:
        parser.error(f"unknown chains: {sorted(unknown)}")
    all_cases = build_cases()
    first = load_initial(out) if args.phase != "initial" else {}
    if args.phase != "initial" and ("ethereum" not in first or any(n not in first for n in names)):
        parser.error("initial phase must exist for Ethereum and every selected chain")

    def work(name: str) -> tuple[str, dict]:
        selected = all_cases if args.phase == "initial" else {
            n: all_cases[n] for n in difference_names(name, first)}
        result = run_chain(name, selected, out / args.phase,
                           args.phase, first.get(name))
        return name, result

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(args.workers, len(names))) as pool:
        for name, result in pool.map(work, names):
            statuses = {}
            for cell in result["cases"].values():
                status = cell["interpretation"]["status"]
                statuses[status] = statuses.get(status, 0) + 1
            print(name, result["status"], len(result["cases"]), statuses, flush=True)
    print(f"wrote {out / args.phase}")
    return 0


if __name__ == "__main__":
    sys.exit(main())

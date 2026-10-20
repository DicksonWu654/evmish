#!/usr/bin/env python3
"""Run read-only EVM behavior probes against every registry entry.

The transaction object for creation probes deliberately omits ``to``.  The
bytes are executed as contract-creation init code without publishing a
transaction.  Direct oracle and account probes are also read-only RPC calls.
"""

from __future__ import annotations

import argparse
import concurrent.futures
import datetime as dt
import json
import pathlib
import re
import sys
import time
import urllib.error
import urllib.request

from keccak import keccak256


ROOT = pathlib.Path(__file__).resolve().parent.parent
ENDPOINTS = ROOT / "probes" / "chains.json"
DEFAULT_DATE = "2026-10-18"
REQUEST_INTERVAL = 0.60  # <= 2 requests/second per endpoint
MAX_WORKERS = 8
USER_AGENT = "evm-divergence-probe/0.3 (read-only RPC)"
WORD_BYTES = 32

# These probes read execution-block context. They use the latest tag and are
# checked twice with the same tag so an endpoint that ignores historical tags
# cannot create a catalog divergence.
BLOCK_CONTEXT_PROBES = {
    "number",
    "basefee",
    "prevrandao",
    "coinbase",
    "gaslimit",
    "timestamp",
    "blockhash-n-minus-1",
    "blockhash-n-minus-256",
    "blockhash-n-minus-257",
}


SPECIAL_ACCOUNTS = {
    # Sender observed in a type-4 transaction's latest Ethereum block; its
    # code is checked at run time and the 0xef0100 prefix is recorded if live.
    "eoa": "0x4337005db25dbad41da5692ba1188751ee5d98b6",
    "empty": "0x9baeb70184075f3ea43e6e8160ec2f162da8d28b",
    "delegated-7702": "0x4de23f3f0fb3318287378adbde030cf61714b2f3",
    "system-contract": "0x0000000000000000000000000000000000000064",
}


def push_int(value: int, width: int | None = None) -> bytes:
    """Encode a positive integer with PUSH1..PUSH32 (zero uses PUSH1)."""
    if value < 0:
        raise ValueError("push_int only accepts non-negative integers")
    if width is None:
        width = max(1, (value.bit_length() + 7) // 8)
    if not 1 <= width <= 32 or value >= 1 << (8 * width):
        raise ValueError(f"integer does not fit PUSH{width}: {value}")
    return bytes([0x5F + width]) + value.to_bytes(width, "big")


def push_bytes(value: bytes) -> bytes:
    if not value:
        return push_int(0)
    if len(value) > 32:
        raise ValueError("push_bytes accepts at most 32 bytes")
    return bytes([0x5F + len(value)]) + value


def return_word(opcode: int) -> bytes:
    return bytes([opcode]) + push_int(0) + b"\x52" + push_int(WORD_BYTES) + push_int(0) + b"\xf3"


def return_words(sequence: bytes, count: int) -> bytes:
    return sequence + push_int(count * WORD_BYTES) + push_int(0) + b"\xf3"


def blockhash_probe(depth: int) -> bytes:
    return return_word(0x43)[:-len(push_int(0) + b"\x52" + push_int(WORD_BYTES) + push_int(0) + b"\xf3")] + push_int(depth) + b"\x03\x40" + push_int(0) + b"\x52" + push_int(WORD_BYTES) + push_int(0) + b"\xf3"


def mstore_chunks(data: bytes, offset: int = 0) -> bytes:
    code = bytearray()
    for start in range(0, len(data), WORD_BYTES):
        chunk = data[start : start + WORD_BYTES].ljust(WORD_BYTES, b"\0")
        code.extend(push_bytes(chunk))
        code.extend(push_int(offset + start))
        code.append(0x52)
    return bytes(code)


def precompile_probe(address: int, calldata: bytes) -> bytes:
    """Call a precompile and return [CALL status, first 64 output bytes]."""
    code = bytearray(mstore_chunks(calldata))
    # Keep output away from calldata (the largest vector is 131 bytes).
    output_offset = 256
    # CALL pops value, input offset/size, output offset/size, and target/gas.
    code.extend(push_int(64))
    code.extend(push_int(output_offset))
    code.extend(push_int(len(calldata)))
    code.extend(push_int(0))
    code.extend(push_int(0))
    code.extend(push_int(address, width=20))
    code.append(0x5A)  # GAS
    code.append(0xF1)  # CALL
    code.extend(push_int(0))
    code.append(0x52)
    return return_words(bytes(code), 10)  # status + output words (with safe gap)


def create_child_init() -> bytes:
    # Runtime returns one zero word.  This init code is also the CREATE2 hash
    # input used by the formula check.
    return bytes.fromhex("600060005260206000f3")


def create_probe(create2: bool) -> bytes:
    child = create_child_init()
    child_offset = 64
    # Fixed-width offset makes the prefix length stable for CODECOPY.
    prefix = bytearray(b"\x30" + push_int(0) + b"\x52")  # ADDRESS at word 0
    prefix.extend(push_int(len(child)))
    prefix.extend(push_int(0, width=2))  # replaced below with child offset
    prefix.extend(push_int(child_offset))
    prefix.append(0x39)  # CODECOPY
    if create2:
        prefix.extend(push_int(0x42, width=32))  # salt
    prefix.extend(push_int(len(child)))
    prefix.extend(push_int(child_offset))
    prefix.extend(push_int(0))
    prefix.append(0xF5 if create2 else 0xF0)
    prefix.extend(push_int(WORD_BYTES))
    prefix.append(0x52)
    prefix.extend(push_int(64))
    prefix.extend(push_int(0))
    prefix.append(0xF3)
    # The CODECOPY source offset is the first byte after this prefix.
    source_offset = len(prefix)
    rebuilt = bytearray(b"\x30" + push_int(0) + b"\x52")
    rebuilt.extend(push_int(len(child)))
    rebuilt.extend(push_int(source_offset, width=2))
    rebuilt.extend(push_int(child_offset))
    rebuilt.append(0x39)
    if create2:
        rebuilt.extend(push_int(0x42, width=32))
    rebuilt.extend(push_int(len(child)))
    rebuilt.extend(push_int(child_offset))
    rebuilt.extend(push_int(0))
    rebuilt.append(0xF5 if create2 else 0xF0)
    rebuilt.extend(push_int(WORD_BYTES))
    rebuilt.append(0x52)
    rebuilt.extend(push_int(64))
    rebuilt.extend(push_int(0))
    rebuilt.append(0xF3)
    return bytes(rebuilt) + child


def oversized_create_probe(runtime_size: int = 24577) -> bytes:
    runtime = b"\0" * runtime_size
    runtime_width = max(2, (runtime_size.bit_length() + 7) // 8)
    # Child init: CODECOPY the appended runtime, then RETURN it.
    child_prefix = bytearray()
    child_prefix.extend(push_int(runtime_size, width=runtime_width))
    child_prefix.extend(push_int(0, width=2))  # runtime offset, replaced below
    child_prefix.extend(push_int(0))
    child_prefix.append(0x39)
    child_prefix.extend(push_int(runtime_size, width=runtime_width))
    child_prefix.extend(push_int(0))
    child_prefix.append(0xF3)
    runtime_offset = len(child_prefix)
    child_prefix = bytearray()
    child_prefix.extend(push_int(runtime_size, width=runtime_width))
    child_prefix.extend(push_int(runtime_offset, width=2))
    child_prefix.extend(push_int(0))
    child_prefix.append(0x39)
    child_prefix.extend(push_int(runtime_size, width=runtime_width))
    child_prefix.extend(push_int(0))
    child_prefix.append(0xF3)
    child = bytes(child_prefix) + runtime

    parent_prefix = bytearray()
    child_width = max(2, (len(child).bit_length() + 7) // 8)
    parent_prefix.extend(push_int(len(child), width=child_width))
    parent_prefix.extend(push_int(0, width=2))
    parent_prefix.extend(push_int(0))
    parent_prefix.append(0x39)
    parent_prefix.extend(push_int(len(child), width=child_width))
    parent_prefix.extend(push_int(0))
    parent_prefix.extend(push_int(0))
    parent_prefix.append(0xF0)
    parent_prefix.extend(push_int(0))
    parent_prefix.append(0x52)
    parent_prefix.extend(push_int(WORD_BYTES))
    parent_prefix.extend(push_int(0))
    parent_prefix.append(0xF3)
    source_offset = len(parent_prefix)
    rebuilt = bytearray()
    rebuilt.extend(push_int(len(child), width=child_width))
    rebuilt.extend(push_int(source_offset, width=2))
    rebuilt.extend(push_int(0))
    rebuilt.append(0x39)
    rebuilt.extend(push_int(len(child), width=child_width))
    rebuilt.extend(push_int(0))
    rebuilt.extend(push_int(0))
    rebuilt.append(0xF0)
    rebuilt.extend(push_int(0))
    rebuilt.append(0x52)
    rebuilt.extend(push_int(WORD_BYTES))
    rebuilt.extend(push_int(0))
    rebuilt.append(0xF3)
    return bytes(rebuilt) + child


def extcode_probe(address: str) -> bytes:
    raw = bytes.fromhex(address[2:])
    code = bytearray()
    code.extend(push_bytes(raw))
    code.append(0x3B)  # EXTCODESIZE
    code.extend(push_int(0))
    code.append(0x52)
    code.extend(push_bytes(raw))
    code.append(0x3F)  # EXTCODEHASH
    code.extend(push_int(WORD_BYTES))
    code.append(0x52)
    return return_words(bytes(code), 2)


def gas_access_probe(address: str, estimate: bool = False) -> bytes:
    raw = bytes.fromhex(address[2:])
    code = bytearray()
    code.extend(b"\x5A")  # before
    code.extend(push_int(0))
    code.append(0x52)
    code.extend(push_bytes(raw))
    code.extend(b"\x3B\x5A")  # cold EXTCODESIZE, after
    code.extend(push_int(WORD_BYTES))
    code.append(0x52)
    if not estimate:
        code.extend(push_bytes(raw))
        code.extend(b"\x3B\x5A")  # warm EXTCODESIZE, after
        code.extend(push_int(2 * WORD_BYTES))
        code.append(0x52)
        return return_words(bytes(code), 3)
    return return_words(bytes(code), 2)


def build_probe_specs() -> dict[str, dict]:
    specs: dict[str, dict] = {
        "push0": {"data": "0x5f60005260206000f3", "meaning": "PUSH0 returns zero.", "decode": "uint256"},
        "number": {"data": "0x4360005260206000f3", "meaning": "NUMBER (block.number).", "decode": "uint256"},
        "basefee": {"data": "0x4860005260206000f3", "meaning": "BASEFEE.", "decode": "uint256"},
        "chainid": {"data": "0x4660005260206000f3", "meaning": "CHAINID.", "decode": "uint256"},
        "deliberate-invalid": {"data": "0xfe", "meaning": "Control probe: INVALID must fail in the VM.", "decode": "none"},
        "tstore-tload": {"data": "0x602a60015d60015c60005260206000f3", "meaning": "TSTORE then TLOAD returns 42.", "decode": "uint256", "vector": "key=1,value=42"},
        "mcopy": {"data": "0x602a6000526020600060205e60206020f3", "meaning": "MCOPY copies a 32-byte word and returns 42.", "decode": "uint256", "vector": "memory[0]=42; copy 0 -> 32"},
        "blobhash": {"data": "0x60004960005260206000f3", "meaning": "BLOBHASH(0) in a no-blob eth_call context.", "decode": "uint256"},
        "blobbasefee": {"data": "0x4a60005260206000f3", "meaning": "BLOBBASEFEE for the execution block.", "decode": "uint256"},
        "prevrandao": {"data": "0x4460005260206000f3", "meaning": "PREVRANDAO/DIFFICULTY value.", "decode": "uint256"},
        "coinbase": {"data": "0x4160005260206000f3", "meaning": "COINBASE/MINER value.", "decode": "uint256"},
        "gaslimit": {"data": "0x4560005260206000f3", "meaning": "GASLIMIT value.", "decode": "uint256"},
        "timestamp": {"data": "0x4260005260206000f3", "meaning": "TIMESTAMP value.", "decode": "uint256"},
        "blockhash-n-minus-1": {"data": "0x436001034060005260206000f3", "meaning": "BLOCKHASH(NUMBER-1).", "decode": "uint256", "vector": "depth=1"},
        "blockhash-n-minus-256": {"data": "0x43610100034060005260206000f3", "meaning": "BLOCKHASH(NUMBER-256).", "decode": "uint256", "vector": "depth=256"},
        "blockhash-n-minus-257": {"data": "0x43610101034060005260206000f3", "meaning": "BLOCKHASH(NUMBER-257), normally zero by EVM rule.", "decode": "uint256", "vector": "depth=257"},
        "create": {"data": "0x" + create_probe(False).hex(), "meaning": "CREATE returns creator and child address words.", "decode": "words", "formula": "create"},
        "create2": {"data": "0x" + create_probe(True).hex(), "meaning": "CREATE2 returns creator and child address words.", "decode": "words", "formula": "create2", "vector": "salt=0x42"},
        "oversized-runtime-create": {"data": "0x" + oversized_create_probe().hex(), "meaning": "CREATE attempts a 24,577-byte runtime; zero means the size limit rejected it.", "decode": "uint256", "vector": "runtime_bytes=24577", "gas": "0x989680"},
        "cold-warm-extcodesize": {"data": "0x" + gas_access_probe(SPECIAL_ACCOUNTS["eoa"]).hex(), "meaning": "GAS deltas for cold then warm EXTCODESIZE.", "decode": "gas-words", "vector": "same EOA address twice"},
        "estimate-gas": {"data": "0x" + gas_access_probe(SPECIAL_ACCOUNTS["eoa"], estimate=True).hex(), "meaning": "eth_estimateGas compared with GAS opcode delta from eth_call.", "decode": "gas-words", "estimate_gas": True},
    }

    vectors = {
        0x01: ("ecrecover", bytes(128), "invalid-zero-signature"),
        0x02: ("sha256", b"abc", "sha256(abc)"),
        0x03: ("ripemd160", b"abc", "ripemd160(abc)"),
        0x04: ("identity", b"abc", "identity(abc)"),
        0x05: ("modexp", (1).to_bytes(32, "big") * 3 + b"\x02\x03\x05", "2^3 mod 5"),
        0x06: ("bn128-add", bytes(128), "infinity + infinity"),
        0x07: ("bn128-mul", bytes(96), "infinity * 0"),
        0x08: ("bn128-pairing", b"", "empty pairing product"),
        0x09: ("blake2f", b"", "invalid-length control"),
        0x0A: ("kzg-point-evaluation", b"", "invalid-length control"),
    }
    for address in range(0x01, 0x12):
        name, calldata, vector = vectors.get(address, (f"address-{address:02x}", b"", "empty input"))
        specs[f"precompile-0x{address:02x}-{name}"] = {
            "data": "0x" + precompile_probe(address, calldata).hex(),
            "meaning": f"CALL precompile/address 0x{address:02x}; return status and output words.",
            "decode": "precompile-words",
            "vector": vector,
            "precompile_address": f"0x{address:02x}",
        }
    specs["precompile-0x100-p256verify"] = {
        "data": "0x" + precompile_probe(0x100, b"").hex(),
        "meaning": "CALL address 0x100 (P256VERIFY candidate); return status and output words.",
        "decode": "precompile-words",
        "vector": "empty-input control; Ethereum baseline has no deployed P256VERIFY code",
        "precompile_address": "0x100",
    }
    for label, address in SPECIAL_ACCOUNTS.items():
        specs[f"extcode-{label}"] = {
            "data": "0x" + extcode_probe(address).hex(),
            "meaning": f"EXTCODESIZE and EXTCODEHASH for {label} candidate {address}.",
            "decode": "extcode-words",
            "address": address,
        }
    return specs


ORACLE_CALLS = {
    "op-mainnet": [
        {"name": "op-gaspriceoracle-l1BaseFee", "to": "0x420000000000000000000000000000000000000F", "data": "0x519b4bd3", "method": "l1BaseFee()"},
        {"name": "op-gaspriceoracle-getL1Fee", "to": "0x420000000000000000000000000000000000000F", "data": "0x49948e0e" + "00" * 31 + "20" + "00" * 32, "method": "getL1Fee(bytes) with empty bytes"},
    ],
    "arbitrum-one": [
        {"name": "arb-gasinfo-l1-base-fee-estimate", "to": "0x000000000000000000000000000000000000006C", "data": "0xf5d6ded7", "method": "getL1BaseFeeEstimate()"},
        {"name": "arb-gasinfo-l1-gas-price-estimate", "to": "0x000000000000000000000000000000000000006C", "data": "0x055f362f", "method": "getL1GasPriceEstimate()"},
    ],
    "zksync-era": [
        {"name": "zksync-system-contract-8008", "to": "0x0000000000000000000000000000000000008008", "data": "0x", "method": "system-contract read candidate"},
    ],
    "scroll": [
        {"name": "scroll-l1-fee-oracle", "to": "0x5300000000000000000000000000000000000002", "data": "0x3fd1263d", "method": "l1Fee(bytes) candidate"},
    ],
    "linea": [
        {"name": "linea-fee-oracle", "to": "0x5300000000000000000000000000000000000002", "data": "0x", "method": "Linea fee-oracle system-contract candidate"},
    ],
}


def probe_specs() -> dict[str, dict]:
    return build_probe_specs()


class RpcClient:
    def __init__(self, url: str):
        self.url = url
        self.next_request_at = 0.0
        self.request_id = 0

    def call(self, method: str, params: list[object]) -> tuple[dict, dict]:
        now = time.monotonic()
        if now < self.next_request_at:
            time.sleep(self.next_request_at - now)
        self.request_id += 1
        request = {"jsonrpc": "2.0", "id": self.request_id, "method": method, "params": params}
        body = json.dumps(request, separators=(",", ":")).encode("utf-8")
        req = urllib.request.Request(
            self.url,
            data=body,
            headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
            method="POST",
        )
        self.next_request_at = time.monotonic() + REQUEST_INTERVAL
        for attempt in range(4):
            try:
                with urllib.request.urlopen(req, timeout=45) as response:
                    raw = response.read().decode("utf-8", errors="replace")
                    return request, {"http_status": response.status, "headers": dict(response.headers.items()), "body": json.loads(raw)}
            except urllib.error.HTTPError as exc:
                raw = exc.read().decode("utf-8", errors="replace")
                if exc.code == 429 and attempt < 3:
                    time.sleep(2 ** (attempt + 1))
                    continue
                try:
                    parsed = json.loads(raw)
                except json.JSONDecodeError:
                    parsed = raw
                return request, {"http_status": exc.code, "headers": dict(exc.headers.items()), "body": parsed}
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                if attempt < 3:
                    time.sleep(2 ** attempt)
                    continue
                return request, {"transport_error": f"{type(exc).__name__}: {exc}"}
        raise AssertionError("unreachable")


def as_int(value: object) -> int | None:
    if isinstance(value, int):
        return value
    if not isinstance(value, str):
        return None
    try:
        return int(value, 16) if value.startswith("0x") else int(value)
    except ValueError:
        return None


def rpc_body(response: dict) -> dict | None:
    body = response.get("body")
    return body if isinstance(body, dict) else None


def response_error(response: dict) -> tuple[str, str] | None:
    if "transport_error" in response:
        return "transport", str(response["transport_error"])
    status = response.get("http_status")
    if isinstance(status, int) and status >= 400:
        return "http", f"HTTP {status}"
    body = rpc_body(response)
    if body is None:
        return "json-shape", "non-object JSON-RPC response"
    if "error" in body:
        error = body["error"]
        if isinstance(error, dict):
            return "jsonrpc", f"{error.get('code')}: {error.get('message', '')}"
        return "jsonrpc", str(error)
    return None


def is_evm_execution_error(response: dict) -> bool:
    error = response_error(response)
    if error is None or error[0] in {"transport", "http", "json-shape"}:
        return False
    lowered = error[1].lower()
    return any(marker in lowered for marker in ("execution", "invalid opcode", "invalidfeopcode", "revert", "out of gas", "vm error", "stack underflow", "stack overflow", "evm error"))


def classify(response: dict, spec: dict | None = None) -> dict:
    error = response_error(response)
    if error is not None:
        kind, reason = error
        if is_evm_execution_error(response):
            expected = spec is not None and spec.get("decode") == "none"
            return {"status": "execution-failure-expected" if expected else "execution-failure", "error_class": "evm-execution", "reason": reason}
        return {"status": "rpc-rejected", "error_class": kind, "reason": reason}
    body = rpc_body(response)
    result = body.get("result") if body else None
    if not isinstance(result, str) or not result.startswith("0x"):
        return {"status": "rpc-rejected", "error_class": "json-shape", "reason": "missing hex result"}
    return {"status": "ok", "error_class": None, "raw_return": result, "uint256": as_int(result)}


def classify_context(response: dict) -> dict:
    error = response_error(response)
    if error is None:
        body = rpc_body(response)
        return {"status": "ok" if body and "result" in body else "rpc-rejected", "error_class": None}
    return {"status": "rpc-rejected", "error_class": error[0], "reason": error[1]}


def decode_words(raw: str) -> list[int]:
    payload = bytes.fromhex(raw[2:])
    return [int.from_bytes(payload[i : i + WORD_BYTES], "big") for i in range(0, len(payload), WORD_BYTES) if len(payload[i : i + WORD_BYTES]) == WORD_BYTES]


def rlp_encode(value: object) -> bytes:
    if isinstance(value, int):
        if value == 0:
            return b""
        return value.to_bytes((value.bit_length() + 7) // 8, "big")
    if isinstance(value, bytes):
        if len(value) == 1 and value[0] < 0x80:
            return value
        if len(value) <= 55:
            return bytes([0x80 + len(value)]) + value
        length = len(value).to_bytes((len(value).bit_length() + 7) // 8, "big")
        return bytes([0xB7 + len(length)]) + length + value
    if isinstance(value, list):
        payload = b"".join(rlp_encode(item) if not isinstance(item, int) else rlp_encode(rlp_encode(item)) for item in value)
        # The integer branch above is intentionally handled separately below.
        payload = b"".join(rlp_encode(item if not isinstance(item, int) else rlp_encode(item)) for item in value)
        if len(payload) <= 55:
            return bytes([0xC0 + len(payload)]) + payload
        length = len(payload).to_bytes((len(payload).bit_length() + 7) // 8, "big")
        return bytes([0xF7 + len(length)]) + length + payload
    raise TypeError(value)


def rlp_list(items: list[object]) -> bytes:
    encoded = bytearray()
    for item in items:
        if isinstance(item, int):
            raw = rlp_encode(item)
            encoded.extend(rlp_encode(raw))
        else:
            encoded.extend(rlp_encode(item))
    if len(encoded) <= 55:
        return bytes([0xC0 + len(encoded)]) + bytes(encoded)
    length = len(encoded).to_bytes((len(encoded).bit_length() + 7) // 8, "big")
    return bytes([0xF7 + len(length)]) + length + bytes(encoded)


def add_formula_interpretation(entry: dict, spec: dict) -> None:
    interpretation = entry["interpretation"]
    raw = interpretation.get("raw_return")
    if interpretation.get("status") != "ok" or not raw or spec.get("decode") != "words":
        return
    words = decode_words(raw)
    interpretation["words"] = words
    if len(words) < 2:
        return
    creator = words[0].to_bytes(32, "big")[-20:]
    child = words[1].to_bytes(32, "big")[-20:]
    child_init = create_child_init()
    if spec.get("formula") == "create2":
        salt = (0x42).to_bytes(32, "big")
        expected = keccak256(b"\xff" + creator + salt + keccak256(child_init))[-20:]
        interpretation["formula"] = "keccak256(0xff ++ creator ++ salt ++ keccak256(init_code))[12:]"
        interpretation["formula_expected_child"] = "0x" + expected.hex()
        interpretation["formula_matches"] = child == expected
    else:
        candidates = []
        for nonce in (0, 1, 2):
            candidates.append("0x" + keccak256(rlp_list([creator, nonce]))[-20:].hex())
        interpretation["formula"] = "keccak256(rlp([creator, nonce]))[12:]"
        interpretation["formula_nonce_candidates"] = candidates
        interpretation["formula_matches"] = "0x" + child.hex() in candidates


def add_decoded_interpretation(entry: dict, spec: dict) -> None:
    interpretation = entry["interpretation"]
    raw = interpretation.get("raw_return")
    if interpretation.get("status") != "ok" or not raw:
        return
    if spec.get("decode") in {"words", "gas-words", "extcode-words", "precompile-words"}:
        words = decode_words(raw)
        interpretation["words"] = words
        if spec.get("decode") == "gas-words" and len(words) >= 2:
            interpretation["gas_delta"] = words[0] - words[1]
            if len(words) >= 3:
                interpretation["warm_gas_delta"] = words[1] - words[2]
        if spec.get("decode") == "extcode-words" and len(words) >= 2:
            interpretation["extcodesize"] = words[0]
            interpretation["extcodehash"] = "0x" + words[1].to_bytes(32, "big").hex()
        if spec.get("decode") == "precompile-words" and words:
            interpretation["precompile_call_status"] = words[0]
            output_start = 256 // WORD_BYTES
            interpretation["precompile_output_words"] = words[output_start : output_start + 2]
            interpretation["precompile_output_hex"] = [f"0x{word.to_bytes(WORD_BYTES, 'big').hex()}" for word in words[output_start : output_start + 2]]
    add_formula_interpretation(entry, spec)


def write_json(path: pathlib.Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def annotate_header_comparisons(probes: dict[str, dict], block: dict | None) -> None:
    if not block:
        return
    expected = {
        "number": as_int(block.get("number")),
        "timestamp": as_int(block.get("timestamp")),
        "basefee": as_int(block.get("baseFeePerGas")),
        "gaslimit": as_int(block.get("gasLimit")),
        "coinbase": as_int(block.get("miner")),
        "prevrandao": as_int(block.get("prevRandao") or block.get("mixHash")),
    }
    for name, value in expected.items():
        interpretation = probes.get(name, {}).get("interpretation", {})
        if interpretation.get("status") == "ok" and value is not None:
            interpretation["header_value"] = value
            interpretation["header_matches"] = interpretation.get("uint256") == value
    for name in ("blockhash-n-minus-257",):
        interpretation = probes.get(name, {}).get("interpretation", {})
        if interpretation.get("status") == "ok":
            interpretation["expected_zero_by_evm_depth_rule"] = True
            interpretation["matches_expected_zero"] = interpretation.get("uint256") == 0


def endpoint_slug(url: str) -> str:
    slug = re.sub(r"[^A-Za-z0-9]+", "-", url.removeprefix("https://").removeprefix("http://"))
    return slug.strip("-")[:80] or "endpoint"


def run_endpoint(
    chain_name: str,
    config: dict,
    rpc_entry: dict,
    chain_dir: pathlib.Path,
    observed_at: str,
    probe_names: list[str] | None = None,
    extra_specs: dict[str, dict] | None = None,
) -> dict:
    url = rpc_entry["url"]
    endpoint_dir = chain_dir / "endpoints" / endpoint_slug(url)
    raw_dir = endpoint_dir / "raw"
    client = RpcClient(url)
    all_specs = probe_specs()
    if extra_specs:
        all_specs = {**all_specs, **extra_specs}
    if probe_names is None:
        specs = all_specs
    else:
        unknown = sorted(set(probe_names) - set(all_specs))
        if unknown:
            raise ValueError(f"unknown probe(s): {', '.join(unknown)}")
        specs = {name: all_specs[name] for name in probe_names}
    context: dict[str, dict] = {}
    for method, params in (("eth_chainId", []), ("eth_blockNumber", [])):
        request, response = client.call(method, params)
        context[method] = {"request": request, "response": response, "interpretation": classify_context(response)}
        write_json(raw_dir / f"{method}.request.json", request)
        write_json(raw_dir / f"{method}.response.json", response)

    chain_id_hex = None
    block_number_hex = None
    body = rpc_body(context["eth_chainId"]["response"])
    if body:
        chain_id_hex = body.get("result")
    body = rpc_body(context["eth_blockNumber"]["response"])
    if body:
        block_number_hex = body.get("result")
    block_tag = block_number_hex if isinstance(block_number_hex, str) else "latest"
    request, response = client.call("eth_getBlockByNumber", [block_tag, False])
    context["eth_getBlockByNumber"] = {"request": request, "response": response, "interpretation": classify_context(response)}
    write_json(raw_dir / "eth_getBlockByNumber.request.json", request)
    write_json(raw_dir / "eth_getBlockByNumber.response.json", response)

    block = None
    body = rpc_body(response)
    if body and isinstance(body.get("result"), dict):
        header = body["result"]
        block = {
            "number": header.get("number"),
            "hash": header.get("hash"),
            "timestamp": header.get("timestamp"),
            "timestamp_unix": as_int(header.get("timestamp")),
            "baseFeePerGas": header.get("baseFeePerGas"),
            "gasLimit": header.get("gasLimit"),
            "gasLimit_uint256": as_int(header.get("gasLimit")),
            "mixHash": header.get("mixHash"),
            "prevRandao": header.get("prevRandao"),
            "miner": header.get("miner"),
            "blobGasUsed": header.get("blobGasUsed"),
            "excessBlobGas": header.get("excessBlobGas"),
        }

    # Block-context probes execute against latest and use the latest header
    # captured immediately before them. The same call/tag is repeated twice
    # for every context probe; moving responses are endpoint evidence, not VM
    # semantics. BASEFEE receives an explicit gas price so geth-style eth_call
    # simulation does not silently substitute zero.
    latest_request, latest_response = client.call("eth_getBlockByNumber", ["latest", False])
    context["eth_getBlockByNumber_latest"] = {
        "request": latest_request,
        "response": latest_response,
        "interpretation": classify_context(latest_response),
    }
    write_json(raw_dir / "eth_getBlockByNumber-latest.request.json", latest_request)
    write_json(raw_dir / "eth_getBlockByNumber-latest.response.json", latest_response)
    context_block = None
    latest_body = rpc_body(latest_response)
    if latest_body and isinstance(latest_body.get("result"), dict):
        header = latest_body["result"]
        context_block = {
            "number": header.get("number"),
            "hash": header.get("hash"),
            "timestamp": header.get("timestamp"),
            "timestamp_unix": as_int(header.get("timestamp")),
            "baseFeePerGas": header.get("baseFeePerGas"),
            "gasLimit": header.get("gasLimit"),
            "gasLimit_uint256": as_int(header.get("gasLimit")),
            "mixHash": header.get("mixHash"),
            "prevRandao": header.get("prevRandao"),
            "miner": header.get("miner"),
            "blobGasUsed": header.get("blobGasUsed"),
            "excessBlobGas": header.get("excessBlobGas"),
        }

    stability = {
        "tag": "latest",
        "status": "stable",
        "probes": {},
    }
    for name in sorted(BLOCK_CONTEXT_PROBES):
        spec = all_specs[name]
        stability_tx = {"data": spec["data"]}
        if name == "basefee":
            stability_tx["gasPrice"] = "0x1"
        stability_responses = []
        for index in (1, 2):
            stability_request, stability_response = client.call("eth_call", [stability_tx, "latest"])
            stability_responses.append(stability_response)
            write_json(raw_dir / f"block-tag-stability-{name}-{index}.request.json", stability_request)
            write_json(raw_dir / f"block-tag-stability-{name}-{index}.response.json", stability_response)
        bodies = [rpc_body(response) for response in stability_responses]
        comparable = all(isinstance(body, dict) for body in bodies)
        values = [body.get("result") if body else None for body in bodies]
        equal = comparable and bodies[0] == bodies[1]
        stability["probes"][name] = {
            "status": "stable" if equal else "unstable",
            "responses_equal": equal,
            "raw_returns": values,
        }
        if not equal:
            stability["status"] = "unstable"
    context["block_tag_stability"] = {
        "request": {"method": "eth_call", "params": [{"data": all_specs["number"]["data"]}, "latest"]},
        "response": stability,
        "interpretation": stability,
    }

    # Keep account-kind evidence alongside EXTCODE probes.  The delegated
    # candidate is checked for the EIP-7702 0xef0100 prefix on every endpoint.
    for label, address in SPECIAL_ACCOUNTS.items():
        method_name = f"eth_getCode_{label}"
        request, response = client.call("eth_getCode", [address, block_tag])
        code_result = rpc_body(response).get("result") if rpc_body(response) else None
        interpretation = classify_context(response)
        if isinstance(code_result, str):
            interpretation["code_length_bytes"] = max(0, (len(code_result) - 2) // 2)
            interpretation["eip7702_delegation_prefix"] = code_result.lower().startswith("0xef0100")
        context[method_name] = {"request": request, "response": response, "interpretation": interpretation, "address": address}
        write_json(raw_dir / f"{method_name}.request.json", request)
        write_json(raw_dir / f"{method_name}.response.json", response)

    probes: dict[str, dict] = {}
    for name, spec in specs.items():
        tx = {"data": spec["data"]}
        if spec.get("gas"):
            tx["gas"] = spec["gas"]
        execution_tag = "latest" if name in BLOCK_CONTEXT_PROBES else block_tag
        if name == "basefee":
            tx["gasPrice"] = "0x1"
        request, response = client.call("eth_call", [tx, execution_tag])
        entry = {
            "data": spec["data"],
            "meaning": spec["meaning"],
            "vector": spec.get("vector"),
            "block_tag": execution_tag,
            "request": request,
            "response": response,
            "interpretation": classify(response, spec),
        }
        add_decoded_interpretation(entry, spec)
        if spec.get("estimate_gas"):
            estimate_request, estimate_response = client.call("eth_estimateGas", [tx, execution_tag])
            entry["estimate_gas"] = {
                "request": estimate_request,
                "response": estimate_response,
                "interpretation": classify(estimate_response),
            }
            estimate_body = rpc_body(estimate_response)
            if estimate_body and isinstance(estimate_body.get("result"), str):
                entry["estimate_gas"]["interpretation"]["estimated_gas"] = as_int(estimate_body["result"])
            gas_interp = entry["interpretation"]
            if gas_interp.get("gas_delta") is not None:
                entry["estimate_gas"]["interpretation"]["actual_gas_delta_from_GAS_opcode"] = gas_interp["gas_delta"]
        probes[name] = entry
        safe_name = name.replace("/", "-")
        write_json(raw_dir / f"{safe_name}.request.json", request)
        write_json(raw_dir / f"{safe_name}.response.json", response)
        if entry.get("estimate_gas"):
            write_json(raw_dir / f"{safe_name}.estimateGas.request.json", entry["estimate_gas"]["request"])
            write_json(raw_dir / f"{safe_name}.estimateGas.response.json", entry["estimate_gas"]["response"])

    annotate_header_comparisons(probes, context_block or block)

    oracles: dict[str, dict] = {}
    for oracle in ORACLE_CALLS.get(chain_name, []):
        request, response = client.call("eth_call", [{"to": oracle["to"], "data": oracle["data"]}, block_tag])
        name = oracle["name"]
        oracles[name] = {
            "to": oracle["to"],
            "data": oracle["data"],
            "method": oracle["method"],
            "request": request,
            "response": response,
            "interpretation": classify(response),
        }
        write_json(raw_dir / f"oracle-{name}.request.json", request)
        write_json(raw_dir / f"oracle-{name}.response.json", response)

    probe_errors = sorted({entry["interpretation"]["error_class"] for entry in probes.values() if entry["interpretation"].get("error_class")})
    context_errors = sorted({entry["interpretation"]["error_class"] for entry in context.values() if entry["interpretation"].get("error_class")})
    oracle_errors = sorted({entry["interpretation"]["error_class"] for entry in oracles.values() if entry["interpretation"].get("error_class")})
    expected_hex = hex(config["chain_id"])
    chain_id_ok = chain_id_hex == expected_hex
    context_ok = chain_id_ok and block is not None
    if not chain_id_ok and chain_id_hex is not None:
        status = "chain-id-mismatch"
    elif not context_ok:
        status = "partial"
    elif any(entry["interpretation"]["status"] == "rpc-rejected" for entry in probes.values()):
        status = "degraded"
    else:
        status = "ok"
    reason = None
    if status != "ok":
        reason = "; ".join(part for part in (
            f"expected chain ID {expected_hex}, observed {chain_id_hex}" if not chain_id_ok else None,
            "block header unavailable" if block is None else None,
            "one or more probes were RPC-rejected" if any(entry["interpretation"]["status"] == "rpc-rejected" for entry in probes.values()) else None,
        ) if part)
    result = {
        "chain": chain_name,
        "status": status,
        "chain_id_expected": config["chain_id"],
        "chain_id_observed": chain_id_hex,
        "rpc": url,
        "rpc_source": rpc_entry.get("source"),
        "rpc_source_accessed": rpc_entry.get("source_accessed"),
        "observed_at": observed_at,
        "block": block,
        "block_context_block": context_block,
        "block_context_tag": "latest",
        "block_number": block_number_hex,
        "context": context,
        "account_candidates": SPECIAL_ACCOUNTS,
        "probes": probes,
        "oracles": oracles,
        "probe_count": len(probes),
        "error_classes": sorted(set(probe_errors + context_errors + oracle_errors)),
        "recorded_reason": reason,
        "evidence_dir": str(endpoint_dir.relative_to(ROOT)),
    }
    return result


def attempt_summary(result: dict) -> dict:
    return {
        "rpc": result.get("rpc"),
        "status": result.get("status"),
        "chain_id_observed": result.get("chain_id_observed"),
        "block_number": result.get("block_number"),
        "probe_count": result.get("probe_count", 0),
        "error_classes": result.get("error_classes", []),
        "recorded_reason": result.get("recorded_reason"),
        "evidence_dir": result.get("evidence_dir"),
    }


def run_chain(name: str, config: dict, output_root: pathlib.Path) -> dict:
    chain_dir = output_root / name
    observed_at = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    attempts: list[dict] = []
    selected: dict | None = None
    for rpc_entry in config.get("rpcs", []):
        try:
            result = run_endpoint(name, config, rpc_entry, chain_dir, observed_at)
            attempts.append(attempt_summary(result))
            if selected is None and result.get("chain_id_observed") == hex(config["chain_id"]):
                selected = result
        except Exception as exc:
            attempts.append({"rpc": rpc_entry.get("url"), "status": "runner-error", "chain_id_observed": None, "block_number": None, "probe_count": 0, "error_classes": ["runner"], "recorded_reason": f"{type(exc).__name__}: {exc}", "evidence_dir": None})
    if selected is None:
        result = {
            "chain": name,
            "status": "unavailable",
            "chain_id_expected": config["chain_id"],
            "chain_id_observed": None,
            "rpc": None,
            "rpc_source": config.get("rpc_source"),
            "rpc_source_accessed": config.get("rpc_source_accessed"),
            "observed_at": observed_at,
            "block": None,
            "block_number": None,
            "context": {},
            "account_candidates": SPECIAL_ACCOUNTS,
            "probes": {},
            "oracles": {},
            "probe_count": 0,
            "error_classes": sorted({e for attempt in attempts for e in attempt.get("error_classes", [])}),
            "recorded_reason": config.get("rpc_status") or ("All configured endpoints failed to return the expected chain ID; see attempts." if attempts else "No public RPC endpoint configured."),
            "attempts": attempts,
            "explorer": config.get("explorer"),
        }
    else:
        result = dict(selected)
        result["attempts"] = attempts
        result["explorer"] = config.get("explorer")
    write_json(chain_dir / f"{name}.json", result)
    return result


def answer_signature(entry: dict) -> tuple[str, int | None]:
    interpretation = entry.get("interpretation", {})
    raw = interpretation.get("raw_return")
    return interpretation.get("status", "not-run"), len(raw) if isinstance(raw, str) else None


def attach_known_answers(results: list[dict], date: str) -> None:
    baseline = next((result for result in results if result.get("chain") == "ethereum" and result.get("status") != "unavailable"), None)
    baseline_path = f"results/{date}/ethereum/ethereum.json"
    if baseline is None:
        return
    for result in results:
        for name, entry in result.get("probes", {}).items():
            base_entry = baseline.get("probes", {}).get(name)
            if base_entry is None:
                entry["known_answer"] = {"baseline_chain": "ethereum", "comparison": "not-in-baseline", "baseline_path": baseline_path}
                continue
            base_status, base_length = answer_signature(base_entry)
            status, length = answer_signature(entry)
            entry["known_answer"] = {
                "baseline_chain": "ethereum",
                "baseline_path": baseline_path,
                "baseline_status": base_status,
                "baseline_raw_return": base_entry.get("interpretation", {}).get("raw_return"),
                "status_matches": status == base_status,
                "return_shape_matches": length == base_length,
                "comparison": "same-status" if status == base_status else "different-status",
            }
        for name, oracle in result.get("oracles", {}).items():
            oracle["known_answer"] = {
                "baseline_chain": "ethereum",
                "baseline_path": baseline_path,
                "comparison": "chain-specific-not-applicable",
                "reason": "Ethereum baseline has no same-chain oracle predeploy; retain the direct response as the known observation.",
            }
        write_json(ROOT / "results" / date / result["chain"] / f"{result['chain']}.json", result)


def summary_row(result: dict, probe_names: list[str], date: str) -> dict:
    probes = result.get("probes", {})
    return {
        "chain": result.get("chain"),
        "expected_chain_id": result.get("chain_id_expected"),
        "status": result.get("status"),
        "rpc": result.get("rpc"),
        "block": (result.get("block") or {}).get("number"),
        "timestamp": (result.get("block") or {}).get("timestamp"),
        "probe_count": len(probes),
        "probe_status": {name: entry["interpretation"]["status"] for name, entry in probes.items()},
        "error_classes": result.get("error_classes", []),
        "recorded_reason": result.get("recorded_reason"),
        "evidence": str(pathlib.Path("results") / date / result.get("chain", "") / f"{result.get('chain', '')}.json"),
    }


def md_cell(value: object) -> str:
    return str(value if value not in (None, "") else "—").replace("|", "\\|").replace("\n", " ")


def write_summary(output_root: pathlib.Path, results: list[dict], date: str) -> None:
    probe_names = list(probe_specs())
    rows = [summary_row(result, probe_names, date) for result in sorted(results, key=lambda item: item.get("chain", ""))]
    write_json(output_root / "SUMMARY.json", {"date": date, "generated_at": dt.datetime.now(dt.timezone.utc).isoformat(), "probe_names": probe_names, "chain_count": len(rows), "chains": rows})
    baseline = next((result for result in results if result.get("chain") == "ethereum" and result.get("status") != "unavailable"), None)
    if baseline is not None:
        write_json(
            output_root / "KNOWN_ANSWERS.json",
            {
                "chain": "ethereum",
                "rpc": baseline.get("rpc"),
                "observed_at": baseline.get("observed_at"),
                "block": baseline.get("block"),
                "source_result": f"results/{date}/ethereum/ethereum.json",
                "probes": {
                    name: {
                        "vector": entry.get("vector"),
                        "data": entry.get("data"),
                        "status": entry.get("interpretation", {}).get("status"),
                        "raw_return": entry.get("interpretation", {}).get("raw_return"),
                        "interpretation": entry.get("interpretation", {}),
                    }
                    for name, entry in baseline.get("probes", {}).items()
                },
            },
        )
    lines = [
        f"# Probe coverage ({date})", "",
        f"The runner issued {len(probe_names)} read-only creation probes per endpoint-backed registry entry, plus account and chain-specific oracle reads. `ok` means the endpoint returned the expected chain ID and a block header; `degraded` and `partial` retain raw responses and reasons. `unavailable` is a recorded endpoint gap, not an assertion that the chain lacks a feature.",
        "The `evm-execution` error class is the expected `deliberate-invalid` control on otherwise healthy rows; RPC rejection is shown on the individual probe status.", "",
        f"Coverage: {len(rows)} registry entries; {sum(row['status'] != 'unavailable' for row in rows)} with endpoint results; {sum(row['status'] == 'unavailable' for row in rows)} with a recorded reason.", "",
        f"| Chain | Expected ID | Status | RPC | Block | Timestamp | Probes ({len(probe_names)}) | Error class | Recorded reason | Evidence |",
        "| --- | ---: | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for row in rows:
        statuses = row["probe_status"]
        probe_cell = "; ".join(f"{name}={statuses.get(name, 'not-run')}" for name in probe_names)
        lines.append("| " + " | ".join(md_cell(value) for value in (row["chain"], row["expected_chain_id"], row["status"], row["rpc"], row["block"], row["timestamp"], f"{row['probe_count']}/{len(probe_names)}; {probe_cell}", ", ".join(row["error_classes"]) or "—", row["recorded_reason"], row["evidence"])) + " |")
    (output_root / "SUMMARY.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("date", nargs="?", default=DEFAULT_DATE, help="results subdirectory (default: %(default)s)")
    parser.add_argument(
        "--chains",
        default=None,
        help="comma-separated registry names to run; default runs every configured chain",
    )
    args = parser.parse_args(argv[1:])
    date = args.date
    output_root = ROOT / "results" / date
    all_configs = json.loads(ENDPOINTS.read_text(encoding="utf-8"))
    if args.chains is not None:
        selected_names = [name.strip() for name in args.chains.split(",") if name.strip()]
        unknown = sorted(set(selected_names) - set(all_configs))
        if unknown:
            parser.error(f"unknown chain(s): {', '.join(unknown)}")
        if not selected_names:
            parser.error("--chains must contain at least one registry name")
        configs = {name: all_configs[name] for name in selected_names}
    else:
        configs = all_configs
    results: list[dict] = []
    workers = min(MAX_WORKERS, max(1, len(configs)))
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {executor.submit(run_chain, name, config, output_root): name for name, config in configs.items()}
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                result = {"chain": name, "status": "unavailable", "chain_id_expected": configs[name].get("chain_id"), "chain_id_observed": None, "rpc": None, "rpc_source": None, "rpc_source_accessed": None, "observed_at": dt.datetime.now(dt.timezone.utc).isoformat(), "block": None, "block_number": None, "context": {}, "account_candidates": SPECIAL_ACCOUNTS, "probes": {}, "oracles": {}, "probe_count": 0, "error_classes": ["runner"], "recorded_reason": f"{type(exc).__name__}: {exc}"}
                write_json(output_root / name / f"{name}.json", result)
            results.append(result)
            print(f"{name}: {result['status']} ({result.get('probe_count', 0)}/{len(probe_specs())} probes)", flush=True)
    attach_known_answers(results, date)
    write_summary(output_root, results, date)
    print(f"wrote {output_root} ({len(results)} chains, {len(probe_specs())} probes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))

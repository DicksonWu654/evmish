#!/usr/bin/env python3
"""Collect read-only chain-history evidence for followup."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import pathlib
import sys


ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "probes"))

from keccak import keccak256  # noqa: E402
from run_creation_probes import RpcClient, as_int, rpc_body, write_json  # noqa: E402


REGISTRY = ROOT / "probes" / "chains.json"
DATE = "2026-10-18"
DEFAULT_OUTPUT = "followup/history"
ALIAS_OFFSET = int("1111000000000000000000000000000000001111", 16)


def call(client: RpcClient, raw_dir: pathlib.Path, label: str, method: str, params: list[object]) -> dict:
    request, response = client.call(method, params)
    write_json(raw_dir / f"{label}.request.json", request)
    write_json(raw_dir / f"{label}.response.json", response)
    body = rpc_body(response)
    return {"method": method, "params": params, "request": request, "response": response, "body": body}


def alias_for(address: str) -> str:
    value = (int(address, 16) + ALIAS_OFFSET) & ((1 << 160) - 1)
    return "0x" + value.to_bytes(20, "big").hex()


def event_topic(signature: str) -> str:
    return "0x" + keccak256(signature.encode("utf-8")).hex()


def history_logs(registry: dict, chain: str, address: str, topics: list[str], tag: str, output_root: pathlib.Path, source_chain: str | None = None) -> dict:
    source_chain = source_chain or chain
    entry = next(item for item in registry[source_chain]["rpcs"] if item.get("role") != "secondary")
    client = RpcClient(entry["url"])
    raw_dir = output_root / chain / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    block = call(client, raw_dir, "block-number", "eth_blockNumber", [])
    latest = as_int((block.get("body") or {}).get("result"))
    if latest is None:
        return {"status": "rpc-rejected", "reason": "eth_blockNumber did not return a block", "rpc": entry["url"]}
    start = max(0, latest - 2000)
    params = [{"address": address, "fromBlock": hex(start), "toBlock": hex(latest), "topics": [topics]}]
    logs = call(client, raw_dir, "message-logs", "eth_getLogs", params)
    body = logs.get("body") or {}
    values = body.get("result") if isinstance(body, dict) else None
    record = {
        "status": "ok" if isinstance(values, list) else "rpc-rejected",
        "rpc": entry["url"],
        "source_chain": source_chain,
        "block_range": {"from": hex(start), "to": hex(latest)},
        "contract": address,
        "topics": topics,
        "log_count": len(values) if isinstance(values, list) else None,
        "logs": values if isinstance(values, list) else None,
    }
    if isinstance(values, list) and values:
        record["transaction_hashes"] = sorted({item.get("transactionHash") for item in values if item.get("transactionHash")})
        first = values[0]
        data = first.get("data", "")
        if len(data) >= 66:
            sender = "0x" + data[26:66]
            sender_code = call(client, raw_dir, "sender-code", "eth_getCode", [sender, first.get("blockNumber", "latest")])
            code_result = (sender_code.get("body") or {}).get("result") if sender_code.get("body") else None
            record["l1_sender"] = sender
            record["aliased_sender_candidate"] = alias_for(sender)
            record["alias_formula"] = "(l1_sender + 0x1111000000000000000000000000000000001111) mod 2^160"
            record["sender_code_length_bytes"] = max(0, (len(code_result) - 2) // 2) if isinstance(code_result, str) else None
            record["alias_applies_candidate"] = bool(record["sender_code_length_bytes"])
            record["note"] = "The decoded L1 sender and formula-derived alias are retained; the record does not claim a relayed msg.sender without a matching L2 relay observation."
    else:
        record["reason"] = "No matching message logs were returned in the sampled 2,000-block window; aliasing remains source-verified and not a live relay claim."
    write_json(output_root / chain / "MESSAGE_LOGS.json", record)
    return record


def monad_receipt(registry: dict, output_root: pathlib.Path) -> dict:
    chain = "monad"
    entry = next(item for item in registry[chain]["rpcs"] if item.get("role") != "secondary")
    client = RpcClient(entry["url"])
    raw_dir = output_root / chain / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    block = call(client, raw_dir, "block-number", "eth_blockNumber", [])
    latest = as_int((block.get("body") or {}).get("result"))
    if latest is None:
        return {"status": "rpc-rejected", "reason": "eth_blockNumber did not return a block", "rpc": entry["url"]}
    selected = None
    block_result = None
    for distance in range(0, 6):
        tag = hex(latest - distance)
        item = call(client, raw_dir, f"block-{distance}", "eth_getBlockByNumber", [tag, True])
        value = (item.get("body") or {}).get("result") if item.get("body") else None
        if isinstance(value, dict) and value.get("transactions"):
            selected = next((tx for tx in value["transactions"] if isinstance(tx, dict) and as_int(tx.get("gas")) not in (None, 0)), value["transactions"][0])
            block_result = value
            break
    if not selected:
        return {"status": "no-observable-transaction", "reason": "No transaction-bearing Monad block was returned in six latest blocks.", "rpc": entry["url"], "block_number": hex(latest)}
    tx_hash = selected.get("hash") if isinstance(selected, dict) else selected
    tx = call(client, raw_dir, "transaction", "eth_getTransactionByHash", [tx_hash])
    receipt = call(client, raw_dir, "receipt", "eth_getTransactionReceipt", [tx_hash])
    tx_value = (tx.get("body") or {}).get("result")
    receipt_value = (receipt.get("body") or {}).get("result")
    record = {
        "status": "ok" if isinstance(tx_value, dict) and isinstance(receipt_value, dict) else "rpc-rejected",
        "rpc": entry["url"],
        "block_number": block_result.get("number") if block_result else None,
        "transaction_hash": tx_hash,
        "gas_limit": tx_value.get("gas") if isinstance(tx_value, dict) else None,
        "gas_used": receipt_value.get("gasUsed") if isinstance(receipt_value, dict) else None,
        "gas_limit_uint256": as_int(tx_value.get("gas")) if isinstance(tx_value, dict) else None,
        "gas_used_uint256": as_int(receipt_value.get("gasUsed")) if isinstance(receipt_value, dict) else None,
        "comparison": "gasUsed and gasLimit retained; this single read-only sample is not a universal fee rule",
    }
    write_json(output_root / chain / "MONAD_RECEIPT.json", record)
    return record


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=DATE)
    parser.add_argument("--output", default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
    output_root = ROOT / "results" / args.date / args.output
    output_root.mkdir(parents=True, exist_ok=True)
    report = {
        "schema": 1,
        "date": args.date,
        "purpose": "read-only chain-history evidence; no transaction was sent or signed",
        "aliasing": {},
        "monad_gas": monad_receipt(registry, output_root),
        "tron_precompile": {
            "status": "rpc-rejected",
            "reason": "Existing TRON full-matrix result records QUANTITY not supported / invalid address before VM execution.",
            "result": f"results/{args.date}/tron/tron.json",
        },
        "delegated_7702": {
            "source": f"results/{args.date}/followup/OPCODE_COVERAGE.json",
            "note": "The coverage report aggregates the existing eth_getCode context and EIP-7702 prefix for every chain result.",
        },
    }
    # OP L2 messenger SentMessage and Arbitrum Inbox MessageDelivered logs.
    op_topic = event_topic("SentMessage(address,address,bytes,uint256,uint256)")
    arb_topic = event_topic("InboxMessageDelivered(uint256,bytes32,bytes)")
    report["aliasing"]["op-mainnet"] = history_logs(
        registry,
        "op-mainnet",
        "0x25ace71c97b33cc4729cf772ae268934f7ab5fa1",
        [op_topic],
        "latest",
        output_root,
        source_chain="ethereum",
    )
    report["aliasing"]["arbitrum-one"] = history_logs(
        registry,
        "arbitrum-one",
        "0x4dbd4fc535ac27206064b68ffcf827b0a60bab3f",
        [arb_topic],
        "latest",
        output_root,
    )
    write_json(output_root / "REPORT.json", report)
    (output_root / "SUMMARY.md").write_text(
        "# followup chain-history evidence (2026-10-18)\n\n"
        "This read-only report samples OP and Arbitrum message logs, a recent Monad transaction receipt, the TRON 0x09 RPC limitation, and delegated-account coverage. Empty log windows and missing receipt data are recorded as reasons rather than claims.\n\n"
        "Machine-readable evidence: `REPORT.json`.\n",
        encoding="utf-8",
    )
    print("followup history evidence complete: OP/Arbitrum log samples, Monad receipt comparison, TRON reason, and 7702 coverage recorded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

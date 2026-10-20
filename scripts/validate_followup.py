#!/usr/bin/env python3
"""Validate the follow-up focused probe, coverage, and history artifacts."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATE = "2026-10-18"
followup = ROOT / "results" / DATE / "followup"
FORMULA_CHAINS = {"ethereum", "zksync-era", "arbitrum-one", "tron"}
PROBES = {"push0", "tstore-tload", "mcopy", "blobhash", "blobbasefee"}
STATUSES = {"ok", "rpc-rejected", "execution-failure", "execution-failure-expected", "not-run"}


def load(path: str) -> dict:
    full = ROOT / path
    if not full.exists():
        raise SystemExit(f"missing followup evidence: {path}")
    try:
        return json.loads(full.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"invalid JSON followup evidence {path}: {exc}") from exc


def check_endpoint(endpoint: dict, required: set[str], label: str) -> dict:
    result_path = endpoint.get("result")
    if not result_path:
        raise SystemExit(f"{label}: missing result path")
    result = load(result_path)
    if endpoint.get("rpc") != result.get("rpc") or endpoint.get("block_number") != result.get("block_number"):
        raise SystemExit(f"{label}: endpoint metadata mismatch")
    raw_dir = endpoint.get("raw_evidence_dir")
    if not raw_dir or not (ROOT / raw_dir / "raw").is_dir():
        raise SystemExit(f"{label}: missing raw evidence directory")
    if set(result.get("probes", {})) != required:
        raise SystemExit(f"{label}: probe set mismatch")
    for name in required:
        status = result["probes"][name].get("interpretation", {}).get("status")
        if status not in STATUSES:
            raise SystemExit(f"{label}/{name}: invalid status {status!r}")
    return result


def main() -> int:
    report = load(f"results/{DATE}/followup/headline-probes/REPORT.json")
    if report.get("schema") != 1 or "RPC/VM" not in report.get("purpose", ""):
        raise SystemExit("headline report schema/purpose mismatch")
    if set(report.get("formula_chains", {})) != FORMULA_CHAINS:
        raise SystemExit("headline formula chain set mismatch")
    for chain, item in report["formula_chains"].items():
        primary = check_endpoint(item["primary"], {"create", "create2"}, f"formula/{chain}/primary")
        if chain == "tron":
            for name in ("create", "create2"):
                if primary["probes"][name]["interpretation"].get("status") != "rpc-rejected":
                    raise SystemExit("TRON formula probes must retain RPC rejection")
        secondary = item.get("secondary")
        if secondary:
            check_endpoint(secondary, {"create", "create2"}, f"formula/{chain}/secondary")

    size = report.get("code_size_chains", {})
    if set(size) != {"ethereum", "monad"}:
        raise SystemExit("headline code-size chain set mismatch")
    check_endpoint(size["ethereum"]["primary"], {"oversized-runtime-create-24576", "oversized-runtime-create-24577"}, "size/ethereum")
    check_endpoint(size["monad"]["primary"], {"oversized-runtime-create-24576", "oversized-runtime-create-24577", "oversized-runtime-create-131072", "oversized-runtime-create-131073"}, "size/monad")

    coverage = load(f"results/{DATE}/followup/OPCODE_COVERAGE.json")
    if set(coverage.get("chains", {})) != {row["chain"] for row in json.loads((ROOT / "results" / DATE / "SUMMARY.json").read_text())["chains"]}:
        raise SystemExit("opcode coverage chain set does not match the registry result matrix")
    if set(coverage.get("probes", [])) != PROBES:
        raise SystemExit("opcode coverage probe set mismatch")
    for chain, item in coverage["chains"].items():
        if set(item.get("probes", {})) != PROBES:
            raise SystemExit(f"opcode coverage probe set mismatch for {chain}")
        for name, probe in item["probes"].items():
            if probe.get("status") not in STATUSES:
                raise SystemExit(f"opcode coverage invalid status {chain}/{name}")
    if coverage.get("tron_precompile_0x09", {}).get("status") != "rpc-rejected":
        raise SystemExit("TRON 0x09 limitation was not retained as RPC rejection")

    history = load(f"results/{DATE}/followup/history/REPORT.json")
    if history.get("purpose", "").find("no transaction was sent") < 0:
        raise SystemExit("history report does not state read-only scope")
    op = history.get("aliasing", {}).get("op-mainnet", {})
    if op.get("log_count", 0) and not {"l1_sender", "aliased_sender_candidate", "alias_formula"} <= set(op):
        raise SystemExit("OP alias log lacks decoded sender and alias candidate")
    arb = history.get("aliasing", {}).get("arbitrum-one", {})
    if not arb.get("log_count") and not arb.get("reason"):
        raise SystemExit("Arbitrum aliasing lacks a log result or recorded reason")
    monad = history.get("monad_gas", {})
    if monad.get("status") == "ok":
        if monad.get("gas_limit_uint256") is None or monad.get("gas_used_uint256") is None:
            raise SystemExit("Monad history result lacks gas limit/used values")
    elif not monad.get("reason"):
        raise SystemExit("Monad history lacks gas result or reason")

    catalog = (ROOT / "CATALOG.md").read_text(encoding="utf-8")
    for path in (
        f"results/{DATE}/followup/headline-probes/REPORT.json",
        f"results/{DATE}/followup/OPCODE_COVERAGE.json",
        f"results/{DATE}/followup/history/REPORT.json",
    ):
        if path not in catalog:
            raise SystemExit(f"catalog does not link followup evidence {path}")
    print("followup validation passed: formula/code-size probes, 27-chain opcode coverage, history evidence, and catalog links present")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

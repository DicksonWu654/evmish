#!/usr/bin/env python3
"""Build the all-chain fork-opcode and 7702 coverage report from raw results."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATE = "2026-10-18"
RESULTS = ROOT / "results" / DATE
PROBES = ("push0", "tstore-tload", "mcopy", "blobhash", "blobbasefee")


def main() -> int:
    summary = json.loads((RESULTS / "SUMMARY.json").read_text(encoding="utf-8"))
    coverage = {
        "schema": 1,
        "date": DATE,
        "purpose": "followup all-chain fork-opcode coverage plus fixed-address account context; execution failures remain distinct from RPC rejection",
        "probes": list(PROBES),
        "chains": {},
        "delegated_7702": {},
        "tron_precompile_0x09": {
            "status": "rpc-rejected",
            "reason": "The recorded TRON endpoint rejected the no-to creation probes before VM execution; see the raw endpoint result.",
            "result": f"results/{DATE}/tron/tron.json",
        },
    }
    history = {
        "schema": 1,
        "date": DATE,
        "purpose": "Per-chain EIP-7702 history gate",
        "status_definition": "none-found means no real type-4 transaction or delegated-account history was captured in this read-only followup evidence; fixed-address eth_getCode context is intentionally not treated as support evidence.",
        "chains": {},
    }
    for row in sorted(summary["chains"], key=lambda item: item["chain"]):
        chain = row["chain"]
        path = RESULTS / chain / f"{chain}.json"
        result = json.loads(path.read_text(encoding="utf-8"))
        entry = {
            "rpc": result.get("rpc"),
            "block_number": result.get("block_number"),
            "status": result.get("status"),
            "result": f"results/{DATE}/{chain}/{chain}.json",
            "probes": {},
        }
        for name in PROBES:
            probe = result.get("probes", {}).get(name, {})
            interp = probe.get("interpretation", {})
            entry["probes"][name] = {
                "status": interp.get("status", "not-run"),
                "error_class": interp.get("error_class"),
                "raw_return": interp.get("raw_return"),
                "uint256": interp.get("uint256"),
                "result": f"results/{DATE}/{chain}/{chain}.json",
            }
        coverage["chains"][chain] = entry
        context = result.get("context", {}).get("eth_getCode_delegated-7702", {})
        context_interp = context.get("interpretation", {})
        coverage["delegated_7702"][chain] = {
            "status": "fixed-address-context-only",
            "error_class": context_interp.get("error_class"),
            "code_length_bytes": context_interp.get("code_length_bytes"),
            "eip7702_delegation_prefix": context_interp.get("eip7702_delegation_prefix"),
            "result": f"results/{DATE}/{chain}/{chain}.json",
            "history_evidence": f"results/{DATE}/followup/EIP7702_HISTORY.json",
        }
        history["chains"][chain] = {
            "status": "none-found",
            "reason": "No real type-4 transaction or delegated-account history was captured; the fixed candidate address was excluded from chain-semantic claims.",
            "result": f"results/{DATE}/{chain}/{chain}.json",
        }

    output = RESULTS / "followup"
    output.mkdir(parents=True, exist_ok=True)
    (output / "OPCODE_COVERAGE.json").write_text(json.dumps(coverage, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    (output / "EIP7702_HISTORY.json").write_text(json.dumps(history, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = [
        "# followup all-chain fork-opcode and account coverage (2026-10-18)",
        "",
        "This report is generated from the dated full probe matrix. It covers PUSH0, TSTORE/TLOAD, MCOPY, BLOBHASH, and BLOBBASEFEE on every registry chain result, retaining `execution-failure` separately from `rpc-rejected`. The delegated-account field is fixed-address context only; `EIP7702_HISTORY.json` records that no real type-4/delegated-account history was captured, so it is not a chain-wide support claim. The TRON 0x09 limitation remains explicit.",
        "",
        "Machine-readable evidence: `OPCODE_COVERAGE.json`.",
        "",
    ]
    (output / "OPCODE_COVERAGE.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"followup coverage report complete: {len(coverage['chains'])} chains, {len(PROBES)} probes, delegated-account context retained")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

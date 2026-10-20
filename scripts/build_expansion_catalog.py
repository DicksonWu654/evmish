#!/usr/bin/env python3
"""Curated E29–E31 catalog rows, gated by the retained result matrices."""

from __future__ import annotations

import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATE = "2026-10-20"
BASE = ROOT / "results" / DATE
ROUND4_TOP10 = "docs/verification/round-4-top10.md"


def read(name: str) -> list[dict[str, str]]:
    with (BASE / name).open(newline="") as stream:
        return list(csv.DictReader(stream))


def links(folder: str, row: dict[str, str], baseline: dict[str, str], fields: tuple[str, str, str]) -> str:
    primary, later, secondary = fields
    items = [(row[primary], "primary"), (baseline[primary], "Ethereum control"),
             (row[later], "later block"), (row[secondary], "second endpoint")]
    return "; ".join(f"[{label}](results/{DATE}/{folder}/{path})" for path, label in items if path)


# One representative control per distinct repricing mechanism; the entire measured
# schedule (including equal, failed, and gas-bound cells) stays in MATRIX.csv.
GAS = [
    ("polygon-pos", "sload-slot0", "cold", "A fixed gas budget for a first storage read can exhaust sooner on this target."),
    ("monad", "memory-expand-32768-words", "operation", "Memory-heavy work has a different gas curve; use a target-chain budget before relying on a size limit."),
    ("monad", "sload-slot0", "cold", "A storage-reading hook with an Ethereum-sized stipend can run out of gas."),
    ("monad", "extcodesize-empty", "cold", "An external-account check with a fixed stipend can run out of gas."),
    ("monad", "funded-call-value-empty", "operation", "A relayer that prices a funded empty-account CALL from Ethereum can underfund that path."),
    ("megaeth", "log1-0-bytes", "operation", "Event-heavy paths need a target-chain gas budget when a callback or relayer has a cap."),
    ("megaeth", "log4-256-bytes", "operation", "A capped event-heavy operation may exhaust gas earlier than its Ethereum test predicts."),
    ("tempo", "create-0-bytes", "operation", "Factory and deployment budgets based on Ethereum can fail on the target."),
    ("tempo", "sstore-transitions", "zero-to-one", "State-creating paths need a target-chain gas budget before use in capped operations."),
    ("sei-evm", "sstore-transitions", "zero-to-one", "A capped first-write path can exhaust gas sooner; the configured price may change."),
    ("somnia", "keccak-32-words", "operation", "Hash-heavy paths with fixed stipends need a target-chain gas budget."),
    ("somnia", "log4-256-bytes", "operation", "Large events in a capped path can exhaust gas sooner than Ethereum tests suggest."),
    ("somnia", "sstore-transitions", "zero-to-one", "An Ethereum-sized first-write budget can fail on the target."),
    ("somnia", "create-0-bytes", "operation", "An Ethereum-sized factory budget can fail on the target."),
    ("somnia", "funded-call-value-empty", "operation", "A funded CALL with a fixed outer gas cap needs testing against the target's pricing."),
    ("kaia", "extcodehash-empty", "cold", "A fixed budget or cold/warm assumption for account inspection needs a target test."),
    ("kaia", "extcodehash-empty", "warm", "Repeated account inspection has a different measured price; benchmark any capped loop on the target."),
]


def build() -> list[tuple[str, str, str, str, str, str]]:
    output = []
    gas = {(r["chain"], r["case"], r["phase"]): r for r in read("gas-schedule/MATRIX.csv")}
    for chain, case, phase, consequence in GAS:
        row, base = gas[(chain, case, phase)], gas[("ethereum", case, phase)]
        if row["status"] != "confirmed-two-endpoints" or not row["confirmation_file"] or not row["secondary_file"]:
            raise ValueError(f"gas evidence gate failed: {chain}/{case}/{phase}")
        a, b = int(base["chain_gas"]), int(row["chain_gas"])
        if a == b or b != int(row["confirmation_gas"]) or b != int(row["secondary_gas"]):
            raise ValueError(f"gas values disagree: {chain}/{case}/{phase}")
        observed = (f"{case} ({phase}) used {b:,} measured gas on {chain} versus {a:,} on Ethereum; "
                    "later-block and second-endpoint measurements matched. "
                    "This is the read-only creation-call operation delta, not a transaction fee or refund.")
        evidence = links("gas-schedule", row, base, ("raw_file", "confirmation_file", "secondary_file"))
        if chain == "somnia" and case == "sstore-transitions" and phase == "zero-to-one":
            consequence = ("A new nonzero slot write requires at least 1,000,000 gas remaining on Somnia, "
                           "although this operation charged 200,100 gas; a lower remaining-gas cap can fail even if it covers the charge.")
            evidence += "; [official gas rule, accessed 2026-10-20](https://docs.somnia.network/developer/deployment-and-production/somnia-gas-differences-to-ethereum.md)"
            evidence += f"; [round-4 threshold control]({ROUND4_TOP10}#additional-gas-threshold-and-input-controls)"
        if chain == "monad" and case == "memory-expand-32768-words":
            consequence = ("Memory-heavy work has a different gas curve below Monad's documented 8 MB memory cap; "
                           "bound user-controlled sizes and test the target limit.")
            evidence += "; [official memory rule, accessed 2026-10-20](https://docs.monad.xyz/developer-essentials/opcode-pricing.md#memory-expansion)"
        output.append(("probe-verified", chain, observed, consequence, evidence, DATE))

    pre = {(r["chain"], r["address"]): r for r in read("precompile-sweep/MATRIX.csv")}
    base = pre[("ethereum", "0x0b")]
    if base["valid_status"] != "match":
        raise ValueError("Ethereum G1ADD known-answer control failed")
    for chain in ("avalanche-c-chain", "blast", "hyperevm", "scroll", "zksync-era"):
        row = pre[(chain, "0x0b")]
        status = "call-failed" if chain == "zksync-era" else "empty-success"
        if row["valid_status"] != status or row["valid_later"] != "same" or not row["later_evidence"]:
            raise ValueError(f"G1ADD evidence gate failed: {chain}")
        second = row["valid_second_endpoint"]
        if second not in {"same", "no-listed-endpoint"}:
            raise ValueError(f"G1ADD endpoint disagreement: {chain}")
        observed = (f"The valid BLS12-381 G1ADD vector at 0x0b returned {status} on {chain}; "
                    "Ethereum returned the known answer. The result recurred at a later block. ")
        if second == "same":
            observed += "A listed second endpoint matched."
        elif chain == "avalanche-c-chain":
            observed += "The independent review's PublicNode replay at block 0x5d7d6fd also returned empty success."
        else:
            observed += "No independent endpoint is listed for this chain."
        consequence = ("This CALL failed closed with status 0; a verifier that requires G1ADD output "
                       "must handle failure, but this result does not imply an empty-success bypass."
                       if chain == "zksync-era" else
                       "A verifier that checks only CALL success could continue with empty output; whether that affects proof acceptance depends on its output checks.")
        evidence_row = {**row, "second_endpoint_evidence": row["second_endpoint_evidence"] if second == "same" else ""}
        evidence = links("precompile-sweep", evidence_row, base,
                         ("initial_evidence", "later_evidence", "second_endpoint_evidence"))
        if chain == "avalanche-c-chain":
            evidence += f"; [PublicNode independent replay]({ROUND4_TOP10}#3-avalanche-g1add)"
        output.append(("probe-verified", chain, observed, consequence, evidence, DATE))

    life = {(r["chain"], r["case"]): r for r in read("lifecycle/MATRIX.csv")}
    for chain, case in [
        ("somnia", "runtime-24577"),
        ("monad", "init-49153"), ("megaeth", "init-49153"),
        ("berachain", "init-49153"), ("somnia", "init-49153"), ("celo", "init-49153"),
        ("zksync-era", "selfdestruct-funded"), ("scroll", "selfdestruct-funded"),
        ("kaia", "precompile-value"),
    ]:
        row, base = life[(chain, case)], life[("ethereum", case)]
        if row["status"] != "observed" or row["later_block"] != "same" or not row["later_evidence"]:
            raise ValueError(f"lifecycle evidence gate failed: {chain}/{case}")
        outcome = json.loads(row["outcome"])
        if case == "runtime-24577":
            if outcome.get("code_size") != 24577 or not outcome.get("created"):
                raise ValueError("Somnia runtime result changed")
            observed = "A read-only CREATE simulation on Somnia produced 24,577 runtime bytes with a 120M-gas call; Ethereum's control rejected the 24,577-byte child."
            consequence = "A factory relying on Ethereum's 24,576-byte bound needs a target deployment test; this simulation does not establish transaction admission."
        elif case == "init-49153":
            if not outcome.get("created") or json.loads(base["outcome"])["status"] != "outer-execution-failure":
                raise ValueError(f"init-size control changed: {chain}")
            observed = f"A read-only CREATE simulation with 49,153-byte init code created a child on {chain}; Ethereum's same control returned an outer execution error."
            consequence = "A factory using init code above Ethereum's 49,152-byte boundary needs a target deployment test; the simulation alone does not prove transaction admission."
            if chain == "monad":
                observed += " Monad's documented 128 KiB runtime-code cap does not establish its init-code limit."
        elif case == "selfdestruct-funded":
            if outcome.get("kill_status") != 0:
                raise ValueError(f"SELFDESTRUCT result changed: {chain}")
            observed = f"The same-call funded SELFDESTRUCT kill returned status 0 on {chain}, while Ethereum returned status 1; the child still had 174 code bytes in the returned state."
            consequence = "A flow that requires the child kill to succeed must test this call path on the target; post-transaction code deletion was not measured."
            if chain == "zksync-era":
                observed += " The zero-value kill also failed and an isolated SELFDESTRUCT init-code call reverted on both reviewed endpoints."
                consequence = "The tested SELFDESTRUCT paths failed closed on zkSync Era; cleanup logic must check the kill status and cannot infer post-transaction deletion from this read-only call."
        else:
            if outcome.get("call_status") != 0:
                raise ValueError("Kaia value-call control changed")
            observed = "Kaia's read-only one-wei identity-precompile CALL returned status 0 and spent no value; Ethereum returned status 1 and spent one wei."
            consequence = "A value-transfer path through this precompile address needs a target test before relying on success or balance movement."
        second = row["second_endpoint"]
        if second not in {"same", "no-listed-endpoint"}:
            raise ValueError(f"lifecycle endpoint disagreement: {chain}/{case}")
        if second == "no-listed-endpoint":
            observed += " No listed second endpoint confirmed it."
        evidence_row = {**row, "second_endpoint_evidence": row["second_endpoint_evidence"] if second == "same" else ""}
        evidence = links("lifecycle", evidence_row, base,
                         ("initial_evidence", "later_evidence", "second_endpoint_evidence"))
        if chain == "zksync-era" and case == "selfdestruct-funded":
            evidence += f"; [round-4 isolated and zero-value controls]({ROUND4_TOP10}#6-zksync-selfdestruct)"
        output.append(("probe-verified", chain, observed, consequence, evidence, DATE))
    return output

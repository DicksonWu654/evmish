#!/usr/bin/env python3
"""Build the public site data contract from the dated probe results."""
from __future__ import annotations

import json
import re
import sys
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
DATE = "2026-10-18"
RESULTS = ROOT / "results" / DATE
BLOG = ROOT / "blog" / "post.md"
CATALOG = ROOT / "CATALOG.md"
CHAINS_CONFIG = ROOT / "probes" / "chains.json"
ENDPOINT_AUDIT = ROOT / "docs" / "endpoint-audit.md"
EXPANSION_DATE = "2026-10-20"
sys.path.insert(0, str(ROOT))

# Keep presentation names derived from the result/config identifiers. These are
# labels, not probe values; all numeric fields come directly from result files.
NAME_OVERRIDES = {
    "ethereum": "Ethereum",
    "arbitrum-one": "Arbitrum One",
    "avalanche-c-chain": "Avalanche C-Chain",
    "bnb-smart-chain": "BNB Smart Chain",
    "op-mainnet": "OP Mainnet",
    "polygon-pos": "Polygon PoS",
    "sei-evm": "Sei EVM",
    "zksync-era": "zkSync Era",
    "evmos": "Evmos",
    "hyperevm": "HyperEVM",
    "megaeth": "MegaETH",
    "cronos": "Cronos",
    "kaia": "Kaia",
    "gnosis": "Gnosis",
    "celo": "Celo",
    "taiko": "Taiko",
    "tempo": "Tempo",
    "plasma": "Plasma",
    "berachain": "Berachain",
    "somnia": "Somnia",
    "mantle": "Mantle",
    "blast": "Blast",
    "monad": "Monad",
    "linea": "Linea",
    "scroll": "Scroll",
    "tron": "TRON",
    "base": "Base",
}

CATEGORY_OVERRIDES = {
    "push0": "opcodes", "tstore-tload": "opcodes", "mcopy": "opcodes",
    "blobhash": "opcodes", "blobbasefee": "opcodes",
    "number": "block context", "basefee": "block context", "chainid": "block context",
    "deliberate-invalid": "block context", "prevrandao": "block context",
    "coinbase": "block context", "gaslimit": "block context", "timestamp": "block context",
    "blockhash-n-minus-1": "block context", "blockhash-n-minus-256": "block context",
    "blockhash-n-minus-257": "block context",
    "create": "addresses", "create2": "addresses", "oversized-runtime-create": "addresses",
    "precompile-0x01-ecrecover": "precompiles", "precompile-0x02-sha256": "precompiles",
    "precompile-0x03-ripemd160": "precompiles", "precompile-0x04-identity": "precompiles",
    "precompile-0x05-modexp": "precompiles", "precompile-0x06-bn128-add": "precompiles",
    "precompile-0x07-bn128-mul": "precompiles", "precompile-0x08-bn128-pairing": "precompiles",
    "precompile-0x09-blake2f": "precompiles", "precompile-0x0a-kzg-point-evaluation": "precompiles",
    "precompile-0x0b-address-0b": "precompiles", "precompile-0x0c-address-0c": "precompiles",
    "precompile-0x0d-address-0d": "precompiles", "precompile-0x0e-address-0e": "precompiles",
    "precompile-0x0f-address-0f": "precompiles", "precompile-0x10-address-10": "precompiles",
    "precompile-0x11-address-11": "precompiles", "precompile-0x100-p256verify": "precompiles",
    "extcode-eoa": "account code", "extcode-empty": "account code",
    "extcode-delegated-7702": "account code", "extcode-system-contract": "account code",
    "cold-warm-extcodesize": "gas/fees", "estimate-gas": "gas/fees",
}

HEADLINES = {
    "bls-precompiles-missing": {"title": "BLS G1ADD known-answer mismatch", "kind": "bls"},
    "ripemd160-zksync-scroll": {"title": "RIPEMD160 failing on zkSync Era and Scroll", "kind": "ripemd"},
    "arbitrum-number-l1": {"title": "Arbitrum NUMBER = L1", "kind": "number"},
    "prevrandao-constants": {"title": "PREVRANDAO constants on zkSync Era and Avalanche", "kind": "prevrandao"},
    "monad-cold-access": {"title": "Monad cold access gas", "kind": "monad"},
    "zksync-create2-docs-stale": {"title": "zkSync CREATE2 docs are stale", "kind": "create2"},
}


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def chain_ids() -> list[str]:
    summary = load_json(RESULTS / "SUMMARY.json")
    return [row["chain"] for row in sorted(summary["chains"], key=lambda row: row["chain"])]


def probe_ids() -> list[str]:
    return list(load_json(RESULTS / "SUMMARY.json")["probe_names"])


def result(chain: str) -> dict:
    path = RESULTS / chain / f"{chain}.json"
    return load_json(path) if path.exists() else {"chain": chain, "status": "unavailable", "probes": {}, "rpc": None}


def host(url: str | None) -> str | None:
    return urlparse(url).hostname if url else None


def lossless(value):
    """Keep EVM integers exact when the JSON is consumed by JavaScript.

    Probe interpretations contain uint256 words, balances, fee values and gas
    measurements.  They are emitted as decimal strings even when a particular
    observation happens to fit in a JavaScript number; booleans remain
    booleans and structural counts outside interpretations remain integers.
    """
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return [lossless(item) for item in value]
    if isinstance(value, dict):
        return {key: lossless(item) for key, item in value.items()}
    return value


PROVIDER_NAMES = {
    "publicnode": "PublicNode",
    "cloudflare": "Cloudflare",
    "drpc": "dRPC",
    "ankr": "Ankr",
    "quicknode": "QuickNode",
    "alchemy": "Alchemy",
    "infura": "Infura",
    "llamarpc": "LlamaRPC",
}


def endpoint_audit() -> dict[str, dict]:
    """Return the audited primary endpoint metadata keyed by host."""
    entries = {}
    for line in ENDPOINT_AUDIT.read_text(encoding="utf-8").splitlines():
        if not line.startswith("|") or line.startswith("|---"):
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) != 7 or parts[0] == "Chain":
            continue
        chain, _expected, source, _returned, endpoint, _verdict, _evidence = parts
        endpoint_match = re.search(r"`([^`]+)`", endpoint)
        source_match = re.search(r"\]\((https?://[^)]+)\)", source)
        if not endpoint_match or endpoint_match.group(1) == "—":
            continue
        endpoint_host = host(endpoint_match.group(1))
        if not endpoint_host:
            continue
        source_host = host(source_match.group(1)) if source_match else None
        provider = None
        for marker, name in PROVIDER_NAMES.items():
            if marker in endpoint_host.lower() or (source_host and marker in source_host.lower()):
                provider = name
                break
        entries[endpoint_host] = {"chain": chain, "operator": "third-party" if provider else "chain", "provider": provider}
    return entries


def endpoint_hosts(chains: list[str], results: dict[str, dict]) -> list[dict]:
    """List only the primary hosts that supplied the matrix inputs."""
    audited = endpoint_audit()
    hosts = []
    for chain in chains:
        endpoint = host(results[chain].get("rpc"))
        if not endpoint:
            continue
        metadata = audited.get(endpoint)
        if metadata is None:
            raise ValueError(f"primary endpoint is absent from endpoint audit: {endpoint}")
        row = {"host": endpoint, "operator": metadata["operator"]}
        if metadata["provider"]:
            row["provider"] = metadata["provider"]
        hosts.append(row)
    return sorted(hosts, key=lambda row: row["host"])


def secondary_endpoint_rows(configs: dict[str, dict]) -> list[dict]:
    """List registered confirmations plus the dated independent review replay."""
    rows = []
    for chain, config in configs.items():
        for entry in config.get("rpcs", []):
            if entry.get("role") != "secondary":
                continue
            endpoint_host = host(entry.get("url"))
            if not endpoint_host:
                continue
            provider = None
            for marker, name in PROVIDER_NAMES.items():
                if marker in endpoint_host.lower():
                    provider = name
                    break
            row = {
                "chain": chain,
                "host": endpoint_host,
                "operator": "third-party" if provider else "chain",
                "used_for": "independent headline and follow-up confirmations",
            }
            if provider:
                row["provider"] = provider
            rows.append(row)
    rows.append({
        "chain": "avalanche-c-chain", "host": "avalanche-c-chain-rpc.publicnode.com",
        "operator": "third-party", "provider": "PublicNode",
        "used_for": "independent review round-4 G1ADD replay at block 0x5d7d6fd",
        "evidence": "docs/verification/round-4-top10.md#3-avalanche-g1add",
    })
    return sorted(rows, key=lambda row: (row["chain"], row["host"]))


def chain_name(chain: str) -> str:
    return NAME_OVERRIDES.get(chain, chain.replace("-", " ").title())


def parse_catalog() -> list[dict]:
    rows = []
    for line in CATALOG.read_text(encoding="utf-8").splitlines():
        if not re.match(r"^\|\s*\d+\s*\|", line):
            continue
        parts = [part.strip() for part in line.strip().strip("|").split("|")]
        if len(parts) != 7:
            raise ValueError(f"unexpected catalog row shape: {line}")
        number, label, scope, behavior, consequence, evidence, date = parts
        paths = [p for p in re.findall(r"\]\(([^)]+)\)", evidence) if not p.startswith(("http://", "https://"))]
        rows.append({
            "number": int(number), "label": label, "chain_scope": scope,
            "behavior": behavior, "consequence": consequence,
            "evidence_path": paths[0] if paths else evidence,
            "evidence_paths": paths, "date": date,
        })
    return rows


def catalog_confirmation_probes() -> dict[str, set[str]]:
    """Map catalog rows with later-block evidence to their probe IDs."""
    from scripts.differential_common import PROBE_DESCRIPTIONS

    selected: dict[str, set[str]] = {}
    for row in parse_catalog():
        if not any("differential-confirmation" in path for path in row["evidence_paths"]):
            continue
        for probe, (title, _description) in PROBE_DESCRIPTIONS.items():
            if row["behavior"].startswith(title + ":"):
                selected.setdefault(row["chain_scope"], set()).add(probe)
                break
    return selected


def interpretation(r: dict, probe: str) -> dict | None:
    return r.get("probes", {}).get(probe, {}).get("interpretation")


def public_class(internal: str) -> str:
    return {
        "diff": "differs", "unsupported": "unsupported/execution-failure",
        "rejected": "rpc-rejected", "unstable-endpoint": "endpoint-artifact",
        "rpc-simulation": "endpoint-artifact", "unverifiable": "endpoint-artifact",
    }.get(internal, internal)


def matrix_cells(chains: list[str], probes: list[str]) -> list[dict]:
    from scripts.differential_common import load_result
    from scripts.build_catalog import matrix_cell
    baseline = load_result("ethereum")
    confirmed = catalog_confirmation_probes()
    out = []
    for chain in chains:
        r = load_result(chain)
        confirmation_path = RESULTS / "differential-confirmation" / chain / f"{chain}.json"
        confirmation = load_json(confirmation_path) if confirmation_path.exists() else {}
        for probe in probes:
            internal = matrix_cell(chain, probe, baseline, r)
            evidence = [f"results/{DATE}/{chain}/{chain}.json"]
            if chain != "ethereum":
                evidence.append(f"results/{DATE}/ethereum/ethereum.json")
            if probe in confirmed.get(chain, set()) and probe in confirmation.get("probes", {}):
                evidence.append(str(confirmation_path.relative_to(ROOT)))
            out.append({
                "chain": chain,
                "probe": probe,
                "class": public_class(internal),
                "value": lossless(interpretation(r, probe)),
                "evidence": evidence,
                "block": block_number(r),
                "sample_date": DATE,
            })
    return out


def first_sentence(text: str) -> str:
    text = text.strip()
    match = re.search(r"\.(?:\s|$)", text)
    return text[: match.end() - 1] if match else text


def checklist() -> list[str]:
    items = []
    current = None
    for raw in (ROOT / "docs" / "checklist.md").read_text(encoding="utf-8").splitlines():
        line = raw.rstrip()
        if line.startswith("- "):
            if current is not None:
                items.append(current)
            current = line[2:].strip()
        elif current is not None and line.strip():
            # Markdown continuation lines are indented; joining with one space
            # preserves the item text without carrying source wrapping through
            # to the JSON contract.
            current += " " + line.strip()
        elif current is not None and not line.strip():
            items.append(current)
            current = None
    if current is not None:
        items.append(current)
    return items


def probe_init_codes(probes: list[str]) -> dict[str, str]:
    sys.path.insert(0, str(ROOT / "probes"))
    from probes.run_creation_probes import probe_specs

    specs = probe_specs()
    missing = [probe for probe in probes if probe not in specs or not specs[probe].get("data")]
    if missing:
        raise ValueError(f"missing probe init code: {', '.join(missing)}")
    return {probe: specs[probe]["data"] for probe in probes}


def block_number(r: dict) -> str | None:
    block = r.get("block_number")
    if block is not None:
        return block
    return (r.get("block") or {}).get("number") if isinstance(r.get("block"), dict) else None


def headline_payloads(results: dict[str, dict]) -> dict[str, dict]:
    eth = results["ethereum"]
    def interp(chain: str, probe: str) -> dict:
        return results[chain].get("probes", {}).get(probe, {}).get("interpretation", {}) or {}
    def b(chain: str) -> str:
        return block_number(results[chain]) or "unknown"
    def precompile_line(chain: str, probe: str) -> str:
        value = interp(chain, probe)
        return (
            f"{chain_name(chain)} block {b(chain)}: {probe} ->\n"
            f"  precompile_call_status={value.get('precompile_call_status')}, precompile_output_words={value.get('precompile_output_words')}"
        )

    import csv
    with (ROOT / "results" / EXPANSION_DATE / "precompile-sweep" / "MATRIX.csv").open(newline="") as stream:
        bls_rows = {r["chain"]: r for r in csv.DictReader(stream) if r["address"] == "0x0b"}
    bls = "\n".join(
        f"{chain_name(chain)} block {bls_rows[chain]['block']}: G1ADD 0x0b valid vector -> "
        f"{bls_rows[chain]['valid_status']}, output_bytes={len(bytes.fromhex(bls_rows[chain]['valid_output'][2:]))}"
        for chain in ("ethereum", "avalanche-c-chain", "blast", "hyperevm", "scroll")
    )
    ripemd = (
        f"Ethereum block {b('ethereum')}: precompile-0x03-ripemd160 -> status="
        f"{interp('ethereum', 'precompile-0x03-ripemd160').get('precompile_call_status')}\n"
        f"zkSync Era block {b('zksync-era')}: precompile-0x03-ripemd160 -> status="
        f"{interp('zksync-era', 'precompile-0x03-ripemd160').get('precompile_call_status')}\n"
        f"Scroll block {b('scroll')}: precompile-0x03-ripemd160 -> status="
        f"{interp('scroll', 'precompile-0x03-ripemd160').get('precompile_call_status')}"
    )
    n_eth, n_arb = interp("ethereum", "number"), interp("arbitrum-one", "number")
    number = (
        f"Arbitrum block tag {b('arbitrum-one')}:\n  probes.number.uint256={n_arb.get('uint256')}\n"
        f"  block.number={n_arb.get('header_value')}\n  header_matches={str(n_arb.get('header_matches')).lower()}\n"
        f"Ethereum block tag {b('ethereum')}:\n  probes.number.uint256={n_eth.get('uint256')}\n  block.number={n_eth.get('header_value')}"
    )
    prevrandao = (
        f"zkSync Era block {b('zksync-era')}: uint256={interp('zksync-era', 'prevrandao').get('uint256')},\n"
        f"  header_value={interp('zksync-era', 'prevrandao').get('header_value')}, header_matches={str(interp('zksync-era', 'prevrandao').get('header_matches')).lower()}\n"
        f"Avalanche C-Chain block {b('avalanche-c-chain')}: uint256={interp('avalanche-c-chain', 'prevrandao').get('uint256')},\n"
        f"  header_value={interp('avalanche-c-chain', 'prevrandao').get('header_value')}, header_matches={str(interp('avalanche-c-chain', 'prevrandao').get('header_matches')).lower()}"
    )
    monad_eth = interp("ethereum", "cold-warm-extcodesize")
    monad_target = interp("monad", "cold-warm-extcodesize")
    monad = (
        f"Ethereum block {b('ethereum')}: gas_delta={monad_eth.get('gas_delta')}, warm_gas_delta={monad_eth.get('warm_gas_delta')}\n"
        f"Monad block {b('monad')}: gas_delta={monad_target.get('gas_delta')}, warm_gas_delta={monad_target.get('warm_gas_delta')}"
    )
    monad_title = f"Monad cold access {monad_target.get('gas_delta'):,} vs {monad_eth.get('gas_delta'):,} gas"
    note = next((p.strip() for p in BLOG.read_text(encoding="utf-8").split("\n\n") if p.startswith("One result went the other way")), "")
    return {
        "bls-precompiles-missing": {"title": HEADLINES["bls-precompiles-missing"]["title"], "raw_lines": bls, "solidity_unsafe": '(bool ok, bytes memory out) = address(0x0b).staticcall(input);\nrequire(ok, "precompile failed");', "solidity_safe": '// on every call: G1ADD returns 128 bytes\n(bool ok, bytes memory out) = address(0x0b).staticcall(input);\nrequire(ok && out.length == 128, "no BLS precompile");\n\n// once, in the constructor: a fixed vector with a known result\n(bool kok, bytes memory kout) = address(0x0b).staticcall(KAT_INPUT);\nrequire(kok && keccak256(kout) == KAT_HASH, "wrong precompile");'},
        "ripemd160-zksync-scroll": {"title": HEADLINES["ripemd160-zksync-scroll"]["title"], "raw_lines": ripemd, "solidity_unsafe": None, "solidity_safe": None},
        "arbitrum-number-l1": {"title": HEADLINES["arbitrum-number-l1"]["title"], "raw_lines": number, "solidity_unsafe": None, "solidity_safe": None},
        "prevrandao-constants": {"title": HEADLINES["prevrandao-constants"]["title"], "raw_lines": prevrandao, "solidity_unsafe": None, "solidity_safe": None},
        "monad-cold-access": {"title": monad_title, "raw_lines": monad, "solidity_unsafe": None, "solidity_safe": None},
        "zksync-create2-docs-stale": {"title": HEADLINES["zksync-create2-docs-stale"]["title"], "raw_lines": None, "note": note, "solidity_unsafe": None, "solidity_safe": None},
    }


def add_headline(row: dict, payloads: dict[str, dict]) -> dict:
    text = " ".join((row["chain_scope"], row["behavior"], row["consequence"]))
    slug = None
    if "NUMBER/header semantics" in row["behavior"] and row["chain_scope"] == "arbitrum-one": slug = "arbitrum-number-l1"
    elif "PREVRANDAO/header semantics" in row["behavior"] and row["chain_scope"] == "avalanche-c-chain": slug = "prevrandao-constants"
    elif "Cold versus warm EXTCODESIZE" in text and row["chain_scope"] == "monad": slug = "monad-cold-access"
    elif "RIPEMD160" in text and row["chain_scope"] == "zksync-era": slug = "ripemd160-zksync-scroll"
    elif "valid BLS12-381 G1ADD vector" in row["behavior"] and row["chain_scope"] == "avalanche-c-chain": slug = "bls-precompiles-missing"
    row["headline"] = bool(slug)
    row["slug"] = slug
    if slug:
        row["headline_content"] = payloads[slug]
    return row


def build_data() -> dict:
    summary = load_json(RESULTS / "SUMMARY.json")
    configs = load_json(CHAINS_CONFIG)
    chains = chain_ids(); probes = probe_ids(); results = {c: result(c) for c in chains}
    probe_codes = probe_init_codes(probes)
    chain_rows = []
    for chain in chains:
        r = results[chain]
        url = r.get("rpc") or (configs.get(chain, {}).get("rpcs") or [{}])[0].get("url")
        chain_row = {"id": chain, "name": chain_name(chain), "chain_id": r.get("chain_id_expected", configs.get(chain, {}).get("chain_id")), "endpoint": host(url), "block": block_number(r), "timestamp": (r.get("block") or {}).get("timestamp_unix") if isinstance(r.get("block"), dict) else None, "profile_status": r.get("status", "unavailable")}
        if chain == "evmos":
            chain_row["note"] = "No public mainnet RPC found, per docs/endpoint-audit.md."
        chain_rows.append(chain_row)
    baseline = results["ethereum"]
    from scripts.differential_common import PROBE_DESCRIPTIONS
    probe_rows = []
    for p in probes:
        title, desc = PROBE_DESCRIPTIONS[p]
        probe_rows.append({"id": p, "name": title, "category": CATEGORY_OVERRIDES[p], "description": desc, "init_code": probe_codes[p], "ethereum_baseline": lossless(interpretation(baseline, p)), "sample_date": DATE})
    from scripts.build_expansion_data import build as build_expansion
    expansion_probes, expansion_cells = build_expansion(chains)
    for probe in expansion_probes:
        probe["ethereum_baseline"] = lossless(probe["ethereum_baseline"])
    for cell in expansion_cells:
        cell["value"] = lossless(cell["value"])
    probe_rows.extend(expansion_probes)
    all_probe_ids = probes + [probe["id"] for probe in expansion_probes]
    all_cells = matrix_cells(chains, probes) + expansion_cells
    findings = [add_headline(row, headline_payloads(results)) for row in parse_catalog()]
    payloads = headline_payloads(results)
    note = payloads["zksync-create2-docs-stale"]
    findings.append({"number": None, "label": "doc-only", "chain_scope": "zksync-era", "behavior": note["title"], "consequence": note.get("note", ""), "evidence_path": "results/2026-10-18/followup/headline-probes/REPORT.json", "evidence_paths": ["results/2026-10-18/followup/headline-probes/REPORT.json", "results/2026-10-18/followup/headline-probes/formula/ethereum/primary/ethereum.json", "results/2026-10-18/followup/headline-probes/formula/zksync-era/primary/zksync-era.json", "results/2026-10-18/followup/headline-probes/formula/arbitrum-one/primary/arbitrum-one.json"], "date": DATE, "headline": True, "slug": "zksync-create2-docs-stale", "headline_content": note})
    verification = verification_rounds()
    endpoint_rows = endpoint_hosts(chains, results)
    secondary_rows = secondary_endpoint_rows(configs)
    return {
        "meta": {"probe_date": summary["date"], "latest_probe_date": EXPANSION_DATE,
                 "evidence_dates": [DATE, EXPANSION_DATE], "chain_count": len(chains),
                 "probe_count": len(all_probe_ids), "endpoints": {"count": len(endpoint_rows), "hosts": endpoint_rows, "secondary": secondary_rows}, "verification_rounds": verification, "kit_command": "./probes/run.sh"},
        "chains": chain_rows, "probes": probe_rows,
        "matrix": {"chain_ids": chains, "probe_ids": all_probe_ids, "cells": all_cells},
        "gas_schedule": gas_schedule_section(chains, probe_rows, all_cells),
        "findings": findings, "checklist": checklist(),
    }


def gas_schedule_section(chains: list[str], probes: list[dict], cells: list[dict]) -> dict:
    """Heatmap-ready E29 grid; a ratio exists only for comparable operation gas."""
    gas_probes = [p for p in probes if p["category"] == "gas schedule"]
    item_ids = [p["id"] for p in gas_probes]
    items = [{"id": p["id"], "name": p["name"],
              "family": p["ethereum_baseline"]["family"],
              "phase": p["ethereum_baseline"]["phase"],
              "metric": p["ethereum_baseline"]["metric"],
              "ethereum_value": p["ethereum_baseline"]["gas"]} for p in gas_probes]
    comparable = {"ethereum-baseline", "same-as-ethereum", "confirmed-two-endpoints", "confirmed-later-block"}
    grid = []
    for cell in cells:
        if cell["probe"] not in item_ids:
            continue
        value = cell["value"] or {}
        ethereum_value = value.get("ethereum_gas")
        chain_value = value.get("gas")
        price_comparable = (value.get("status") in comparable and value.get("metric") == "gas_used"
                            and ethereum_value is not None and chain_value is not None
                            and int(ethereum_value) > 0)
        ratio = format(Decimal(chain_value) / Decimal(ethereum_value), ".6f") if price_comparable else None
        grid.append({"chain": cell["chain"], "item": cell["probe"],
                     "ethereum_value": ethereum_value, "chain_value": chain_value,
                     "ratio": ratio, "status": value.get("status"),
                     "metric": value.get("metric"), "evidence": cell["evidence"]})
    if len(grid) != len(chains) * len(item_ids):
        raise ValueError("gas schedule is not a complete chain × item grid")
    return {"date": EXPANSION_DATE, "chain_ids": chains, "item_ids": item_ids,
            "items": items, "cells": grid}


def verification_rounds() -> list[dict]:
    rounds = []
    for line in (ROOT / 'docs/verification.md').read_text().splitlines():
        cells = [cell.strip() for cell in line.split('|')]
        if len(cells) < 7 or not cells[1].isdigit(): continue
        verdict = cells[4]
        round_number = int(cells[1])
        date = '2026-10-18' if round_number == 1 else '2026-10-20' if round_number == 4 else '2026-10-19'
        evidence = 'docs/verification/round-4-sample.md' if round_number == 4 else 'docs/verification.md'
        rounds.append({'round': round_number, 'seed': int(cells[2]), 'sampled': int(cells[3]), 'correct': count_result(verdict, 'CORRECT'), 'wrong': sum(count_result(verdict, x) for x in ['NOT-A-DIVERGENCE', 'OVERSTATED-CONSEQUENCE', 'wrong']), 'unverifiable': count_result(verdict, 'UNVERIFIABLE'), 'date': date, 'result': verdict, 'evidence': evidence})
    return rounds


def count_result(result: str, pattern: str) -> int:
    match = re.search(rf"(\d+)\s+{pattern}", result, re.I)
    return int(match.group(1)) if match else 0


def main() -> int:
    out = ROOT / "site" / "data" / "data.json"
    out.write_text(json.dumps(build_data(), indent=2, sort_keys=False) + "\n", encoding="utf-8")
    print(f"wrote {out}")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())

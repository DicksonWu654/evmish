#!/usr/bin/env python3
"""Validate the public site data contract against the dated evidence."""
from __future__ import annotations

import json
import re
import sys
from decimal import Decimal
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from scripts.build_site_data import build_data  # noqa: E402

DATA_PATH = ROOT / "site" / "data" / "data.json"
ALLOWED_CLASSES = {"same", "differs", "unsupported/execution-failure", "rpc-rejected", "endpoint-artifact", "state-only", "unavailable"}
MAX_SAFE_INTEGER = 2**53 - 1
NUMBER_RE = re.compile(r"(?<![A-Za-z])(?:0x[0-9a-fA-F]+|\d[\d,]*)")
URL_RE = re.compile(r"(?:https?://|www\.)[^\s)]+")


def walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from walk_strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from walk_strings(item)


def walk_numbers(value, path="$", interpretation=False):
    """Yield unsafe JSON numbers and numeric interpretation values."""
    if isinstance(value, bool):
        return
    if isinstance(value, int):
        if value > MAX_SAFE_INTEGER:
            yield path, value
        if interpretation:
            raise SystemExit(f"EVM numeric value must be a decimal string: {path}")
    elif isinstance(value, dict):
        for key, item in value.items():
            yield from walk_numbers(item, f"{path}.{key}", interpretation=interpretation)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from walk_numbers(item, f"{path}[{index}]", interpretation=interpretation)
def result_text() -> str:
    return "\n".join(path.read_text(encoding="utf-8", errors="ignore") for path in (ROOT / "results").rglob("*") if path.is_file())


def validate_blog_numbers() -> None:
    blog = (ROOT / "blog" / "post.md").read_text(encoding="utf-8")
    source = result_text()
    url_spans = [m.span() for m in URL_RE.finditer(blog)]
    missing = []
    for match in NUMBER_RE.finditer(blog):
        if any(start <= match.start() < end for start, end in url_spans):
            continue  # pinned URL/commit identifiers are evidence locators
        token = match.group(0)
        normalized = token.replace(",", "")
        if token not in source and normalized not in source:
            missing.append(token)
    if missing:
        raise SystemExit("blog numeric evidence missing from results: " + ", ".join(sorted(set(missing))))


def main() -> int:
    if not DATA_PATH.exists():
        raise SystemExit(f"missing {DATA_PATH}")
    actual = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    expected = build_data()
    if actual != expected:
        raise SystemExit("data.json differs from deterministic build output")
    if any("/" + "home/" in s for s in walk_strings(actual)):
        raise SystemExit("data.json contains a local filesystem path")
    unsafe = list(walk_numbers(actual))
    if unsafe:
        raise SystemExit("JSON number exceeds Number.MAX_SAFE_INTEGER: " + unsafe[0][0])
    for probe in actual["probes"]:
        if not isinstance(probe.get("init_code"), str) or not re.fullmatch(r"0x[0-9a-fA-F]*", probe["init_code"]):
            raise SystemExit(f"probe init_code is not hex: {probe.get('id')}")
        description = probe.get("description")
        if not isinstance(description, str) or description.strip() == probe.get("name", "").strip() or not re.search(r"[.!?]$", description.strip()):
            raise SystemExit(f"probe description must be a distinct sentence: {probe.get('id')}")
        list(walk_numbers(probe.get("ethereum_baseline"), f"probes.{probe.get('id')}.ethereum_baseline", interpretation=True))
    for chain in actual["chains"]:
        endpoint = chain["endpoint"]
        if endpoint and ("/" in endpoint or ":" in endpoint or "?" in endpoint):
            raise SystemExit(f"endpoint is not host-only: {endpoint}")
        if chain["id"] == "evmos" and chain.get("note") != "No public mainnet RPC found, per docs/endpoint-audit.md.":
            raise SystemExit("Evmos endpoint gap note is missing or incorrect")
    endpoints = actual["meta"]["endpoints"]
    if endpoints["count"] != len(endpoints["hosts"]):
        raise SystemExit("endpoint count does not match host records")
    seen_hosts = set()
    for entry in endpoints["hosts"]:
        if not isinstance(entry, dict) or not isinstance(entry.get("host"), str):
            raise SystemExit("endpoint hosts must be host records")
        endpoint = entry["host"]
        if endpoint in seen_hosts:
            raise SystemExit(f"duplicate endpoint host: {endpoint}")
        seen_hosts.add(endpoint)
        if any(token in endpoint.lower() for token in ("testnet", "carrot")):
            raise SystemExit(f"testnet endpoint host is not allowed: {endpoint}")
        if entry.get("operator") not in {"chain", "third-party"}:
            raise SystemExit(f"unknown endpoint operator: {endpoint}")
        if entry["operator"] == "third-party" and not entry.get("provider"):
            raise SystemExit(f"third-party endpoint is missing provider: {endpoint}")
    secondary = endpoints.get("secondary")
    if not isinstance(secondary, list):
        raise SystemExit("secondary endpoints must be a list")
    secondary_hosts = set()
    for entry in secondary:
        required = {"chain", "host", "operator", "used_for"}
        if not isinstance(entry, dict) or not required <= entry.keys():
            raise SystemExit("secondary endpoint is missing required fields")
        endpoint = entry["host"]
        if endpoint in secondary_hosts:
            raise SystemExit(f"duplicate secondary endpoint host: {endpoint}")
        secondary_hosts.add(endpoint)
        if any(token in endpoint.lower() for token in ("testnet", "carrot")):
            raise SystemExit(f"testnet secondary endpoint host is not allowed: {endpoint}")
        if entry["operator"] not in {"chain", "third-party"}:
            raise SystemExit(f"unknown secondary endpoint operator: {endpoint}")
        if entry["operator"] == "third-party" and not entry.get("provider"):
            raise SystemExit(f"third-party secondary endpoint is missing provider: {endpoint}")
        if not isinstance(entry["used_for"], str) or not entry["used_for"].strip():
            raise SystemExit(f"secondary endpoint is missing used_for: {endpoint}")
        if entry.get("evidence") and not (ROOT / entry["evidence"].split("#", 1)[0]).exists():
            raise SystemExit(f"secondary endpoint evidence is missing: {entry['evidence']}")
    for verification in actual["meta"].get("verification_rounds", []):
        required = {"round", "seed", "sampled", "correct", "wrong", "unverifiable"}
        if not required <= verification.keys() or any(not isinstance(verification[key], int) for key in required):
            raise SystemExit("verification round is missing structured integer counts")
    round4 = [r for r in actual["meta"].get("verification_rounds", []) if r["round"] == 4]
    if len(round4) != 1 or (round4[0]["sampled"], round4[0]["correct"], round4[0]["wrong"]) != (20, 19, 1):
        raise SystemExit("independent review round-4 verification summary is missing or miscounted")
    cells = actual["matrix"]["cells"]
    if len(cells) != actual["meta"]["chain_count"] * actual["meta"]["probe_count"]:
        raise SystemExit("matrix is not a complete chain × probe product")
    if any(cell["class"] not in ALLOWED_CLASSES for cell in cells):
        raise SystemExit("matrix contains an unknown public class")
    for cell in cells:
        evidence = cell.get("evidence")
        if not isinstance(evidence, list) or not evidence:
            raise SystemExit(f"matrix cell has no evidence: {cell.get('chain')}/{cell.get('probe')}")
        for path in evidence:
            if path.startswith(("http://", "https://", "/")) or not (ROOT / path).exists():
                raise SystemExit(f"missing matrix evidence path: {path}")
        list(walk_numbers(cell.get("value"), f"matrix.{cell.get('chain')}.{cell.get('probe')}.value", interpretation=True))
    gas = actual.get("gas_schedule") or {}
    gas_ids = [p["id"] for p in actual["probes"] if p["category"] == "gas schedule"]
    if gas.get("chain_ids") != actual["matrix"]["chain_ids"] or gas.get("item_ids") != gas_ids:
        raise SystemExit("gas schedule axes do not match the source matrix")
    gas_cells = gas.get("cells") or []
    if len(gas_cells) != len(gas["chain_ids"]) * len(gas_ids):
        raise SystemExit("gas schedule is not a complete chain × item grid")
    matrix_by = {(c["chain"], c["probe"]): c for c in cells}
    seen_gas = set()
    comparable = {"ethereum-baseline", "same-as-ethereum", "confirmed-two-endpoints", "confirmed-later-block"}
    for cell in gas_cells:
        key = (cell["chain"], cell["item"])
        if key in seen_gas:
            raise SystemExit(f"duplicate gas schedule cell: {key}")
        seen_gas.add(key)
        source = matrix_by.get(key)
        if source is None or cell["evidence"] != source["evidence"]:
            raise SystemExit(f"gas schedule evidence does not match its probe cell: {key}")
        value = source["value"] or {}
        if (cell["status"], cell["metric"], cell["chain_value"], cell["ethereum_value"]) != (
                value.get("status"), value.get("metric"), value.get("gas"), value.get("ethereum_gas")):
            raise SystemExit(f"gas schedule values do not match their probe cell: {key}")
        allowed_ratio = (cell["status"] in comparable and cell["metric"] == "gas_used"
                         and cell["chain_value"] is not None and cell["ethereum_value"] is not None
                         and int(cell["ethereum_value"]) > 0)
        expected_ratio = (format(Decimal(cell["chain_value"]) / Decimal(cell["ethereum_value"]), ".6f")
                          if allowed_ratio else None)
        if cell["ratio"] != expected_ratio:
            raise SystemExit(f"gas schedule ratio is unsafe or incorrect: {key}")
        if key[1] in {"gas/call-value-empty/operation", "gas/value-call-stipend/child_gasleft"} and cell["ratio"] is not None:
            raise SystemExit(f"control or stipend has a price ratio: {key}")
    for cell in cells:
        value = cell.get("value") or {}
        if cell["probe"].startswith("precompile-vector/") and value.get("gas_scope") == "cap-exhausted-not-price":
            if value.get("status") != "call-failed" or not any(
                    int(gas) >= 10_000_000 for gas in (value.get("first_call_gas"), value.get("second_call_gas")) if gas is not None):
                raise SystemExit(f"precompile cap label lacks a failed bounded call: {cell['chain']}/{cell['probe']}")
    expected_checklist = build_data()["checklist"]
    if actual.get("checklist") != expected_checklist:
        raise SystemExit("checklist entries are truncated or do not match docs/checklist.md")
    if any(not isinstance(item, str) or not re.search(r"[.?]$", item.strip()) for item in actual["checklist"]):
        raise SystemExit("every checklist entry must end with . or ?")
    catalog_rows = [line for line in (ROOT / "CATALOG.md").read_text(encoding="utf-8").splitlines() if re.match(r"^\|\s*\d+\s*\|", line)]
    headline_slugs = {row["slug"] for row in actual["findings"] if row["headline"]}
    if len(actual["findings"]) != len(catalog_rows) + 1 or len(headline_slugs) != 6:
        raise SystemExit("findings/headline count does not match the catalog and headline set")
    for row in actual["findings"]:
        for path in row.get("evidence_paths", []):
            if path.startswith(("http://", "https://")) or path.startswith("/"):
                raise SystemExit(f"non-repository evidence path: {path}")
            if not (ROOT / path.split("#", 1)[0]).exists():
                raise SystemExit(f"missing evidence path: {path}")
    blog = (ROOT / "blog" / "post.md").read_text(encoding="utf-8")
    for row in actual["findings"]:
        content = row.get("headline_content")
        if content and content.get("raw_lines") and content["raw_lines"] not in blog:
            raise SystemExit(f"headline raw lines not found in blog: {row['slug']}")
        if content:
            for key in ("solidity_unsafe", "solidity_safe"):
                snippet = content.get(key)
                if snippet and snippet not in blog:
                    raise SystemExit(f"headline snippet not found in blog: {row['slug']} {key}")
    validate_blog_numbers()
    classes = {}
    for cell in cells:
        classes[cell["class"]] = classes.get(cell["class"], 0) + 1
    print(f"site data validation passed: {len(actual['chains'])} chains, {len(actual['probes'])} probes, {len(cells)} cells, {len(actual['findings'])} findings; classes={classes}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

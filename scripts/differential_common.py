"""Shared normalization for the differential catalog and confirmations."""

from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
DATE = "2026-10-18"
RESULTS = ROOT / "results" / DATE

PROBE_DESCRIPTIONS = {
    "push0": ("PUSH0 executes and returns zero", "The init code executes PUSH0, stores the zero word in memory, and returns it."),
    "number": ("NUMBER/header semantics", "The init code reads NUMBER, stores the block number in memory, and returns it."),
    "basefee": ("BASEFEE value semantics", "The init code reads BASEFEE, stores the value in memory, and returns it."),
    "chainid": ("CHAINID value", "The init code reads CHAINID, stores the chain identifier in memory, and returns it."),
    "deliberate-invalid": ("INVALID execution control", "The init code executes INVALID and should fail before returning a value."),
    "tstore-tload": ("TSTORE/TLOAD transient storage round trip", "The init code stores 42 at transient key 1, loads that key, and returns the word."),
    "mcopy": ("MCOPY memory copy", "The init code stores 42 at memory offset 0, copies 32 bytes to offset 32 with MCOPY, and returns the copy."),
    "blobhash": ("BLOBHASH(0) zero semantics", "The init code reads BLOBHASH(0) without a blob context, stores it, and returns the word."),
    "blobbasefee": ("BLOBBASEFEE value semantics", "The init code reads BLOBBASEFEE for the execution block, stores it, and returns the word."),
    "prevrandao": ("PREVRANDAO/header semantics", "The init code reads PREVRANDAO, stores the entropy word, and returns it for comparison with the block header."),
    "coinbase": ("COINBASE/header semantics", "The init code reads COINBASE, stores the fee-recipient address word, and returns it."),
    "gaslimit": ("GASLIMIT/header semantics", "The init code reads GASLIMIT, stores the block gas limit, and returns it."),
    "timestamp": ("TIMESTAMP/header semantics", "The init code reads TIMESTAMP, stores the block time, and returns it."),
    "blockhash-n-minus-1": ("BLOCKHASH(NUMBER-1) zero semantics", "The init code computes NUMBER minus 1, reads that block hash, and returns it."),
    "blockhash-n-minus-256": ("BLOCKHASH(NUMBER-256) zero semantics", "The init code computes NUMBER minus 256, reads that block hash, and returns it."),
    "blockhash-n-minus-257": ("BLOCKHASH(NUMBER-257) depth boundary", "The init code computes NUMBER minus 257, reads that block hash, and returns it."),
    "create": ("CREATE address formula", "The init code creates a child with CREATE and returns the creator and child address words."),
    "create2": ("CREATE2 address formula", "The init code creates a child with CREATE2 using salt 0x42 and returns the creator and child address words."),
    "oversized-runtime-create": ("24,577-byte runtime CREATE boundary", "The init code attempts to create a 24,577-byte runtime and returns zero when the size limit rejects it."),
    "cold-warm-extcodesize": ("Cold versus warm EXTCODESIZE gas", "The init code measures GAS around two EXTCODESIZE reads of the same EOA to compare cold and warm costs."),
    "estimate-gas": ("eth_estimateGas versus GAS", "The init code measures GAS around one EXTCODESIZE read so the runner can compare execution with eth_estimateGas."),
    "precompile-0x01-ecrecover": ("ECRECOVER vector/status", "The init code calls address 0x01 with a zeroed invalid-signature vector and returns call status and output words."),
    "precompile-0x02-sha256": ("SHA256 vector", "The init code calls address 0x02 with the bytes abc and returns call status and output words."),
    "precompile-0x03-ripemd160": ("RIPEMD160 vector", "The init code calls address 0x03 with the bytes abc and returns call status and output words."),
    "precompile-0x04-identity": ("IDENTITY vector", "The init code calls address 0x04 with the bytes abc and returns call status and output words."),
    "precompile-0x05-modexp": ("MODEXP vector", "The init code calls address 0x05 with the 2^3 mod 5 vector and returns call status and output words."),
    "precompile-0x06-bn128-add": ("BN128 addition vector", "The init code calls address 0x06 with the infinity-plus-infinity vector and returns call status and output words."),
    "precompile-0x07-bn128-mul": ("BN128 multiplication vector", "The init code calls address 0x07 with the infinity-times-zero vector and returns call status and output words."),
    "precompile-0x08-bn128-pairing": ("BN128 pairing empty-vector control", "The init code calls address 0x08 with an empty pairing vector and returns call status and output words."),
    "precompile-0x09-blake2f": ("BLAKE2F invalid-length control", "The init code calls address 0x09 with empty invalid-length input and returns call status and output words."),
    "precompile-0x0a-kzg-point-evaluation": ("KZG point-evaluation invalid-length control", "The init code calls address 0x0a with empty invalid-length input and returns call status and output words."),
    "precompile-0x0b-address-0b": ("Address 0x0b empty-input behavior", "The init code calls address 0x0b with empty input and returns call status and output words."),
    "precompile-0x0c-address-0c": ("Address 0x0c empty-input behavior", "The init code calls address 0x0c with empty input and returns call status and output words."),
    "precompile-0x0d-address-0d": ("Address 0x0d empty-input behavior", "The init code calls address 0x0d with empty input and returns call status and output words."),
    "precompile-0x0e-address-0e": ("Address 0x0e empty-input behavior", "The init code calls address 0x0e with empty input and returns call status and output words."),
    "precompile-0x0f-address-0f": ("Address 0x0f empty-input behavior", "The init code calls address 0x0f with empty input and returns call status and output words."),
    "precompile-0x10-address-10": ("Address 0x10 empty-input behavior", "The init code calls address 0x10 with empty input and returns call status and output words."),
    "precompile-0x11-address-11": ("Address 0x11 empty-input behavior", "The init code calls address 0x11 with empty input and returns call status and output words."),
    "precompile-0x100-p256verify": ("P256VERIFY candidate at 0x100", "The init code calls candidate address 0x100 with empty input and returns call status and output words."),
    "extcode-eoa": ("EXTCODESIZE on an EOA candidate", "The init code reads EXTCODESIZE and EXTCODEHASH for the fixed EOA candidate and returns both words."),
    "extcode-empty": ("EXTCODESIZE on an empty account", "The init code reads EXTCODESIZE and EXTCODEHASH for the fixed empty-account candidate and returns both words."),
    "extcode-delegated-7702": ("EXTCODESIZE on an EIP-7702 delegated account", "The init code reads EXTCODESIZE and EXTCODEHASH for the fixed delegated-account candidate and returns both words."),
    "extcode-system-contract": ("EXTCODESIZE on a system candidate", "The init code reads EXTCODESIZE and EXTCODEHASH for the fixed system-contract candidate and returns both words."),
}

HEADER_PROBES = {"number", "timestamp", "coinbase", "gaslimit", "prevrandao"}
ZERO_PROBES = {"blobhash", "blockhash-n-minus-1", "blockhash-n-minus-256"}
BLOCK_CONTEXT_PROBES = HEADER_PROBES | {"basefee", "blockhash-n-minus-1", "blockhash-n-minus-256", "blockhash-n-minus-257"}
BASEFEE_SIMULATION_PROBES = {"basefee"}

# This probe uses one address captured as delegated on Ethereum and reuses it
# on every target. A different account state is evidence about that address,
# not a chain-wide EIP-7702 semantic. Keep it visible in the matrix, but never
# promote it to a catalog divergence.
STATE_COMPARISON_PROBES = {"extcode-delegated-7702"}

# Round-1/round-2 verification found that Cronos and HyperEVM endpoints return
# moving values for historical block tags. The endpoint-quality manifest
# records the observation; affected block-context cells remain matrix warnings
# and are excluded from catalog rows.
UNSTABLE_ENDPOINT_PROBES = {
    (chain, probe)
    for chain in ("cronos", "hyperevm")
    for probe in ({"number", "timestamp", "basefee", "blockhash-n-minus-1", "blockhash-n-minus-256", "blockhash-n-minus-257", "prevrandao"} | ({"gaslimit"} if chain == "hyperevm" else set()))
}

# Somnia exposes a zero mixHash and no prevRandao header field. Keep the live
# non-zero observation as doc-only context rather than a header divergence.
UNVERIFIABLE_PROBES = {("somnia", "prevrandao")}


def ethereum_basefee_is_simulation(baseline: dict | None) -> bool:
    """The dated baseline called BASEFEE without a gas price and returned zero."""

    value = interpretation(baseline or {}, "basefee")
    return bool(value and value.get("status") == "ok" and value.get("uint256") == 0 and value.get("header_value"))


def load_result(chain: str, root: Path = RESULTS) -> dict:
    path = root / chain / f"{chain}.json"
    if not path.exists():
        return {"chain": chain, "status": "unavailable", "probes": {}, "rpc": None}
    return json.loads(path.read_text(encoding="utf-8"))


def probe_names(root: Path = RESULTS) -> list[str]:
    summary = json.loads((root / "SUMMARY.json").read_text(encoding="utf-8"))
    return list(summary["probe_names"])


def chain_names(root: Path = RESULTS) -> list[str]:
    summary = json.loads((root / "SUMMARY.json").read_text(encoding="utf-8"))
    return [row["chain"] for row in sorted(summary["chains"], key=lambda row: row["chain"])]


def interpretation(result: dict, name: str) -> dict | None:
    return result.get("probes", {}).get(name, {}).get("interpretation")


def semantic_signature(name: str, value: dict | None) -> tuple:
    """Normalize moving values while retaining behaviorally meaningful fields."""

    if not value:
        return ("missing",)
    status = value.get("status")
    if status == "rpc-rejected":
        return ("rejected", value.get("error_class"))
    if status and status.startswith("execution-failure"):
        return ("execution-failure", value.get("error_class"))
    if status != "ok":
        return ("missing", status)
    if name in HEADER_PROBES:
        return ("header", value.get("header_matches"))
    if name in ZERO_PROBES:
        return ("zero", value.get("uint256") == 0)
    if name == "blockhash-n-minus-257":
        return ("depth-257", value.get("matches_expected_zero"))
    if name in {"basefee", "blobbasefee"}:
        # Exact fee values move every block and are not a portability
        # distinction. Preserve whether the opcode is zero/nonzero instead.
        return ("fee-zero", value.get("uint256") == 0)
    if name == "chainid":
        # A chain-specific numeric ID is expected. The differential question
        # is whether CHAINID executes, which is represented by the status.
        return ("chainid-executes",)
    if name in {"create", "create2"}:
        return ("formula", value.get("formula_matches"))
    if name == "oversized-runtime-create":
        return ("size-rejected", value.get("uint256") == 0)
    if name == "cold-warm-extcodesize":
        return ("gas", value.get("gas_delta"), value.get("warm_gas_delta"))
    if name == "estimate-gas":
        return ("gas", value.get("gas_delta"))
    if name.startswith("precompile-"):
        return ("precompile", value.get("precompile_call_status"), tuple(value.get("precompile_output_hex") or []))
    if name.startswith("extcode-"):
        size = value.get("extcodesize")
        return ("code-size", size, bool(size))
    return ("value", value.get("uint256"))


def classify_against_baseline(name: str, baseline: dict | None, candidate: dict | None) -> str:
    """Return the matrix cell; RPC rejection is visible but is not a divergence row."""

    if not candidate:
        return "unavailable"
    candidate_status = candidate.get("status")
    if candidate_status == "rpc-rejected":
        return "rejected"
    baseline_sig = semantic_signature(name, baseline)
    candidate_sig = semantic_signature(name, candidate)
    if candidate_sig[0] == "execution-failure" and baseline and baseline.get("status") == "ok":
        return "unsupported"
    if candidate_sig[0] in {"missing", "rejected"}:
        return "unavailable" if candidate_sig[0] == "missing" else "rejected"
    if candidate_sig == baseline_sig:
        return "same"
    return "diff"


def confirmation_candidates(root: Path = RESULTS) -> dict[str, list[str]]:
    baseline = load_result("ethereum", root)
    names = probe_names(root)
    candidates: dict[str, list[str]] = {}
    for chain in chain_names(root):
        if chain == "ethereum":
            continue
        result = load_result(chain, root)
        selected = []
        for name in names:
            if name in STATE_COMPARISON_PROBES or name in BASEFEE_SIMULATION_PROBES or (chain, name) in UNSTABLE_ENDPOINT_PROBES:
                continue
            cell = classify_against_baseline(name, interpretation(baseline, name), interpretation(result, name))
            if cell in {"diff", "unsupported"}:
                selected.append(name)
        if selected:
            candidates[chain] = selected
    return candidates


def short_value(value: object) -> str:
    if value is None:
        return "—"
    text = str(value)
    return text if len(text) <= 48 else text[:45] + "…"


def difference_text(name: str, baseline: dict | None, candidate: dict | None, cell: str) -> str:
    description = PROBE_DESCRIPTIONS[name][0]
    if cell == "unsupported":
        return f"{description}: Ethereum executes the probe; the target returned {candidate.get('status')} ({candidate.get('error_class')})."
    if not candidate or not baseline:
        return f"{description}: target evidence is unavailable."
    bs = semantic_signature(name, baseline)
    cs = semantic_signature(name, candidate)
    if name in HEADER_PROBES:
        return f"{description}: Ethereum header_matches={bs[-1]}, target header_matches={cs[-1]}."
    if name in {"create", "create2"}:
        return f"{description}: Ethereum formula_matches={bs[-1]}, target formula_matches={cs[-1]}."
    if name == "oversized-runtime-create":
        return f"{description}: Ethereum size_rejected={bs[-1]}, target size_rejected={cs[-1]}."
    if name in {"cold-warm-extcodesize", "estimate-gas"}:
        return f"{description}: Ethereum gas signature={bs[1:]}, target gas signature={cs[1:]}."
    if name.startswith("precompile-"):
        return f"{description}: Ethereum call/output signature={short_value(bs[1:])}, target={short_value(cs[1:])}."
    if name.startswith("extcode-"):
        return f"{description}: Ethereum code-size signature={bs[1:]}, target={cs[1:]}."
    return f"{description}: Ethereum signature={short_value(bs[1:])}, target={short_value(cs[1:])}."

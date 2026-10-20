#!/usr/bin/env python3
"""Build the differential catalog and matrix from dated probe evidence."""

from __future__ import annotations

import json
from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parent.parent
DATE = "2026-10-18"
RESULTS = ROOT / "results" / DATE
sys.path.insert(0, str(ROOT / "scripts"))

from differential_common import (  # noqa: E402
    BASEFEE_SIMULATION_PROBES,
    PROBE_DESCRIPTIONS,
    STATE_COMPARISON_PROBES,
    UNVERIFIABLE_PROBES,
    UNSTABLE_ENDPOINT_PROBES,
    ethereum_basefee_is_simulation,
    classify_against_baseline,
    chain_names,
    difference_text,
    interpretation,
    load_result,
    probe_names,
)
from build_expansion_catalog import build as build_expansion_rows  # noqa: E402


SOURCE_ROWS = [
    ("L1-to-L2 sender aliasing", "OP and Arbitrum message paths can represent an L1 sender through an alias; compare messenger rules before using onlyOwner.", "https://docs.arbitrum.io/how-arbitrum-works/deep-dives/l1-to-l2-messaging#address-aliasing; https://docs.optimism.io/op-stack/transactions/transaction-flow"),
    ("Sequencer ordering and finality", "Rollup ordering and finality windows are chain protocols, not Ethereum block-finality guarantees.", "https://docs.optimism.io/op-stack/transactions/transaction-finality; https://docs.arbitrum.io/how-arbitrum-works/deep-dives/finality"),
    ("Blast ETH yield/rebasing model", "Value movement and yield accounting need chain-specific balance and transfer tests.", "https://metalayerlabs.mintlify.app/building/guides/eth-yield"),
    ("Celo fee currencies", "Fee payment can use configured currencies, so native-asset assumptions in tooling need review.", "https://docs.celo.org/build/fee-abstraction/add-fee-currency"),
    ("Mantle fee/native-asset model", "The fee mechanism and native-value paths are chain-specific and stateful.", "https://docs.mantle.xyz/network/system-information/fee-mechanism"),
    ("TRON 0x09 precompile collision", "TVM's precompile/address set includes a BatchValidateSign path at 0x09.", "https://developers.tron.network/docs/tvm-vs-evm"),
    ("Monad gas-limit charging", "Monad documents charging by gas limit rather than ordinary gas used.", "https://docs.monad.xyz/developer-essentials/gas-pricing"),
    ("Monad reserve balance", "Reserve-balance rules can reject calls or transactions that Ethereum would admit.", "https://docs.monad.xyz/developer-essentials/reserve-balance"),
    ("MegaETH dual gas model", "Compute/storage meters and RPC estimation require a MegaETH target endpoint.", "https://docs.megaeth.com/developer-docs/overview.md"),
    ("MegaETH mini-blocks and EVM blocks", "Mini-block and EVM-block timing creates a second confirmation context.", "https://docs.megaeth.com/mini-block.md"),
    ("HyperEVM dual-block architecture", "Big/small block selection changes gas and ordering assumptions.", "https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/hyperevm/dual-block-architecture"),
    ("Tempo TIP-20 fee currency", "Tempo documents stablecoin fee payment and no native gas token.", "https://tempo.xyz/developers/docs/network"),
]


PRIOR_ART_ROWS = [
    (
        "[mds1/evm-diff opcode data](https://github.com/mds1/evm-diff/blob/6beeefe8a91484cf9e3c23d59b364ef3bba673b4/script/data/feature/opcodes.json), `6beeefe8a91484cf9e3c23d59b364ef3bba673b4`",
        "Its Arbitrum BLOBBASEFEE entry agrees with the dated Arbitrum RPC rejection.",
        "No contradiction; the live evidence adds the block-tagged request and error class.",
    ),
    (
        "[shemnon/evm-directory Arbitrum row](https://github.com/shemnon/evm-directory/blob/f06b85450e87772221ff636aa3df29ae20f563b6/chains/arbitrum/chain.yaml), `f06b85450e87772221ff636aa3df29ae20f563b6`",
        "Its source-pinned rows complement the live Arbitrum NUMBER/header and gas observations.",
        "No direct contradiction found; coverage gap is recorded rather than promoted to a conflict.",
    ),
]

followup_SOURCE_EVIDENCE = {
    "L1-to-L2 sender aliasing": "results/2026-10-18/followup/history/REPORT.json",
    "Monad gas-limit charging": "results/2026-10-18/followup/history/REPORT.json",
    "TRON 0x09 precompile collision": "results/2026-10-18/followup/history/REPORT.json",
}


def evidence_link(path: str, label: str) -> str:
    return f"[{label}]({path})"


def confirmation_result(chain: str) -> dict | None:
    path = RESULTS / "differential-confirmation" / chain / f"{chain}.json"
    if not path.exists():
        return None
    return json.loads(path.read_text(encoding="utf-8"))


def matrix_cell(chain: str, name: str, baseline: dict, result: dict) -> str:
    """Classify a cell while retaining known comparability failures explicitly."""

    candidate = interpretation(result, name)
    if (chain, name) in UNSTABLE_ENDPOINT_PROBES:
        return "unstable-endpoint" if candidate else "unavailable"
    if (chain, name) in UNVERIFIABLE_PROBES:
        return "unverifiable" if candidate else "unavailable"
    if name in BASEFEE_SIMULATION_PROBES and ethereum_basefee_is_simulation(baseline):
        if not candidate:
            return "unavailable"
        if candidate.get("status") == "rpc-rejected":
            return "rejected"
        return "rpc-simulation"
    if name in STATE_COMPARISON_PROBES:
        if not candidate:
            return "unavailable"
        if candidate.get("status") == "rpc-rejected":
            return "rejected"
        return "state-only"
    return classify_against_baseline(name, interpretation(baseline, name), candidate)


def value_text(value: object) -> str:
    if value is None:
        return "unknown"
    if isinstance(value, int):
        return str(value)
    return str(value)


def concrete_consequence(name: str, chain: str, baseline: dict | None, candidate: dict | None, cell: str) -> str:
    """Describe only the measured control and its bounded review implication."""

    if not candidate or not baseline:
        return f"The {name} control has no complete target and Ethereum comparison in the retained evidence."
    if cell == "unsupported":
        return f"The {name} creation call returned an EVM execution failure on {chain} while Ethereum executed it; this probe establishes a VM compatibility boundary, not the cause of the failure."
    if name in {"number", "timestamp", "coinbase", "gaslimit", "prevrandao"}:
        return (
            f"The {name} control returned {value_text(candidate.get('uint256'))} on {chain}; its captured header field was "
            f"{value_text(candidate.get('header_value'))}, while Ethereum's corresponding control returned "
            f"{value_text(baseline.get('uint256'))} against {value_text(baseline.get('header_value'))}. Consumers must use the target's observed header relationship."
        )
    if name in {"basefee", "blobbasefee"}:
        return (
            f"The {name} control returned {value_text(candidate.get('uint256'))} on {chain}, with captured header value "
            f"{value_text(candidate.get('header_value'))}; Ethereum returned {value_text(baseline.get('uint256'))} with header "
            f"{value_text(baseline.get('header_value'))}. Fee logic needs a target-specific value check."
        )
    if name in {"cold-warm-extcodesize", "estimate-gas"}:
        return (
            f"The {name} control measured gas delta {value_text(candidate.get('gas_delta'))}"
            + (f" and warm delta {value_text(candidate.get('warm_gas_delta'))}" if name == "cold-warm-extcodesize" else "")
            + f" on {chain}, versus Ethereum's {value_text(baseline.get('gas_delta'))}; treat this as a measured gas-schedule or estimator difference."
        )
    if name.startswith("precompile-"):
        target_status = value_text(candidate.get("precompile_call_status"))
        base_status = value_text(baseline.get("precompile_call_status"))
        target_words = candidate.get("precompile_output_words") or []
        base_words = baseline.get("precompile_output_words") or []
        return (
            f"The supplied {name} control returned CALL status {target_status} with {len(target_words)} output words on {chain}, "
            f"versus status {base_status} with {len(base_words)} output words on Ethereum; this establishes only the tested vector's dispatch behavior."
        )
    if name.startswith("extcode-"):
        return (
            f"The fixed {name} address probe observed EXTCODESIZE {value_text(candidate.get('extcodesize'))} on {chain}, "
            f"versus {value_text(baseline.get('extcodesize'))} on Ethereum; address state and predeploy registries must be checked on the target."
        )
    if name in {"create", "create2"}:
        return f"The {name} control reported formula_matches={value_text(candidate.get('formula_matches'))} on {chain}, versus {value_text(baseline.get('formula_matches'))} on Ethereum; predicted deployment addresses need a target-chain check."
    if name == "oversized-runtime-create":
        return f"The 24,577-byte CREATE control reported size_rejected={value_text(candidate.get('uint256') == 0)} on {chain}, versus {value_text(baseline.get('uint256') == 0)} on Ethereum; the boundary needs a target deployment test."
    target = candidate.get("uint256")
    base = baseline.get("uint256")
    return f"The {name} control returned {value_text(target)} on {chain}, versus {value_text(base)} on Ethereum; integrations should test this observed result on the target."


def matrix_markdown(chains: list[str], names: list[str], baseline: dict, results: dict[str, dict]) -> str:
    lines = [
        "# Differential probe matrix",
        "",
        "<!-- GENERATED BY scripts/build_catalog.py FROM results/2026-10-18 -->",
        "",
        "Each cell compares one chain's normalized probe semantics with Ethereum's. `same` means the normalized behavior matches; `diff` is a different value or semantic relationship; `unsupported` is an EVM execution failure where Ethereum executes; `rejected` is an RPC-level rejection and is not a catalog divergence; `unavailable` has no usable endpoint result.",
        "",
        "| Probe | " + " | ".join(chains) + " |",
        "| --- | " + " | ".join("---" for _ in chains) + " |",
    ]
    for name in names:
        cells = []
        base_interp = interpretation(baseline, name)
        for chain in chains:
            cells.append(matrix_cell(chain, name, baseline, results[chain]))
        lines.append("| `" + name + "` | " + " | ".join(cells) + " |")
    lines.extend(["", "Generated from the primary result files; later-block confirmation evidence is required before a `diff` or `unsupported` cell becomes a catalog row.", ""])
    return "\n".join(lines)


def main() -> None:
    names = probe_names(RESULTS)
    chains = chain_names(RESULTS)
    baseline = load_result("ethereum")
    results = {chain: load_result(chain) for chain in chains}
    matrix = matrix_markdown(chains, names, baseline, results)
    matrix_path = RESULTS / "DIFFERENTIAL_MATRIX.md"
    matrix_path.write_text(matrix, encoding="utf-8")

    rows: list[tuple[str, str, str, str, str, str]] = []
    missing_confirmations = []
    unconfirmed = []
    for chain in chains:
        if chain == "ethereum":
            continue
        confirmation = confirmation_result(chain)
        for name in names:
            # Empty-input BLS controls are superseded by a real G1ADD vector.
            if chain in {"avalanche-c-chain", "blast", "hyperevm", "scroll"} and name.startswith("precompile-0x") and name.split("-")[1] in {f"0x{x:02x}" for x in range(11, 18)}:
                continue
            # A high-gas E31 creation succeeded on Somnia; MegaETH remains
            # gas-bound, so neither old execution failure proves a size rule.
            if name == "oversized-runtime-create" and chain in {"megaeth", "somnia"}:
                continue
            base_interp = interpretation(baseline, name)
            candidate_interp = interpretation(results[chain], name)
            cell = matrix_cell(chain, name, baseline, results[chain])
            if (chain, name) in UNVERIFIABLE_PROBES:
                observed = f"PREVRANDAO returned non-zero entropy {value_text((candidate_interp or {}).get('uint256'))} on {chain}; the RPC header exposes no `prevRandao` field to compare, so this is not a proven header divergence."
                consequence = "The target returned non-zero entropy, but no header field is available for comparison; this control does not establish a security or randomness consequence."
                primary_path = f"results/{DATE}/{chain}/{chain}.json"
                later_path = f"results/{DATE}/differential-confirmation/{chain}/{chain}.json"
                evidence = "; ".join((evidence_link(primary_path, "primary"), evidence_link(later_path, "later-block observation"), evidence_link("docs/verification.md", "round-3 review")))
                rows.append(("doc-only", chain, observed, consequence, evidence, DATE))
                continue
            if cell not in {"diff", "unsupported"}:
                continue
            if confirmation is None or name not in confirmation.get("probes", {}):
                missing_confirmations.append(f"{chain}/{name}")
                continue
            confirmed_interp = interpretation(confirmation, name)
            confirmed_cell = classify_against_baseline(name, base_interp, confirmed_interp)
            if confirmed_cell not in {"diff", "unsupported"}:
                unconfirmed.append(f"{chain}/{name}: primary={cell}, later={confirmed_cell}")
                continue
            primary_path = f"results/{DATE}/{chain}/{chain}.json"
            later_path = f"results/{DATE}/differential-confirmation/{chain}/{chain}.json"
            block = confirmation.get("block_number") or "unknown"
            observed = difference_text(name, base_interp, candidate_interp, cell) + f" Later-block confirmation at {block} retained the {confirmed_cell} classification."
            consequence = concrete_consequence(name, chain, base_interp, candidate_interp, cell)
            evidence = "; ".join((evidence_link(primary_path, "primary"), evidence_link(later_path, "later-block confirmation")))
            if name == "oversized-runtime-create" and chain in {"polygon-pos", "monad", "berachain", "celo"}:
                from build_expansion_catalog import read
                life = next(r for r in read("lifecycle/MATRIX.csv") if r["chain"] == chain and r["case"] == "runtime-24577")
                if life["status"] != "observed" or life["later_block"] != "same" or "\"created\": true" not in life["outcome"]:
                    raise SystemExit(f"new runtime-size control did not confirm {chain}")
                evidence += "; " + evidence_link(f"results/2026-10-20/lifecycle/{life['initial_evidence']}", "new runtime control")
                evidence += "; " + evidence_link(f"results/2026-10-20/lifecycle/{life['later_evidence']}", "new later block")
                observed += " The 2026-10-20 24,577-byte runtime control also created a child."
            rows.append(("probe-verified", chain, observed, consequence, evidence, DATE))

    if missing_confirmations or unconfirmed:
        details = missing_confirmations + unconfirmed
        raise SystemExit("differential catalog confirmation gate failed: " + "; ".join(details[:12]) + ("; …" if len(details) > 12 else ""))

    rows.extend(build_expansion_rows())

    for divergence, consequence, source in SOURCE_ROWS:
        links = "; ".join(evidence_link(url.strip(), "official source") for url in source.split("; "))
        links += "; " + evidence_link("docs/top10.md", "local context")
        if divergence in followup_SOURCE_EVIDENCE:
            links += "; " + evidence_link(followup_SOURCE_EVIDENCE[divergence], "followup evidence")
        rows.append(("source-verified", "multiple / source scope", divergence, consequence, links, DATE))

    lines = [
        "# Differential EVM divergence catalog",
        "",
        "This catalog is generated from the 2026-10-18 primary/confirmation probes and curated 2026-10-20 gas, vector, and lifecycle sweeps. The three new full matrices retain equal, failed, and gas-bound cells; catalog rows are selected measured differences, not an exhaustive gas-price table. RPC-only rejections, unavailable endpoints, Ethereum baseline rows, and generic profile rows are not catalog divergences.",
        "",
        "Labels: `probe-verified` is a live read-only RPC observation confirmed at a later block (a second endpoint is named only when available); `source-verified` is an official source claim accessed on 2026-10-18; `doc-only` is retained observation context whose semantic comparison is unresolved. Read-only creation simulations do not establish transaction admission. A rejected RPC call is recorded in the matrix as `rejected`, never upgraded to unsupported VM behavior. `state-only` marks a fixed-address account comparison; `unstable-endpoint` marks failed fixed-tag stability; `rpc-simulation` marks the Ethereum BASEFEE no-gas-price artifact.",
        "",
        f"Catalog coverage: **{len(rows)} rows** ({sum(row[0] == 'probe-verified' for row in rows)} probe-verified, {sum(row[0] == 'source-verified' for row in rows)} source-verified, {sum(row[0] == 'doc-only' for row in rows)} doc-only). The differential matrix is [generated here](results/{DATE}/DIFFERENTIAL_MATRIX.md).",
        "",
        "Focused evidence: [CREATE/code-size probes](results/2026-10-18/followup/headline-probes/REPORT.json), [all-chain opcode coverage](results/2026-10-18/followup/OPCODE_COVERAGE.json), [7702 history status](results/2026-10-18/followup/EIP7702_HISTORY.json), [gas schedule](results/2026-10-20/gas-schedule/MATRIX.csv), [precompile vectors](results/2026-10-20/precompile-sweep/MATRIX.csv), [lifecycle](results/2026-10-20/lifecycle/MATRIX.csv), [chain-history evidence](results/2026-10-18/followup/history/REPORT.json), [endpoint-quality record](results/2026-10-18/ENDPOINT_QUALITY.json), and [RPC simulation record](results/2026-10-18/RPC_SIMULATION.json).",
        "",
        "| # | Evidence label | Chain / scope | Divergence or observed behavior | Security consequence | Evidence | Date |",
        "|---:|---|---|---|---|---|---|",
    ]
    for index, row in enumerate(rows, 1):
        lines.append("| " + str(index) + " | " + " | ".join(row) + " |")

    lines.extend(
        [
            "",
            "## Prior-art contradictions and coverage",
            "",
            "Prior art is credited rather than treated as a race. The table records pinned comparisons and coverage gaps; the earlier MegaETH chain-ID conflict was an endpoint-selection error and is removed by the mainnet audit.",
            "",
            "| Prior artifact and pinned revision | Probe comparison | Finding |",
            "|---|---|---|",
        ]
    )
    for row in PRIOR_ART_ROWS:
        lines.append("| " + " | ".join(row) + " |")
    lines.extend(
        [
            "",
            "## Reading and updating this file",
            "",
            "Run `./probes/run.sh` to create a new dated matrix, run `python3 scripts/run_differential_confirmations.py` to reconfirm primary differences, then regenerate this file with `python3 scripts/build_catalog.py`. Do not promote a `rejected` or `unavailable` cell to a divergence row without VM evidence.",
            "",
        ]
    )
    (ROOT / "CATALOG.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote differential catalog with {len(rows)} rows and matrix {matrix_path}")


if __name__ == "__main__":
    main()

# Creation-probe prototype

`./probes/run.sh [YYYY-MM-DD] [--chains ethereum,monad]` reruns the creation,
gas-schedule, funded value-call, precompile, and lifecycle probes with read-only `eth_call` requests
whose transaction object has no `to` field. The `data` bytes are
contract-creation init code; the original library's snippets return one
32-byte word (except the deliberate failure control). The runner walks every
entry in `chains.json`, records the exact JSON-RPC
request and response, endpoint, observed block number/hash/timestamp, and an
interpretation in `results/<date>/<chain>/`. It also writes a Markdown coverage
table at `results/<date>/SUMMARY.md` and the Ethereum baseline vectors in
`results/<date>/KNOWN_ANSWERS.json`.

The registry covers the 27 chains in the handoff, with a source URL and access
date for each listed public endpoint. Evmos has an explicit no-endpoint reason
when no no-key EVM RPC is available; it remains in the coverage table. No keys,
signing, transactions, or deployments are used. Requests are spaced at 0.60
seconds per endpoint and retry HTTP 429 responses with exponential backoff.

The library currently contains 43 creation probes: fork-gated opcodes and
block context; three BLOCKHASH depths; 18 precompile/address vectors (0x01
through 0x11 and 0x100); CREATE/CREATE2 formula checks; EXTCODE probes for EOA,
empty, EIP-7702 delegated, and system candidates; an oversized CREATE; cold and
warm access deltas; and an `eth_estimateGas` comparison. OP, Arbitrum, zkSync,
Scroll, and Linea fee-oracle candidates are recorded as direct read-only
`eth_call`s. Every probe result receives a compact Ethereum-mainnet baseline
comparison; differing values are retained as evidence rather than treated as
failures.

## focused-probe-29 gas schedule

The [gas schedule method and findings](../docs/gas-schedule.md) describe the
123 additional timed cases and link the chain-by-item matrix. A single
`./probes/run.sh` invocation collects their initial raw responses along with
the original probe library. To confirm measured gas differences after a later
block and check listed second endpoints, run:

```sh
python3 probes/run_gas_schedule.py --date 2026-10-20 --phase confirm
python3 probes/run_gas_schedule.py --date 2026-10-20 --phase secondary
python3 probes/run_value_call.py --date 2026-10-20 --phase confirm
python3 probes/run_value_call.py --date 2026-10-20 --phase secondary
python3 scripts/build_gas_schedule.py --date 2026-10-20
```

These commands process or collect evidence; none is an independent verifier.

## focused-probe-30 precompiles and focused-probe-31 lifecycle

The [precompile sweep](../docs/precompile-sweep.md) checks 18 pinned
known-answer vectors and malformed or short-input controls, then records
CALL-inclusive gas. The [lifecycle sweep](../docs/lifecycle-sweep.md) tests
runtime and init-code boundaries, call depth, same-call SELFDESTRUCT,
return/revert data, failed-CREATE nonce, and value sent to a precompile. Their
initial results and matrices are collected by `./probes/run.sh`. To repeat the
saved later-block and listed second-endpoint observations, run:

```sh
python3 probes/run_precompile_sweep.py --phase confirm
python3 probes/run_precompile_sweep.py --phase secondary
python3 probes/build_precompile_matrix.py
python3 probes/run_lifecycle_sweep.py --phase confirm
python3 probes/run_lifecycle_sweep.py --phase secondary
python3 probes/build_lifecycle_matrix.py
```

The lifecycle fixture's source is `lifecycle_probe.sol`; the checked-in
`lifecycle_bytecode.json` keeps `./probes/run.sh` Python-only. To inspect the
compiler output, use `solc --evm-version paris --optimize --combined-json bin
probes/lifecycle_probe.sol` with solc 0.8.36. The runner checks the source hash
before using that bytecode. These probes remain read-only on public endpoints.

| probe | init code | interpretation |
| --- | --- | --- |
| `push0` | `5f60005260206000f3` | A 32-byte zero means opcode `PUSH0` executed; an execution error means the opcode is unavailable on that VM. |
| `number` | `4360005260206000f3` | The returned integer is the execution block's `NUMBER`; compare it with the recorded header. |
| `basefee` | `4860005260206000f3` | The returned integer is `BASEFEE`; zero can be a valid chain value. |
| `chainid` | `4660005260206000f3` | The returned integer is the EVM `CHAINID`; compare it with the registry and `eth_chainId`. |
| `deliberate-invalid` | `fe` | An execution error is expected and proves the endpoint reached EVM execution. |

An HTTP/transport failure or a JSON-RPC error before execution is recorded as
`rpc-rejected`; an EVM execution error is recorded as `execution-failure` (or
`execution-failure-expected` for `deliberate-invalid`). This distinction keeps
“unsupported opcode” separate from “the RPC rejected a no-`to` call.”

Ten-line interpretation note:

1. The no-`to` transaction object asks the node to execute `data` as init code.
2. A 32-byte `result` is the init code's returned memory, not a transaction receipt.
3. `PUSH0` returning zero shows that opcode executed successfully on that VM.
4. `NUMBER` is compared with the recorded header to expose L2/L1 numbering semantics.
5. `BASEFEE` is the block context value; zero is valid and does not mean the probe failed.
6. `CHAINID` is the EVM opcode result and is compared with `eth_chainId`.
7. The raw return is retained before integer decoding so leading zero bytes remain auditable.
8. `deliberate-invalid` must return an EVM execution error and is the failing control probe.
9. An unsupported opcode is an execution error after the RPC accepted the call shape.
10. HTTP/transport or pre-execution JSON-RPC errors are `rpc-rejected`, not unsupported opcodes.

## CI drift wrapper

The optional [manual workflow](../.github/workflows/probe-drift.yml) accepts a
comma-separated chain list, runs the same read-only runner, and compares stable
probe semantics with `results/2026-10-18/CI_BASELINE.json`. Moving block values
such as timestamps and raw `NUMBER` returns are intentionally ignored; status,
known-answer outputs, formula checks, account code observations, and gas deltas
remain drift signals. A mismatch exits nonzero and prints the chain/probe that
changed.

To refresh the committed baseline after reviewing a deliberate change:

```sh
python3 scripts/build_ci_baseline.py
```

To run the same check locally against the committed matrix:

```sh
python3 scripts/check_ci_drift.py \
  --baseline results/2026-10-18/CI_BASELINE.json \
  --results results/2026-10-18 \
  --chains ethereum,arbitrum-one,op-mainnet
```

The focused-probe-12 independent-endpoint pass is reproducible with:

```sh
python3 scripts/run_secondary_probes.py
```

It runs only the headline probes against the `role=secondary` endpoints in
`chains.json`, writes raw evidence below
`results/2026-10-18/secondary/`, and emits `COMPARISON.json` plus `SUMMARY.md`.
Chain-ID mismatches are marked uncomparable; RPC rejections remain rejections.

The focused focused-probe-16 `PREVRANDAO` follow-up is reproducible with:

```sh
python3 scripts/run_entropy_followup.py
python3 scripts/validate_entropy_followup.py
```

It reruns the probe on the primary and registered secondary endpoints for
Ethereum and zkSync Era, writes four endpoint result files plus raw requests
under `results/2026-10-18/entropy-followup/`, and records `match`,
`rpc-rejected`, or `header-disagreement` without changing catalog labels.

The focused-probe-17 chain-specific fee-oracle follow-up is reproducible with:

```sh
python3 scripts/run_fee_oracle_followup.py
python3 scripts/validate_fee_oracle_followup.py
```

It reruns the OP GasPriceOracle and Arbitrum ArbGasInfo read calls on each
chain's primary and registered secondary endpoint. Direct oracle values and
raw returns are retained alongside block context; moving latest-block values
are not promoted to a catalog claim.

The focused-probe-18 block-context boundary follow-up is reproducible with:

```sh
python3 scripts/run_block_context_followup.py
python3 scripts/validate_block_context_followup.py
```

It reruns `NUMBER`, `TIMESTAMP`, and `BLOCKHASH(NUMBER-1/256/257)` on the
primary and registered secondary endpoint for Ethereum, Arbitrum One, and OP
Mainnet. Header comparisons, the depth-257 zero rule, endpoint errors, and raw
responses are retained without changing catalog labels.

The focused-probe-19 fork-opcode follow-up is reproducible with:

```sh
python3 scripts/run_fork_opcode_followup.py
python3 scripts/validate_fork_opcode_followup.py
```

It reruns `PUSH0`, `TSTORE/TLOAD`, and `MCOPY` on Base's primary and
registered secondary endpoint. `execution-failure` remains distinct from
`rpc-rejected` in both the endpoint results and comparison report.

The differential catalog rebuild uses the confirmed result set with:

```sh
python3 scripts/run_differential_confirmations.py
python3 scripts/build_catalog.py
python3 scripts/validate_catalog.py
```

It writes `results/2026-10-18/DIFFERENTIAL_MATRIX.md`, keeps `same`, `diff`,
`unsupported`, `rejected`, and `unavailable` cells visible, and emits catalog
rows only for confirmed `diff` or `unsupported` cells.

The followup headline evidence is reproducible with:

```sh
python3 scripts/run_followup_headline_probes.py
python3 scripts/build_followup_coverage.py
python3 scripts/run_followup_history.py
python3 scripts/validate_followup.py
```

The focused reports cover CREATE/CREATE2, code-size boundaries, all-chain
fork-opcode and delegated-account status, OP/Arbitrum history samples, Monad
receipt gas fields, and recorded RPC/history gaps.

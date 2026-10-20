# Top-10 divergence checks and new-chain specifics

Checked 2026-10-18. A `confirmed` verdict means the current probe or an
official source directly supports the statement. `changed` means the probe
narrowed or contradicted the original hypothesis. `unverifiable` means the
read-only method could not establish it; that is not a claim that the behavior
is unsupported. Source links were accessed on 2026-10-18. Creation probes are
read-only `eth_call`s with no `to`; no transaction was signed, sent, or deployed.

Stateful follow-ups that would need a local node or a two-step fixture are
listed in [`docs/needs-deploy.md`](needs-deploy.md); none were run against a
public network.

## Top-10 dangers

| # | Danger | Verdict | Evidence |
|---:|---|---|---|
| 1 | L1-to-L2 sender aliasing can break `onlyOwner` | **confirmed** (source-verified) | [Arbitrum L1-to-L2 messaging](https://docs.arbitrum.io/how-arbitrum-works/deep-dives/l1-to-l2-messaging#address-aliasing), accessed 2026-10-18; [OP transaction flow](https://docs.optimism.io/op-stack/transactions/transaction-flow), accessed 2026-10-18 |
| 2 | CREATE/CREATE2 deployer formulas differ on zkSync or TRON | **changed** (probe-verified) | [Ethereum baseline](../results/2026-10-18/ethereum/ethereum.json), [zkSync Era](../results/2026-10-18/zksync-era/zksync-era.json), and [Arbitrum](../results/2026-10-18/arbitrum-one/arbitrum-one.json) both report `formula_matches: true`; [TRON](../results/2026-10-18/tron/tron.json) records the RPC's `QUANTITY not supported` rejection before execution |
| 3 | Fork-gated opcodes pass Ethereum CI but fail elsewhere | **confirmed** (probe-verified) | [Arbitrum BLOBBASEFEE raw response](../results/2026-10-18/arbitrum-one/endpoints/arb1-arbitrum-io-rpc/raw/blobbasefee.response.json) says `BLOBBASEFEE is not supported on Arbitrum`; the full [coverage table](../results/2026-10-18/SUMMARY.md) retains all opcode outcomes |
| 4 | Rollup L1-data fees underfund relayers or paymasters | **confirmed** (probe-verified) | [OP GasPriceOracle results](../results/2026-10-18/op-mainnet/op-mainnet.json), [Arbitrum ArbGasInfo results](../results/2026-10-18/arbitrum-one/arbitrum-one.json), and the zkSync/Scroll oracle reverts are retained in each chain JSON and raw oracle files |
| 5 | Block clock/hash semantics break timelocks, TWAPs, or randomness | **confirmed** (probe-verified) | [Arbitrum result](../results/2026-10-18/arbitrum-one/arbitrum-one.json) reports `NUMBER=26221369` while the L2 header is `0x1ec262a3` (`516055715`); its timestamp matches the header. Arbitrum documents the distinction in [block numbers and time](https://docs.arbitrum.io/arbitrum-essentials/arbitrum-vs-ethereum/block-numbers-and-time), accessed 2026-10-18 |
| 6 | Native value, rebasing ETH, fee currencies, and `.transfer()` differ | **unverifiable** (source-verified limits) | Blast documents ETH yield in [Receive and claim ETH yield](https://metalayerlabs.mintlify.app/building/guides/eth-yield), Celo documents fee currencies in [Adding Fee Currencies](https://docs.celo.org/build/fee-abstraction/add-fee-currency), and Mantle documents its fee mechanism at [Fee mechanism](https://docs.mantle.xyz/network/system-information/fee-mechanism); accessed 2026-10-18. A no-state-change call cannot establish value-transfer or rebasing behavior. |
| 7 | System precompile/address collisions change call meaning | **confirmed** (source-verified; live call blocked) | TRON's [TVM versus EVM](https://developers.tron.network/docs/tvm-vs-evm) page documents the precompile set including `0x09`/`BatchValidateSign`, accessed 2026-10-18. The [TRON raw probes](../results/2026-10-18/tron/tron.json) record `invalid address`/quantity RPC rejection, so no unsupported live execution claim is made. |
| 8 | AA, nonce rules, EIP-7702, and EOA code checks need account-state review | **confirmed** (Ethereum context; cross-chain comparison removed) | [Ethereum EIP-7702 account probe](../results/2026-10-18/ethereum/ethereum.json) records the `0xef0100` delegation prefix and `EXTCODESIZE=23`; the EOA candidate is size 0. The fixed candidate comparison on other chains is state-only and is not a VM divergence. The normative [EIP-7702](https://eips.ethereum.org/EIPS/eip-7702) was accessed 2026-10-18. |
| 9 | Sequencer ordering and finality are not Ethereum finality | **confirmed** (source-verified) | OP documents [transaction finality](https://docs.optimism.io/op-stack/transactions/transaction-finality), Arbitrum documents [finality](https://docs.arbitrum.io/how-arbitrum-works/deep-dives/finality) and [sequencer transaction flow](https://docs.arbitrum.io/how-arbitrum-works/deep-dives/sequencer-transaction-flow); all accessed 2026-10-18. A read-only EVM call cannot prove a future finality window. |
| 10 | RPC simulation can disagree with execution context | **confirmed** (probe-verified) | Ethereum's [BASEFEE probe](../results/2026-10-18/ethereum/ethereum.json) returned zero while the captured header `baseFeePerGas` was nonzero; TRON records pre-execution no-`to` rejection and Arbitrum records an unsupported BLOBBASEFEE error. These are distinct RPC/VM outcomes in the raw records. |

### 1. Sender aliasing

The source documentation is sufficient to confirm that an L1-originated
message can be represented by an aliased L2 sender. The security consequence is
an authorization check that compares `msg.sender` to an L1 address without
using the chain's messenger or aliasing rules. This item needs a cross-domain
message or local rollup node for a behavioral exploit demonstration; no such
deployment was made here.

### 2. CREATE and CREATE2

The probe returns the creator and child addresses and checks the Ethereum RLP
and `0xff || creator || salt || keccak(init_code)` formulas. Ethereum, zkSync
Era, Arbitrum, and OP all matched the formula at their captured blocks. TRON's
JSON-RPC adapter rejected the block quantity before running the init code, so
the prior claim of a TRON formula difference remains unverified rather than
being promoted to a finding.

### 3. Fork-gated opcodes

The matrix distinguishes an EVM execution failure from an RPC rejection. The
Arbitrum BLOBBASEFEE response is an explicit unsupported-opcode-style error;
the TRON rows are RPC parameter errors. TSTORE/TLOAD, MCOPY, BLOBHASH, and
BLOBBASEFEE outcomes for every endpoint are in the dated chain JSON files.

### 4. Two-dimensional fees

OP's `GasPriceOracle` calls returned raw L1-base-fee and L1-fee words, and
Arbitrum's `ArbGasInfo` calls returned L1 estimates. zkSync and Scroll oracle
candidate calls reverted, while Linea's candidate returned an empty result;
these are observations of the selected public endpoints, not claims that the
chains have no fee mechanism. The exact raw requests and responses are under
each endpoint's `raw/oracle-*` directory.

### 5. Clock and hash semantics

The Arbitrum `NUMBER` result is the L1 number while `eth_getBlockByNumber`
reports the L2 header number. Timestamp, PREVRANDAO, COINBASE, GASLIMIT, and
three BLOCKHASH depths are checked against the same captured block tag, so a
moving `latest` tag cannot create a false mismatch.

### 6. Native value and fee currencies

The cited Blast, Celo, and Mantle documentation establishes why these need
chain-specific review, but proving a value-transfer or rebasing difference
requires stateful calls or a deployment. The catalog therefore records this as
unverifiable by the current read-only kit.

### 7. Precompile collisions

The precompile library calls `0x01` through `0x11` and `0x100` with vectors and
records status plus output. TRON's adapter rejects the no-`to` creation shape,
so the source-backed `0x09` collision is retained as a source claim and not
misrepresented as a live probe result.

### 8. EIP-7702 and code checks

The Ethereum account context records a live delegated account (`0xef0100`
prefix), an EOA candidate, an empty account candidate, and a system-contract
candidate. The paired EXTCODESIZE/EXTCODEHASH results make the common
`extcodesize == 0` EOA heuristic auditable; they do not claim that all account
abstraction implementations share one representation.

### 9. Finality and sequencers

The official OP and Arbitrum references describe sequencer ordering and their
finality processes. The probe kit can measure block context and RPC behavior,
but it cannot force a reorg, wait for a dispute window, or submit an L1
message under the read-only rules.

### 10. RPC simulation

Every result retains the RPC URL, block tag, header, raw return, and error
class. The Ethereum BASEFEE mismatch is therefore a reproducible simulation
observation at the captured block, while TRON's `invalid address` and
Arbitrum's unsupported BLOBBASEFEE remain clearly separate failure classes.

## New-chain specifics

| Chain / claim | Verdict | Evidence |
|---|---|---|
| Monad: gas limit is charged rather than gas used | **confirmed** (source-verified) | Monad [gas pricing](https://docs.monad.xyz/developer-essentials/gas-pricing), accessed 2026-10-18; it explicitly describes gas-limit charging. |
| Monad: reserve-balance rules can revert | **confirmed** (source-verified) | Monad [reserve balance](https://docs.monad.xyz/developer-essentials/reserve-balance), accessed 2026-10-18. |
| Monad: cold access is about 10,100 gas | **confirmed** (probe-verified) | Monad [cold/warm probe](../results/2026-10-18/monad/monad.json) reports `gas_delta=10111`; its [opcode pricing](https://docs.monad.xyz/developer-essentials/opcode-pricing), accessed 2026-10-18, lists 10,100 for cold account access. |
| Monad: 128 KB code limit | **unverifiable** (probe-verified limit) | The 24,577-byte oversized CREATE [returned a nonzero address](../results/2026-10-18/monad/monad.json), proving only that this smaller test succeeds; it does not establish the upper limit. |
| MegaETH: dual compute/storage gas and gas estimation differences | **confirmed** (source-verified) | MegaETH [developer overview](https://docs.megaeth.com/developer-docs/overview.md), accessed 2026-10-18, documents the dual gas model and warns Ethereum estimators can undercount; [matrix result](../results/2026-10-18/megaeth/megaeth.json) records the probe context. |
| MegaETH: mini-blocks versus EVM blocks and real-time timestamps | **confirmed** (source-verified) | MegaETH [mini-blocks](https://docs.megaeth.com/mini-block.md), accessed 2026-10-18, describes ~10 ms mini-blocks and ~1 s EVM blocks; the current `NUMBER`/`TIMESTAMP` probes are compatible observations, not a timing benchmark. |
| MegaETH: exact 60k intrinsic/compute-cap rule | **unverifiable** | The current read-only library does not isolate intrinsic gas or the post-context compute cap; no exact numeric claim is promoted. |
| HyperEVM: dual big/small blocks | **confirmed** (source-verified) | Hyperliquid [dual-block architecture](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/hyperevm/dual-block-architecture), accessed 2026-10-18. |
| HyperEVM: CoreWriter reads and ordering | **unverifiable** | The [HyperEVM documentation](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/hyperevm), accessed 2026-10-18, is the source reference; this matrix has no CoreWriter-specific call and makes no runtime claim. |
| Tempo: TIP-20 tokens and stablecoin fee currency | **confirmed** (source-verified) | Tempo [network overview](https://tempo.xyz/developers/docs/network), accessed 2026-10-18, states there is no native gas token and fees use supported TIP-20 stablecoins; the current matrix records Tempo EVM context. |
| Tempo: transfer-policy registry/precompile behavior | **unverifiable** | The current precompile vectors do not target Tempo's TIP-20 registry; use the [Tempo network/token docs](https://tempo.xyz/developers/docs/network/tokens), accessed 2026-10-18, as the pinned source until a dedicated read-only call is added. |
| Plasma: custom gas-token behavior | **unverifiable** (source-only) | Plasma [network fees](https://www.plasma.org/docs/plasma-chain/network-information/network-fees), accessed 2026-10-18, describes the standard `Gas Used × Gas Price` formula and says custom gas-token support is being built. No current fee-payment divergence is established by the read-only matrix. |
| Arbitrum: `block.number` is the L1 number | **confirmed** (probe-verified) | [Arbitrum result](../results/2026-10-18/arbitrum-one/arbitrum-one.json) shows the mismatch directly; the official [block numbers and time](https://docs.arbitrum.io/arbitrum-essentials/arbitrum-vs-ethereum/block-numbers-and-time) page was accessed 2026-10-18. |

These verdicts deliberately separate a documented chain rule, a measured
endpoint response, and a behavior that would require a stateful or adversarial
test. The raw matrix and source URLs provide the next step for each item. The
acceptance audit covers all 10 danger rows and 13 new-chain-specific rows; each
row has a verdict and at least one dated local result or official source link.

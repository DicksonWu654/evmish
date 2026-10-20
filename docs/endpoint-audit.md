# Mainnet endpoint audit

Audited 2026-10-19 after round-3 verification identified MegaETH testnet evidence. Each primary endpoint was checked against the chain ID in the registry and its documented endpoint-listing source. `mainnet-id-match` means the returned ID equals the expected mainnet ID; it does not claim finality or archive support.

| Chain | Expected mainnet ID | Source | Returned ID | Endpoint | Verdict | Evidence |
|---|---:|---|---:|---|---|---|
| ethereum | 1 | [https://www.publicnode.com/](https://www.publicnode.com/) | 1 | `https://ethereum-rpc.publicnode.com` (third-party: PublicNode) | **mainnet-id-match** | `results/2026-10-18/ethereum/ethereum.json` |
| tron | 728126428 | [https://developers.tron.network/docs/connect-to-the-tron-network](https://developers.tron.network/docs/connect-to-the-tron-network) | 728126428 | `https://api.trongrid.io/jsonrpc` | **mainnet-id-match** | `results/2026-10-18/tron/tron.json` |
| zksync-era | 324 | [https://docs.zksync.io/zksync-era/tooling/node-providers](https://docs.zksync.io/zksync-era/tooling/node-providers) | 324 | `https://mainnet.era.zksync.io` | **mainnet-id-match** | `results/2026-10-18/zksync-era/zksync-era.json` |
| arbitrum-one | 42161 | [https://docs.arbitrum.io/build-decentralized-apps/reference/node-providers](https://docs.arbitrum.io/build-decentralized-apps/reference/node-providers) | 42161 | `https://arb1.arbitrum.io/rpc` | **mainnet-id-match** | `results/2026-10-18/arbitrum-one/arbitrum-one.json` |
| op-mainnet | 10 | [https://docs.optimism.io/app-developers/reference/rpc-providers](https://docs.optimism.io/app-developers/reference/rpc-providers) | 10 | `https://mainnet.optimism.io` | **mainnet-id-match** | `results/2026-10-18/op-mainnet/op-mainnet.json` |
| base | 8453 | [https://docs.base.org/base-chain/api-reference/rpc-overview](https://docs.base.org/base-chain/api-reference/rpc-overview) | 8453 | `https://mainnet.base.org` | **mainnet-id-match** | `results/2026-10-18/base/base.json` |
| polygon-pos | 137 | [https://www.publicnode.com/](https://www.publicnode.com/) | 137 | `https://polygon-bor-rpc.publicnode.com` (third-party: PublicNode) | **mainnet-id-match** | `results/2026-10-18/polygon-pos/polygon-pos.json` |
| bnb-smart-chain | 56 | [https://docs.bnbchain.org/bnb-smart-chain/developers/json_rpc/json-rpc-endpoint/](https://docs.bnbchain.org/bnb-smart-chain/developers/json_rpc/json-rpc-endpoint/) | 56 | `https://bsc-dataseed.binance.org` | **mainnet-id-match** | `results/2026-10-18/bnb-smart-chain/bnb-smart-chain.json` |
| avalanche-c-chain | 43114 | [https://build.avax.network/docs/quickstart/avalanche-consensus](https://build.avax.network/docs/quickstart/avalanche-consensus) | 43114 | `https://api.avax.network/ext/bc/C/rpc` | **mainnet-id-match** | `results/2026-10-18/avalanche-c-chain/avalanche-c-chain.json` |
| scroll | 534352 | [https://docs.scroll.io/](https://docs.scroll.io/) | 534352 | `https://rpc.scroll.io` | **mainnet-id-match** | `results/2026-10-18/scroll/scroll.json` |
| linea | 59144 | [https://docs.linea.build/network](https://docs.linea.build/network) | 59144 | `https://rpc.linea.build` | **mainnet-id-match** | `results/2026-10-18/linea/linea.json` |
| mantle | 5000 | [https://docs.mantle.xyz/network](https://docs.mantle.xyz/network) | 5000 | `https://rpc.mantle.xyz` | **mainnet-id-match** | `results/2026-10-18/mantle/mantle.json` |
| blast | 81457 | [https://metalayerlabs.mintlify.app/building/network-information](https://metalayerlabs.mintlify.app/building/network-information) | 81457 | `https://rpc.blast.io` | **mainnet-id-match** | `results/2026-10-18/blast/blast.json` |
| monad | 143 | [https://docs.monad.xyz/developer-essentials/network-information](https://docs.monad.xyz/developer-essentials/network-information) | 143 | `https://rpc.monad.xyz` | **mainnet-id-match** | `results/2026-10-18/monad/monad.json` |
| megaeth | 4326 | [https://docs.megaeth.com/developer-docs/rpc](https://docs.megaeth.com/developer-docs/rpc) | 4326 | `https://mainnet.megaeth.com/rpc` | **mainnet-id-match** | `results/2026-10-18/megaeth/megaeth.json` |
| hyperevm | 999 | [https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/hyperevm](https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/hyperevm) | 999 | `https://rpc.hyperliquid.xyz/evm` | **mainnet-id-match** | `results/2026-10-18/hyperevm/hyperevm.json` |
| tempo | 4217 | [https://tempo.xyz/developers/docs/network](https://tempo.xyz/developers/docs/network) | 4217 | `https://rpc.tempo.xyz` | **mainnet-id-match** | `results/2026-10-18/tempo/tempo.json` |
| plasma | 9745 | [https://docs.plasma.to/](https://docs.plasma.to/) | 9745 | `https://rpc.plasma.to` | **mainnet-id-match** | `results/2026-10-18/plasma/plasma.json` |
| berachain | 80094 | [https://docs.berachain.com/nodes/operations/self-hosted-rpc](https://docs.berachain.com/nodes/operations/self-hosted-rpc) | 80094 | `https://rpc.berachain.com` | **mainnet-id-match** | `results/2026-10-18/berachain/berachain.json` |
| sei-evm | 1329 | [https://docs.sei.io/evm/networks](https://docs.sei.io/evm/networks) | 1329 | `https://evm-rpc.sei-apis.com` | **mainnet-id-match** | `results/2026-10-18/sei-evm/sei-evm.json` |
| somnia | 5031 | [https://docs.somnia.network/](https://docs.somnia.network/) | 5031 | `https://api.infra.mainnet.somnia.network` | **mainnet-id-match** | `results/2026-10-18/somnia/somnia.json` |
| celo | 42220 | [https://docs.celo.org/operate/operators/public-rpc-node](https://docs.celo.org/operate/operators/public-rpc-node) | 42220 | `https://forno.celo.org` | **mainnet-id-match** | `results/2026-10-18/celo/celo.json` |
| taiko | 167000 | [https://docs.taiko.xyz/network/differences-from-ethereum](https://docs.taiko.xyz/network/differences-from-ethereum) | 167000 | `https://rpc.mainnet.taiko.xyz` | **mainnet-id-match** | `results/2026-10-18/taiko/taiko.json` |
| cronos | 25 | [https://docs.cronos.com/for-dapp-developers/chain-integration/public-rpc-endpoints](https://docs.cronos.com/for-dapp-developers/chain-integration/public-rpc-endpoints) | 25 | `https://evm.cronos.org` | **mainnet-id-match** | `results/2026-10-18/cronos/cronos.json` |
| kaia | 8217 | [https://docs.kaia.io/references/json-rpc/](https://docs.kaia.io/references/json-rpc/) | 8217 | `https://public-en.node.kaia.io` | **mainnet-id-match** | `results/2026-10-18/kaia/kaia.json` |
| gnosis | 100 | [https://docs.gnosischain.com/tools/rpc](https://docs.gnosischain.com/tools/rpc) | 100 | `https://rpc.gnosischain.com` | **mainnet-id-match** | `results/2026-10-18/gnosis/gnosis.json` |
| evmos | 9001 | [https://docs.evmos.org/](https://docs.evmos.org/) | — | `—` | **no-public-mainnet-rpc** | `results/2026-10-18/evmos/evmos.json` |

## MegaETH correction


The audit is an endpoint and chain-ID check. It does not establish that every RPC supports historical tags or archive queries; those limitations remain in `docs/verification.md` and endpoint-quality evidence.

## Third-party providers

- `https://arbitrum-one.publicnode.com` — third-party: PublicNode.
- `https://base.publicnode.com` — third-party: PublicNode.
- `https://cloudflare-eth.com` — third-party: Cloudflare.
- `https://ethereum-rpc.publicnode.com` — third-party: PublicNode.
- `https://klaytn.drpc.org` — third-party: dRPC.
- `https://megaeth.drpc.org` — third-party: dRPC.
- `https://monad.drpc.org` — third-party: dRPC.
- `https://optimism.publicnode.com` — third-party: PublicNode.
- `https://polygon-bor-rpc.publicnode.com` — third-party: PublicNode.
- `https://polygon.drpc.org` — third-party: dRPC.
- `https://sei-evm-rpc.publicnode.com` — third-party: PublicNode.
- `https://somnia.publicnode.com` — third-party: PublicNode.
- `https://tempo.drpc.org` — third-party: dRPC.
- `https://zksync.drpc.org` — third-party: dRPC.

Historical correction: `https://carrot.megaeth.com/rpc` returned chain ID 6343 and was testnet. That evidence is omitted. Active MegaETH evidence uses mainnet chain ID 4326.

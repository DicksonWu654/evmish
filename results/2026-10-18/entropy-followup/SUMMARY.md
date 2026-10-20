# PREVRANDAO entropy follow-up (2026-10-18)

This focused pass reran the `PREVRANDAO` creation probe on the primary and independent secondary endpoint for Ethereum and zkSync Era. Each endpoint was queried at its own latest block. Raw requests and responses are retained below the linked result paths.

| Chain | Primary | Secondary | Primary block | Secondary block | Primary VM status | Secondary VM status | Header semantics | Result evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ethereum | [https://ethereum-rpc.publicnode.com](ethereum/primary/ethereum.json) | [https://cloudflare-eth.com](ethereum/secondary/ethereum.json) | 0x1901ce2 | — | ok | rpc-rejected | **rpc-rejected** | [ethereum raw evidence](ethereum/primary/endpoints/ethereum-rpc-publicnode-com) / [ethereum secondary raw evidence](ethereum/secondary/endpoints/cloudflare-eth-com) |
| ↳ differences | — | — | — | — | — | — | `[{"field": "status", "primary": "ok", "secondary": "rpc-rejected"}, {"field": "error_class", "primary": null, "secondary": "jsonrpc"}, {"field": "uint256", "primary": 18885316680498289337291817282235810165935516964337885988781116750490932047928, "secondary": null}, {"field": "header_value", "primary": 18885316680498289337291817282235810165935516964337885988781116750490932047928, "secondary": null}, {"field": "header_matches", "primary": true, "secondary": null}]` | — |
| zksync-era | [https://mainnet.era.zksync.io](zksync-era/primary/zksync-era.json) | [https://zksync.drpc.org](zksync-era/secondary/zksync-era.json) | 0x45306bd | 0x45306bd | ok | ok | **header-disagreement** | [zksync-era raw evidence](zksync-era/primary/endpoints/mainnet-era-zksync-io) / [zksync-era secondary raw evidence](zksync-era/secondary/endpoints/zksync-drpc-org) |

`match` means both endpoints reached the probe successfully and each opcode result matched its captured header. `rpc-rejected` records an endpoint-level rejection without treating it as an unsupported VM opcode. `header-disagreement` records a successful probe whose opcode result does not match the endpoint's captured header, or a disagreement between endpoints. Dynamic values are retained in `COMPARISON.json` but are not compared as drift signals across moving latest blocks.

The catalog label is unchanged by this follow-up; review the raw evidence before making any claim upgrade.

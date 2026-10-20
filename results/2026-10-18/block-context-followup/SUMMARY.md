# Block-context boundary follow-up (2026-10-18)

This pass reran `NUMBER`, `TIMESTAMP`, and `BLOCKHASH(NUMBER-1/256/257)` on the primary and independent secondary endpoints for Ethereum, Arbitrum One, and OP Mainnet. Raw requests and block headers are retained for every endpoint.

| Chain | Primary | Secondary | Blocks | Overall | Probe classifications | Evidence |
| --- | --- | --- | --- | --- | --- | --- |
| ethereum | [https://ethereum-rpc.publicnode.com](ethereum/primary/ethereum.json) | [https://cloudflare-eth.com](ethereum/secondary/ethereum.json) | 0x1901d2d / — | **rpc-rejected** | `number`=rpc-rejected; `timestamp`=rpc-rejected; `blockhash-n-minus-1`=rpc-rejected; `blockhash-n-minus-256`=rpc-rejected; `blockhash-n-minus-257`=rpc-rejected | [ethereum primary raw](ethereum/primary/endpoints/ethereum-rpc-publicnode-com) / [ethereum secondary raw](ethereum/secondary/endpoints/cloudflare-eth-com) |
| arbitrum-one | [https://arb1.arbitrum.io/rpc](arbitrum-one/primary/arbitrum-one.json) | [https://arbitrum-one.publicnode.com](arbitrum-one/secondary/arbitrum-one.json) | 0x1ec2b706 / 0x1ec2b727 | **header-disagreement** | `number`=header-disagreement; `timestamp`=match; `blockhash-n-minus-1`=match; `blockhash-n-minus-256`=match; `blockhash-n-minus-257`=match | [arbitrum-one primary raw](arbitrum-one/primary/endpoints/arb1-arbitrum-io-rpc) / [arbitrum-one secondary raw](arbitrum-one/secondary/endpoints/arbitrum-one-publicnode-com) |
| op-mainnet | [https://mainnet.optimism.io](op-mainnet/primary/op-mainnet.json) | [https://optimism.publicnode.com](op-mainnet/secondary/op-mainnet.json) | 0x970a9e1 / 0x970a9e5 | **match** | `number`=match; `timestamp`=match; `blockhash-n-minus-1`=match; `blockhash-n-minus-256`=match; `blockhash-n-minus-257`=match | [op-mainnet primary raw](op-mainnet/primary/endpoints/mainnet-optimism-io) / [op-mainnet secondary raw](op-mainnet/secondary/endpoints/optimism-publicnode-com) |

`rpc-rejected` preserves an endpoint-level rejection and does not imply an unsupported opcode. `header-disagreement` records a probe result that does not match its captured `NUMBER`/`TIMESTAMP` header, a different header relationship between endpoints, or a different depth-257 zero result. Dynamic block values are retained but are not compared as drift signals across moving latest blocks.

The catalog labels remain unchanged by this follow-up.

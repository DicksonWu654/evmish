# Chain-specific fee-oracle follow-up (2026-10-18)

This pass reran the OP Mainnet GasPriceOracle and Arbitrum ArbGasInfo read calls on their primary and independent secondary public RPC endpoints. Every endpoint retains its block context and raw request/response files.

| Chain | Primary | Secondary | Blocks | Comparison | Oracle observations | Raw evidence |
| --- | --- | --- | --- | --- | --- | --- |
| op-mainnet | [https://mainnet.optimism.io](op-mainnet/primary/op-mainnet.json) | [https://optimism.publicnode.com](op-mainnet/secondary/op-mainnet.json) | 0x970a8cf / 0x970a8d1 | **match** | `op-gaspriceoracle-l1BaseFee`=match; `op-gaspriceoracle-getL1Fee`=match | [op-mainnet primary](op-mainnet/primary/endpoints/mainnet-optimism-io) / [op-mainnet secondary](op-mainnet/secondary/endpoints/optimism-publicnode-com) |
| arbitrum-one | [https://arb1.arbitrum.io/rpc](arbitrum-one/primary/arbitrum-one.json) | [https://arbitrum-one.publicnode.com](arbitrum-one/secondary/arbitrum-one.json) | 0x1ec2afc2 / 0x1ec2afe7 | **match** | `arb-gasinfo-l1-base-fee-estimate`=match; `arb-gasinfo-l1-gas-price-estimate`=match | [arbitrum-one primary](arbitrum-one/primary/endpoints/arb1-arbitrum-io-rpc) / [arbitrum-one secondary](arbitrum-one/secondary/endpoints/arbitrum-one-publicnode-com) |

`match` means both endpoints returned the same oracle status and error class. Raw return values and decoded integers are retained even when they differ at moving latest blocks; those changes are reported as `value_changed_at_moving_block`, not promoted to a portability claim. RPC rejection remains distinct from VM execution failure.

The catalog labels remain unchanged by this follow-up.

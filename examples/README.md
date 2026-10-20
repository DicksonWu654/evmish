# Security examples

These examples turn the catalog's measured or source-backed divergence classes
into small Solidity review fixtures. Each file contains an intentionally unsafe
assumption and a safer pattern that makes the chain-specific dependency
explicit. They are teaching fixtures, not production libraries.

| File | Divergence class | Catalog evidence |
| --- | --- | --- |
| `01_fork_gated_opcodes.sol` | Cancun opcodes, blobs, and fork activation | [rows 6-9](../CATALOG.md#L16-L19), [Ethereum matrix](../results/2026-10-18/ethereum/ethereum.json) |
| `02_chain_id_and_signatures.sol` | Chain ID and replay protection | [row 4](../CATALOG.md#L14), [Ethereum matrix](../results/2026-10-18/ethereum/ethereum.json) |
| `03_cross_domain_sender.sol` | OP/Arbitrum sender aliasing and messenger context | [row 71](../CATALOG.md#L81), [top-10](../docs/top10.md) |
| `04_clock_hash_finality.sol` | L2 block numbers, clocks, hash windows, and finality | [rows 2, 10, 14-16, 72, 85](../CATALOG.md#L12-L26), [top-10](../docs/top10.md) |
| `05_fee_and_gas.sol` | L1 data fees, gas estimation, and chain gas charging | [rows 20-21, 77-80](../CATALOG.md#L30-L31), [matrix](../results/2026-10-18/monad/monad.json) |
| `06_create_addresses.sol` | CREATE2/deployer address formulas | [rows 17-18](../CATALOG.md#L27-L28), [matrix](../results/2026-10-18/ethereum/ethereum.json) |
| `07_precompiles_and_system_addresses.sol` | Precompile and system-address collisions | [rows 22-43, 76](../CATALOG.md#L32-L53), [top-10](../docs/top10.md) |
| `08_account_code_and_aa.sol` | EIP-7702, smart accounts, and EOA checks | [rows 40-43](../CATALOG.md#L50-L53), [Ethereum matrix](../results/2026-10-18/ethereum/ethereum.json) |
| `09_native_asset_and_fee_currency.sol` | Native value, rebasing, and fee currencies | [rows 73-75, 83-84](../CATALOG.md#L83-L94), [top-10](../docs/top10.md) |
| `10_code_size_and_modularity.sol` | Init/runtime code-size limits | [row 19](../CATALOG.md#L29), [matrix](../results/2026-10-18/ethereum/ethereum.json) |

Compile all fixtures with the same EVM target used by the probe campaign:

```sh
./examples/compile.sh
```

The Cancun-only fixture is deliberately expected to require a Cancun-capable
target. A successful `solc` compile is not evidence that every target chain
accepts the resulting bytecode; run `./probes/run.sh` against the deployment
RPC before selecting a compiler target.

The local exploit-style authorization demo uses no RPC, key, or public network:

```sh
./examples/local-demo/run.sh
```

It proves that an intermediate contract drains the `tx.origin` wallet and that
the explicit-principal wallet rejects the same call. The cross-chain account
probe evidence is in [Ethereum](../results/2026-10-18/ethereum/ethereum.json),
[MegaETH](../results/2026-10-18/megaeth/megaeth.json), and [zkSync Era](../results/2026-10-18/zksync-era/zksync-era.json).

# Differential chain probe matrix

Captured 2026-10-18 from the committed raw results. This figure includes only chains that differ from Ethereum in at least one displayed security-relevant dimension. `RIPEMD160 call` is the inner precompile call status; `—` means the endpoint was unavailable or the probe did not run.

| Chain | ID | Profile | Block | BLOBBASEFEE | NUMBER/header | RIPEMD160 call | Cold access delta | Evidence |
| --- | ---: | --- | --- | --- | --- | ---: | ---: | --- |
| arbitrum-one | 42161 | degraded | 0x1ec262a3 | rpc-rejected | diff | 1 | 2614 | [results/2026-10-18/arbitrum-one/arbitrum-one.json](../results/2026-10-18/arbitrum-one/arbitrum-one.json) |
| hyperevm | 999 | ok | 0x2ea1269 | ok | diff | 1 | 2614 | [results/2026-10-18/hyperevm/hyperevm.json](../results/2026-10-18/hyperevm/hyperevm.json) |
| megaeth | 4326 | ok | 0x1c36980 | ok | diff | 1 | 2614 | [results/2026-10-18/megaeth/megaeth.json](../results/2026-10-18/megaeth/megaeth.json) |
| monad | 143 | ok | 0x6d3d722 | ok | match | 1 | 10111 | [results/2026-10-18/monad/monad.json](../results/2026-10-18/monad/monad.json) |
| polygon-pos | 137 | ok | 0x5b539ba | execution-failure | match | 1 | 2614 | [results/2026-10-18/polygon-pos/polygon-pos.json](../results/2026-10-18/polygon-pos/polygon-pos.json) |
| scroll | 534352 | ok | 0x21c7954 | execution-failure | match | 0 | 2614 | [results/2026-10-18/scroll/scroll.json](../results/2026-10-18/scroll/scroll.json) |
| somnia | 5031 | ok | 0x1a57b678 | ok | match | 1 | 114 | [results/2026-10-18/somnia/somnia.json](../results/2026-10-18/somnia/somnia.json) |
| taiko | 167000 | degraded | 0xc4201f | ok | match | 1 | 2614 | [results/2026-10-18/taiko/taiko.json](../results/2026-10-18/taiko/taiko.json) |
| tron | 728126428 | degraded | 0x532f4cb | rpc-rejected | rpc-rejected | — | — | [results/2026-10-18/tron/tron.json](../results/2026-10-18/tron/tron.json) |
| zksync-era | 324 | ok | 0x4530344 | ok | match | 0 | 2614 | [results/2026-10-18/zksync-era/zksync-era.json](../results/2026-10-18/zksync-era/zksync-era.json) |

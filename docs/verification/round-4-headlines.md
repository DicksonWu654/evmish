# Gas headline check — 2026-10-20

**Scope and method.** I inspected `probes/run_gas_schedule.py`, the dated raw results, and `site/data/data.json → gas_schedule`, then reran selected probes by read-only `eth_call` with **no `to`**, init code in `data`, and a 30,000,000-gas simulation allowance. Each call used the block number just returned by its endpoint. Requests were serialized at no more than two per second per endpoint. No transaction was signed or sent. The count audit uses the full dated dataset; the live rerun covers the headline cases and one differing case on each of the six requested chains, rather than all 27 chains.

In the tables, **`W(a,b,…)` is the exact raw `eth_call.result`**, written as successive 32-byte, unsigned, big-endian words in decimal: `0x` followed by each word as 64 zero-padded hex digits. This compact notation is lossless. The numbers following `→` are the probe's derived gas values, not the raw return. The init code, transaction fields, original JSON-RPC responses, and prior later-block/second-endpoint runs are in `results/2026-10-20/gas-schedule/`.

## 1. Somnia zero-value `CALL` to the tested empty account — **CONFIRMED, narrowly**

| Endpoint and block | Raw `call-empty` result | Derived cold / warm gas |
|---|---|---:|
| Somnia `https://api.infra.mainnet.somnia.network` · `0x1a6b0da9` | `W(37,25,25)` | 0 / 0 |
| Somnia `https://somnia.publicnode.com` · `0x1a6b0dc3` | `W(37,25,25)` | 0 / 0 |
| Ethereum `https://ethereum-rpc.publicnode.com` · `0x1904460` | `W(37,2625,125)` | 2,600 / 100 |

The probe pushes seven `CALL` arguments, requests **zero forwarded gas and zero value**, discards the success bit, and compares each timer with a control that replaces the call with seven `POP`s. Its correction is **+12 gas**, accounting for the six excess `POP`s in that control: `25 − 37 + 12 = 0` on Somnia; `2625 − 37 + 12 = 2600` and `125 − 37 + 12 = 100` on Ethereum. `GAS` records gas left during execution, before transaction-end refunds. With zero gas forwarded, a forwarded-gas debit cannot explain this result.

I separately ran an init-code wrapper that preserves the `CALL` success bit and stores the timer delta. Its bytecode for the zero-forwarded-gas case was `0x5a60006000600060006000739baeb70184075f3ea43e6e8160ec2f162da8d28b6000f16000525a900360205260406000f3`. Raw results were `W(1,32)` on Somnia primary at `0x1a6b0c4e` **and** secondary at `0x1a6b0c5b`, versus `W(1,2632)` on Ethereum at `0x190445e`. The first word is success (`1`). The wrapper's pushes, status storage, first memory expansion, and second `GAS` consume 32 gas; the excess is **0** on Somnia and **2,600** on Ethereum. Requesting 1,000,000 forwarded gas also returned `W(1,32)` on both Somnia endpoints and `W(1,2632)` on Ethereum at those respective blocks: unused forwarded gas returned to the caller. At the pinned primary blocks, `eth_getCode=0x`, `eth_getBalance=0x0`, and `eth_getTransactionCount=0x0` for `0x9baeb70184075f3ea43e6e8160ec2f162da8d28b` on both chains.

[Somnia's official gas differences](https://docs.somnia.network/developer/deployment-and-production/somnia-gas-differences-to-ethereum.md), accessed 2026-10-20, lists `CALL` among account operations and says a read of a nonexistent account requires at least 1,000,000 **caller gas remaining** but adds no account-storage charge. It does **not explicitly state a zero static `CALL` price**; the zero here is established by the live timer and successful independent wrapper. The 30,000,000-gas outer allowance meets that remaining-gas condition. A value-transferring or code-executing call has different costs; the saved funded-call measurement is 406,700 gas on Somnia.

**Safe headline:** “In a read-only creation-call probe, a successful zero-value `CALL` to a verified empty address consumed 0 measured gas on Somnia on both first and repeated access, versus 2,600 and 100 on Ethereum.” Do not shorten this to “calls are free on Somnia.”

## 2. Somnia `SELFBALANCE` and `KECCAK256` — **CONFIRMED**

| Case | Somnia primary `0x1a6b0da9` and secondary `0x1a6b0dc3`: raw result → gas | Ethereum `0x1904460`: raw result → gas |
|---|---|---|
| `SELFBALANCE` | `W(2,309)` → **305** | `W(2,9)` → **5** |
| `KECCAK256`, 4 words / 128 bytes | `W(12,2460)` → **2,450** | `W(12,64)` → **54** |
| `KECCAK256`, 32 words / 1,024 bytes | `W(12,10860)` → **10,850** | `W(12,232)` → **222** |

The probe pre-expands memory before each `KECCAK256` timer. Its common control costs 10 gas; the operation values are `target − control + 2` (the correction replaces the extra control `POP`). For `SELFBALANCE`, the control costs zero and the same formula gives `309 − 2 − 2 = 305`. The official [Somnia gas page](https://docs.somnia.network/developer/deployment-and-production/somnia-gas-differences-to-ethereum.md) explicitly specifies `SELFBALANCE = 305` and `KECCAK256 = 1,250 + 300 × minimum_word_size`, matching both live values. The Ethereum results match 5 and `30 + 6 × words`.

**Safe headline:** “Somnia charged 305 gas for `SELFBALANCE` in this probe, **61×** Ethereum's 5; hashing 128 and 1,024 bytes cost 2,450 and 10,850 gas, versus Ethereum's 54 and 222.” These are execution gas units, not native-token transaction fees.

## 3. Site headline counts — **CONFIRMED as dataset counts; qualify coverage**

Verdicts: **CONFIRMED** for “109 measured prices differ on 7 chains” as a count of comparable chain–item cells; **CONFIRMED** for “17 chains match Ethereum on every measured item” only when “measured” excludes unsuccessful probes as described below.

I recomputed statuses from all 3,699 site cells (27 chains × 137 items). Exactly **109 chain–item cells** have `confirmed-two-endpoints`, distributed as Somnia 54, MegaETH 24, Tempo 14, Monad 12, Kaia 2, Polygon PoS 2, and Sei EVM 1. This counts different **chain/probe-item measurements**, including multiple sizes and cold/warm phases, rather than 109 distinct opcode names or a complete protocol gas schedule. The live spot checks below agree with one cell on each non-Somnia chain; the full 109 count relies on the dated first, later-block, and second-endpoint records.

Seventeen **other** chains have no differing successful comparable cell. Fifteen have 136/136 comparable items: Avalanche C-Chain, Base, Berachain, Blast, BNB Smart Chain, Celo, Cronos, Gnosis, HyperEVM, Linea, Mantle, OP Mainnet, Plasma, Taiko, and zkSync Era. Arbitrum One has 135/136 because `BLOBBASEFEE` was RPC-rejected (`-32000`, “BLOBBASEFEE is not supported on Arbitrum”); Scroll has 134/136 because `BLOBHASH` and `BLOBBASEFEE` returned invalid-opcode execution errors. These are **failures to compare**, not Ethereum matches. One of the 137 items (`call-value-empty`) is an unfunded value-call control on every chain and is excluded from comparative prices.

Evmos is excluded from the 17 because the registry had **no no-key public EVM RPC** for this run. TRON is excluded because its public JSON-RPC rejected 134 no-`to` creation probes: the saved `add` call at block `0x5338827` returned `{"code":-32602,"data":"{}","message":"invalid address"}`; its two value-call items have target-state RPC errors. There is thus no comparable TRON gas schedule from this method. Polygon PoS, a differing chain, also has two invalid-opcode blob cases (134/136 comparable). Tempo's two funded-value items are marked `synthetic-balance-rpc`, not measured prices; its documented balance response and rejected funded call prevent a value-transfer conclusion. Some BNB account calls fell back to `latest` after a pinned-state error, so equality there is a successful RPC observation, not proof at the originally requested historical block.

**Safe headline:** “In the 2026-10-20 read-only probe set, 109 comparable chain–item gas deltas differed from Ethereum across seven chains. Seventeen other chains showed no difference among their successful comparable measurements; Arbitrum and Scroll had incomplete opcode coverage, while TRON and Evmos could not be compared by this method.”

## 4. Six live spot checks — **CONFIRMED**

The same raw result appeared on both listed public RPCs at the listed blocks. Ethereum comparisons below were rerun at `https://ethereum-rpc.publicnode.com`, block `0x1904460`. The official links specify a price where stated; a link to general network or gas documentation is **not** treated as proof of an exact observed opcode price.

| Chain / case | Endpoints and pinned blocks | Raw `eth_call.result` on each endpoint → derived gas | Ethereum raw → gas | Documentation and safe headline wording |
|---|---|---|---|---|
| Tempo, empty `CREATE` | `https://rpc.tempo.xyz` `0x2ae7e9c`; `https://tempo.drpc.org` `0x2ae7e9d` | `W(17,500013)` → **500,000** | `W(17,32013)` → **32,000** | [TIP-1000, pinned commit](https://github.com/tempoxyz/tempo/blob/296be2abd6df2cf666bd68d9e3da9ca3517d6714/tips/tip-1000.md). “A STOP-only child `CREATE` cost 500,000 gas in Tempo simulation versus 32,000 on Ethereum.” |
| MegaETH, `LOG1` with zero payload bytes | `https://mainnet.megaeth.com/rpc` `0x1c4df98`; `https://megaeth.drpc.org` `0x1c4df99` | `W(17,4511)` → **4,500** | `W(17,761)` → **750** | [MegaEVM dual gas specification](https://docs.megaeth.com/spec/megaevm/dual-gas-model). “A one-topic, empty-data log cost 4,500 gas in this MegaETH probe versus 750 on Ethereum.” |
| Monad, first `SLOAD` of fresh creation slot zero | `https://rpc.monad.xyz` `0x6da3a7d`; `https://monad.drpc.org` `0x6da3a7f` | `W(7,8107,107)` → **8,100 cold**, 100 warm | `W(7,2107,107)` → **2,100 cold**, 100 warm | [Monad opcode pricing](https://docs.monad.xyz/developer-essentials/opcode-pricing.md) specifies 8,100 per first storage-page access. “A first-page `SLOAD` cost 8,100 gas on Monad versus 2,100 on Ethereum in this probe.” |
| Kaia, `EXTCODEHASH` of tested empty address | `https://public-en.node.kaia.io` `0xdb9b2be`; `https://klaytn.drpc.org` `0xdb9b2b8` | `W(7,407,407)` → **400 first**, 400 repeated | `W(7,2607,107)` → **2,600 first**, 100 repeated | [Kaia execution-gas page](https://docs.kaia.io/learn/transaction-fees/execution-gas/) does not establish this exact current result. “`EXTCODEHASH` of the tested empty address used 400 gas on each Kaia access, versus 2,600 then 100 on Ethereum.” |
| Polygon PoS, first `SLOAD` of fresh creation slot zero | `https://polygon-bor-rpc.publicnode.com` `0x5b68410`; `https://polygon.drpc.org` `0x5b68410` | `W(7,5467,107)` → **5,460 cold**, 100 warm | `W(7,2107,107)` → **2,100 cold**, 100 warm | [Polygon PoS RPC endpoints](https://docs.polygon.technology/pos/reference/rpc-endpoints.md); no official exact-cost source found. “This cold-slot `SLOAD` used 5,460 gas on Polygon PoS versus 2,100 on Ethereum.” |
| Sei EVM, fresh slot `SSTORE` 0→1 | `https://evm-rpc.sei-apis.com` `0xe3915c1`; `https://sei-evm-rpc.publicnode.com` `0xe3915c2` | `W(12,74108,108,108,108)` → **74,100** first write | `W(12,22108,108,108,108)` → **22,100** first write | [Sei gas and fees](https://docs.sei.io/evm/evm-parity/gas-and-fees.md) gives a governance-adjustable 72,000 write component. “A first 0→1 storage write used 74,100 gas on Sei EVM versus 22,100 on Ethereum in this probe”; the observed total includes the cold access and can change with governance. |

**Verdict on publication:** The measured values are reproducible at these endpoints and blocks. Preserve the probe conditions and coverage qualifiers in the public wording above, especially for the zero-gas `CALL` and the 17-chain count.

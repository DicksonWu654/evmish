# Gas schedule sweep — 2026-10-20

The [gas matrix](../results/2026-10-20/gas-schedule/MATRIX.csv) compares each
measured item with Ethereum. Each row names its raw JSON file and the JSON
pointer to the request/response. The [registry](../probes/chains.json) gives
the endpoint and its source. focused-probe-29 evidence is integrated into the catalog and
site; the independent review's [round-4 review](verification/round-4-sample.md)
sampled new rows, and its [Ethereum baseline check](gas-baseline-check.md)
matched 209/209 gas-schedule and precompile expectations under the stated rules.
The matrix contains 3,699 chain/item cells; all 109 measured differences
recurred at a later block and matched a second listed RPC endpoint.

## Method

`python3 probes/run_gas_schedule.py --date 2026-10-20` runs the read-only
creation calls. Each init-code case brackets a no-op control and the operation
with `GAS`, returns both deltas, and subtracts the control and stack POP
correction. The raw words, full request and response, chain ID, header, RPC
URL, and UTC observation time are retained in each chain JSON. The 123 cases
retain JSON-RPC bodies and HTTP status; HTTP response headers are omitted
because public endpoints can put transient cookies in them. The cases
cover representative arithmetic, comparison, bitwise, context, copy, stack,
control-flow, memory, storage, transient storage, account access, hashing,
logs, CREATE, and CREATE2 operations. STOP, RETURN, REVERT, and SELFDESTRUCT
cannot sit inside a continuing timer; stateful lifecycle boundaries belong
to focused-probe-31.

`--phase confirm` reruns **only measured differences** at a later block.
`--phase secondary` reruns them against the second listed endpoint where one
exists. The [funded value-call probe](../probes/run_value_call.py) separately
supplies one wei from a publicly funded address in `eth_call`, checks that the
target has zero code, balance, and nonce, checks that its CALL returned
success with one million gas requested (unused gas
is returned), and creates a transient child within the
same read-only simulation to observe the value stipend with zero requested
forwarded gas. No transaction was signed, sent, or deployed on a public chain.

Memory is pre-expanded before timing MCOPY, KECCAK256, EXTCODECOPY, and LOG,
so those rows isolate their operation cost. Four separate MSTORE cases measure
expansion from zero to 1, 32, 1,024, and 32,768 words. CREATE and CREATE2
use STOP-only child init code of 0, 1, 32, 33, 256, and 1,024 bytes, returning
zero runtime bytes; those rows isolate creation base cost and init-code length
steps, not deployed runtime-code deposit cost. The SSTORE sequence is 0→1,
1→2, 2→2, 2→0 in fresh creation storage. `GAS` does not reveal refunds; net
refund accounting requires a separate transaction or local-node fixture.

## Repricing observed

Every numeric item below reproduced at a later block. A second endpoint
matched where indicated in the matrix. Official sources were accessed
2026-10-20; source text explains the schedule where it actually specifies
these costs.

| Chain | Measured gas versus Ethereum | Official source and limit |
|---|---|---|
| Polygon PoS | Cold SLOAD 5,460 versus 2,100; fresh 0→1 SSTORE 22,940 versus 22,100. | Both endpoints agree. [Polygon's RPC page](https://docs.polygon.technology/pos/reference/rpc-endpoints.md) lists the second endpoint; an official page specifying these two exact costs was not found. Keep the numbers as measured observations. |
| Monad | Cold account access 10,100 versus 2,600; cold SLOAD 8,100 versus 2,100; fresh SSTORE 27,900 versus 22,100. Memory expansion is linear: one-word MSTORE 3 versus 6, 32-word 19 versus 101, 1,024-word 515 versus 5,123, and 32,768-word 16,387 versus 2,195,459. A successful one-wei empty-account CALL costs 41,800 versus 34,300. | [Monad opcode pricing](https://docs.monad.xyz/developer-essentials/opcode-pricing) specifies cold account/storage costs, storage pages, and linear memory pricing. The second endpoint agrees. |
| MegaETH | LOG0 with one byte costs 463 versus 383; LOG1 with zero bytes costs 4,500 versus 750; LOG4 with 256 bytes costs 39,403 versus 3,923. | [MegaEVM dual gas specification](https://docs.megaeth.com/spec/megaevm/dual-gas-model) describes additional storage gas for log topics/data. The second endpoint agrees. |
| Tempo | STOP-only CREATE costs 500,000 versus 32,000; fresh SSTORE 254,300 versus 22,100; the final dirty-slot clear costs 3,000 versus 100. | [Tempo EVM differences](https://tempo.xyz/developers/docs/quickstart/evm-compatibility) links [TIP-1000 at commit 296be2a](https://github.com/tempoxyz/tempo/blob/296be2abd6df2cf666bd68d9e3da9ca3517d6714/tips/tip-1000.md) and describes higher state-creation costs. The second endpoint agrees. The doc also states that `eth_getBalance` returns a synthetic native-balance value for every address; a separate funded `eth_call` attempt returned `value transfer not allowed`. No successful native value-CALL price is asserted. |
| Somnia | ADDMOD and MULMOD cost 358 versus 8; SELFBALANCE 305 versus 5; KECCAK256 costs 1,250 + 300 per word; LOG0 costs 3,200 + 160 per byte and each topic adds 5,120; fresh SSTORE costs 200,100 versus 22,100; STOP-only CREATE costs 432,000 versus 32,000. A successful one-wei empty-account CALL with one million gas requested costs 406,700 versus 34,300. The tested empty account has no cold surcharge in BALANCE/EXTCODEHASH; the exact storage/account charge can depend on cache and existence. | [Somnia gas differences](https://docs.somnia.network/developer/deployment-and-production/somnia-gas-differences-to-ethereum.md) states these formulas and cache rules. The second endpoint agrees. With zero requested gas the empty-account CALL returned status 0, while the transient-child CALL still observed the 2,300-gas stipend. |
| Sei EVM | Fresh SSTORE costs 74,100 versus 22,100, including a 2,100 cold read. | [Sei gas and fees](https://docs.sei.io/evm/evm-parity/gas-and-fees.md) states that the current SSTORE write cost is governance-adjustable at 72,000. A later block agrees. The first second-endpoint attempt returned an internal RPC error; see the saved attempt. |
| Kaia | EXTCODEHASH of the chosen empty address costs 400 on both first and second access, versus 2,600 then 100 on Ethereum. | The two listed endpoints agree. [Kaia's execution-gas page](https://docs.kaia.io/learn/transaction-fees/execution-gas) gives historical opcode figures, but does not establish this exact current two-access result; retain it as a measured observation. |

All other successful cells matched the Ethereum baseline in this run. The
matrix keeps identical cells, RPC failures, and unsupported opcodes visible so
absence of a reported difference is not mistaken for complete VM equivalence.
TRON's official RPC rejects no-`to` creation calls (`invalid address`), and
Evmos has no no-key public endpoint in the registry. BNB's RPC could not read
recent pinned state for some account cases (`missing trie node`); those raw
errors and the separately labeled `latest` retries are both retained. A
`latest` call is not proof of historical-block behavior. The failed Sei dRPC
attempt, Kaia dRPC/OnFinality errors, Cronos future-height response, and
[Tempo's rejected value call](../results/2026-10-20/gas-schedule/secondary-attempts/tempo-value-transfer-rejected.json)
are preserved under `secondary-attempts/` rather than promoted to chain
results.

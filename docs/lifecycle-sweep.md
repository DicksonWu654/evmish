# Limits and lifecycle sweep — 2026-10-20

The [focused-probe-31 matrix](../results/2026-10-20/lifecycle/MATRIX.csv) has 390
chain/case rows: 15 creation-call cases on 26 registry RPC scopes. Each row
points to [raw request/response evidence](../results/2026-10-20/lifecycle/)
with endpoint, chain ID, block number and timestamp, block tag, and UTC
observation time. Evmos has no no-key public endpoint in the registry. The
matrix distinguishes observed VM output from outer execution errors, RPC
rejections, resource-bound probes, and unavailable funded senders. Curated focused-probe-31
rows are integrated into the catalog and site; the independent review's
[round-4 review](verification/round-4-sample.md) sampled new rows
and [replayed lifecycle top-ten cases](verification/round-4-top10.md).

## Fixture and interpretation

The [Solidity fixture](../probes/lifecycle_probe.sol) is compiled with solc
0.8.36, optimization enabled, and Paris EVM target; the reproducible
[creation bytecode](../probes/lifecycle_bytecode.json) includes the compiler
version and source hash. The [runner](../probes/run_lifecycle_sweep.py) passes
the fixture as no-`to` `eth_call` data. It sends no transaction. Its constructor
creates children inside the simulation and returns fixed 32-byte words for:

- 24,575/24,576/24,577-byte zero-filled runtime code, checking the child
  address, `EXTCODESIZE`, `EXTCODEHASH`, and CREATE gas;
- 49,120/49,152/49,153-byte STOP-only init code, checking child creation and
  gas after memory was expanded; the first two differ by one 32-byte word;
- four-byte `0xdeadbeef` return and revert data, including CALL status and
  `RETURNDATASIZE`-equivalent lengths;
- a failed REVERTing inner CREATE followed by a successful one, comparing the
  resulting address with the RLP nonce-2 formula;
- a newly created child called through `SELFDESTRUCT`, recording code size,
  code hash, child balance, beneficiary balance, and CALL status before/after;
- identity precompile `0x04` called with one wei and byte `0x5a`, recording
  output and balance deltas; and
- recursive self-CALL to targets 64, 256, 512, and 1024, recording whether the
  target was reached and the deepest returned frame.

The value cases use a publicly funded `from` address selected by read-only
balance calls and attach one wei to `eth_call`. They do not sign or transfer
committed funds. If no funded sender exists, the case says `not-run`. The base
call supplies 30 million gas. When the 24,576-byte runtime control fails,
the runner records separate 60M, 120M, and at most 250M read-only attempts.
Those requests identify gas-bound simulations; they do **not** prove a code
limit merely because CREATE returned zero. Failed CREATE gas and a recursion
shortfall are excluded from protocol-outcome comparisons because they vary
with gas allowance and [EIP-150](https://eips.ethereum.org/EIPS/eip-150)'s
63/64 forwarding rule. An outer RPC error supplies no child status. The
endpoint may also ignore historical block tags (previously observed on
HyperEVM), so a later sampled header is an observation repeat, not proof of
historical-tag fidelity.

Official Ethereum specifications: [EIP-170 runtime limit](https://eips.ethereum.org/EIPS/eip-170),
[EIP-3860 init-code limit and per-word charge](https://eips.ethereum.org/EIPS/eip-3860),
[EIP-161 creation nonce](https://eips.ethereum.org/EIPS/eip-161),
[EIP-211 return data](https://eips.ethereum.org/EIPS/eip-211), and
[EIP-6780 SELFDESTRUCT](https://eips.ethereum.org/EIPS/eip-6780).
Links were accessed 2026-10-20. They describe Ethereum; target-chain values
below come from the dated calls.

## Boundary observations

| Observation | Evidence-backed result | Limit |
|---|---|---|
| Runtime code | Ethereum created 24,576 bytes and returned child address zero for 24,577. Polygon PoS, Monad, Berachain, Somnia, and Celo created 24,577 bytes. Polygon, Monad, and Somnia matched their listed second endpoints; Berachain and Celo have none listed. | Somnia needed a 120M `eth_call` allowance for both 24,576 and 24,577; its zero results at 30M/60M were gas-bound. MegaETH remained resource-inconclusive even at 250M, with CREATE consuming almost all forwarded gas. Do not call those code-size rejection evidence. |
| Init code | Ethereum created from 49,152 bytes, with CREATE gas rising by 2 from 49,120, but returned an outer `CreateInitCodeSizeLimit` error for 49,153. Monad, MegaETH, Berachain, Somnia, and Celo returned a nonzero child for 49,153; the listed second endpoints for Monad, MegaETH, and Somnia agreed. | An outer error does not expose an inner CREATE status. The +2 gas step in successful cases is measured, not an independent attribution of every component of CREATE gas. |
| Return/revert | Every observable scope returned `0xdeadbeef` in both cases, with success status 1 and revert status 0, length 4 each. | TRON rejected no-`to` creation calls. |
| Failed CREATE nonce | Every observable scope returned zero for the failed child and a second child address matching `keccak256(rlp([creator,2]))[12:]`. | This is a simulated, same-call nonce observation; it says nothing about a committed transaction nonce. |
| Same-call SELFDESTRUCT | Ethereum's new child kept the same 174-byte code and code hash until the constructor returned. With one wei, its balance fell 1→0 and the beneficiary rose by one. zkSync Era and Scroll returned CALL status 0 for the `kill` call and retained the child's balance/code; zkSync's listed second endpoint agreed. | `eth_call` cannot show post-transaction deletion or persistence. A failed child CALL does not alone identify which opcode or runtime rule caused it. |
| Precompile with value | Ethereum identity `0x04` returned byte `0x5a`; the simulated precompile balance rose by one and caller balance fell by one. Kaia returned CALL status 0 with no output or balance delta on both listed endpoints. Tempo's funded call was rejected with `value transfer not allowed`. | No committed value transfer is claimed. |
| Call depth | Target 64 was reached on all 25 observable scopes; target 256 was reached on 24 (zkSync Era returned an outer revert). Somnia reached 512 at the sampled gas allowance; no scope reached 1024. Taiko returned `zk gas limit exceeded` for 512 and 1024. | The maximum returned frame and 1024 shortfall are gas/provider observations, **not** measured protocol call-depth limits. |

All 390 rows repeated at a later sampled block: 345 normalized observed
outcomes, 42 recurring error/not-run classes, and three resource-inconclusive
MegaETH runtime rows. Of 165 cells on 11 usable listed second endpoints, 149
observed outcomes, 13 error classes, and three resource-bound rows agreed on
that same normalized basis. Fifteen scopes had no listed second endpoint; the
Ethereum Cloudflare secondary returned block-context errors. Raw error text
and exact gas values remain in the JSON even where comparison omits them.
These are implementation checks run by the author, not independent
verification. Catalog labels are set by the focused-probe-32/focused-probe-33 integration, not by these
author-run implementation checks.

`./probes/run.sh` runs the initial focused-probe-31 cases. To refresh later-block and
second-endpoint evidence and the matrix, run
`python3 probes/run_lifecycle_sweep.py --phase confirm`, then
`python3 probes/run_lifecycle_sweep.py --phase secondary`, then
`python3 probes/build_lifecycle_matrix.py`.

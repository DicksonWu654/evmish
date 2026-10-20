# Cross-chain EVM security checklist

Use this checklist before deploying or changing a protocol on an EVM-compatible
chain. Attach the target chain, RPC URL, block number, timestamp, and raw probe
response to each answer. A rejected RPC call records an integration limitation;
it does not prove that the VM lacks the feature.

## Execution and compiler target

- Which fork and `--evm-version` does the target execute today? Run the probe
  kit for `PUSH0`, `TSTORE/TLOAD`, `MCOPY`, `BLOBHASH`, and `BLOBBASEFEE`.
- Does the deployment bytecode contain an opcode the target rejects? Compile the
  smallest fixture in `examples/01_fork_gated_opcodes.sol` for the target fork.
- What are the target's init-code, runtime-code, and contract-size limits? Test
  a boundary-sized CREATE on the target, rather than relying on Ethereum's
  limit or a local compiler success.

## Addresses, accounts, and authorization

- Are CREATE and CREATE2 addresses computed by the same formula as Ethereum?
  Store the address returned by the target VM and compare it with any off-chain
  prediction before sending funds or approvals.
- For OP or Arbitrum messages, which messenger authenticates the L1 sender and
  what aliasing rule applies? Check the messenger and its x-domain sender; do
  not compare `msg.sender` or `tx.origin` directly with the L1 administrator.
- Does any authorization rule use `tx.origin`, `address.code.length`,
  `EXTCODESIZE`, or `EXTCODEHASH` as an EOA test? Test an EIP-7702 delegated
  account, a smart account, an EOA, and the chain's system addresses.
- Are precompile addresses and vectors chain-specific? Run known-answer calls
  for every precompile the protocol uses and confirm the chain ID and address
  registry at deployment.

## Time, ordering, and randomness

- Does `block.number` represent this chain's local blocks, L1 blocks, batches,
  or another counter? Arbitrum's measured NUMBER/header mismatch is a reminder
  to check the target directly.
- What clock and finality guarantee does each timelock, TWAP, auction, and
  withdrawal use? Configure delays in seconds and add the target's finality
  policy where wall-clock behavior is required.
- Does any randomness use `blockhash`, `prevrandao`, `timestamp`, or
  `coinbase`? Record the target semantics and prefer a commit/reveal or an
  external verifiable randomness source when adversarial ordering matters.
- What is the sequencer ordering and L1 finality path? Define when a message or
  price is considered final instead of treating an accepted RPC response as
  Ethereum-style finality.

## Fees and value

- Does the fee estimate include L1 data, storage, blob, or chain-specific gas
  charges? Compare `eth_estimateGas` with the target's fee oracle and an actual
  probe; do not price a relayer from `gasleft() * tx.gasprice` alone.
- On Monad or another chain with non-Ethereum charging, is the budget based on
  the documented gas-limit rule rather than ordinary gas used?
- Which asset is native value, which asset pays fees, and can either rebase or
  be configured? Test `call{value:...}`, balance accounting, fee-token payment,
  and failure/refund paths on the target.
- Does the code use `.transfer()` or assume the recipient's fallback gas and
  native-asset semantics match Ethereum? Prefer an explicit asset adapter,
  checked low-level calls, and reentrancy protection.

## Evidence and release gate

- Record chain, RPC endpoint, block, timestamp, raw return, and interpretation
  for every probe. Preserve RPC errors verbatim and rerun surprising results on
  a second independent official endpoint.
- Pin each documentation or source claim with an official URL, commit, and
  access date. Mark observations `probe-verified`, source claims
  `source-verified`, and unresolved items `doc-only`.
- Require the fixtures in `examples/` to compile for the selected compiler
  target, then run the complete probe matrix in CI before release.

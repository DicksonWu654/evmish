# Stateful follow-ups deferred from focused-probe-4

The focused-probe-4 pass stayed within read-only public RPC rules. These questions need a
local node, a two-step message, or a state-changing fixture before they can be
called confirmed:

| Question | Why a public read-only probe is insufficient | Suggested local fixture |
|---|---|---|
| OP/Arbitrum L1-to-L2 sender aliasing | The alias is applied while relaying a cross-domain message; `eth_call` cannot create that message context. | A local OP/Arbitrum dev node with an L1 messenger and an `onlyOwner` receiver. |
| Blast rebasing/yield and `.transfer()` behavior | The consequence depends on balances and value movement over time. | A local fork or chain node with a funded account and a minimal value-transfer contract. |
| Celo fee-currency payment and Mantle native-value semantics | Fee payment and native-asset movement require transaction/state transitions. | A local node fixture that configures a fee currency and exercises `transfer`/`call{value:...}`. |
| Sequencer ordering/finality windows | Finality requires observing delayed messages, ordering, or a reorg/dispute transition. | A local sequencer plus replica/L1 harness. |
| Exact Monad maximum code boundary | The public probe only tested a 24,577-byte runtime and observed success; the exact upper bound needs boundary-sized creations. | A local Monad-compatible node, testing both init and runtime limits around the documented cap. |
| Post-transaction SELFDESTRUCT code state | focused-probe-31's no-`to` `eth_call` can inspect the new child's code, hash and balance after SELFDESTRUCT in the same simulation, but the simulation is discarded before a later RPC can inspect committed state. | A local VM state-transition fixture that executes creation/destruction and inspects post-transition state; no RPC transaction, public deployment, or signing. |
| Exact 1,024-frame call-depth boundary | focused-probe-31's recursive public `eth_call` falls short as EIP-150 reduces forwarded gas at every frame; a shortfall does not distinguish the hard depth rule from gas exhaustion. | A local VM/interpreter fixture with an intentionally enlarged gas allowance, recording the first CALL rejected specifically for depth. |
| SSTORE refund and committed native-value behavior | `GAS` reports consumption before transaction-end refunds. Tempo rejects a funded value `eth_call`; on Somnia the empty-account CALL succeeds when one million gas is requested but fails with zero requested gas. Neither read-only simulation establishes committed balances. | Local transactions and receipts for refund accounting, value transfer, and balance changes, without publishing to a public network. |

No public transaction, signature, deployment, or private key was used for this
list.

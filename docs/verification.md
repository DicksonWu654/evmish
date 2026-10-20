# Verification spot checks

Four independent spot-check rounds sampled 20 catalog rows each. Samples refer to the catalog version reviewed at that time, so row numbers and totals change after corrections.

| Round | Seed | Sample size | Verdict counts | Corrections |
|---|---:|---:|---|---|
| 1 | 91823 | 20 | 13 CORRECT; 3 NOT-A-DIVERGENCE; 3 OVERSTATED-CONSEQUENCE; 1 UNVERIFIABLE | Removed 11 fixed-account delegation rows, one unstable HyperEVM NUMBER row, and one planned Plasma fee claim; narrowed retained consequences to the measured controls. |
| 2 | 55117 | 20 | 17 CORRECT; 3 NOT-A-DIVERGENCE | Removed six BASEFEE comparison rows affected by no-gas-price simulation and two unstable TIMESTAMP rows; retained explicit RPC simulation and historical-tag quality records. |
| 3 | 70331 | 20 | 18 CORRECT; 0 wrong; 2 UNVERIFIABLE | Removed HyperEVM GASLIMIT from VM claims because execution blocks could not be pinned; narrowed Somnia PREVRANDAO to doc-only because the header did not expose a comparable value. MegaETH was subsequently rerun on mainnet and testnet evidence omitted. |
| 4 | 40217 | 20 | 19 CORRECT; 1 OVERSTATED-CONSEQUENCE | [Sample review](verification/round-4-sample.md), [top-10 review](verification/round-4-top10.md), and [headline review](verification/round-4-headlines.md). The [Ethereum gas baseline](gas-baseline-check.md) matched 209 of 209 readings under the applicable rules. |

The third and fourth rounds met the threshold of at most one wrong row. The third round's two unverifiable observations were explicitly limited rather than counted as verified. These checks do not establish correctness of every row or future chain behavior.

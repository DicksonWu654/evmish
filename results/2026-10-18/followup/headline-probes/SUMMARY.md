# follow-up focused creation and code-size probes (2026-10-18)

The report covers CREATE/CREATE2 formula checks on Ethereum, zkSync Era, Arbitrum One, and TRON; 24,576/24,577-byte boundaries on Ethereum and Monad; and 128 KiB candidates on Monad. Every endpoint result retains the block tag and raw request/response evidence.

`rpc-rejected` means the endpoint rejected the read before VM execution. `execution-failure` means the RPC accepted the creation call and the VM returned an execution error. A nonzero CREATE return is recorded as a successful child address, not as proof of an exact maximum code limit.

Machine-readable evidence: `REPORT.json`.

# followup all-chain fork-opcode and account coverage (2026-10-18)

This report is generated from the dated full probe matrix. It covers PUSH0, TSTORE/TLOAD, MCOPY, BLOBHASH, and BLOBBASEFEE on every registry chain result, retaining `execution-failure` separately from `rpc-rejected`. The delegated-account field is fixed-address context only; `EIP7702_HISTORY.json` records that no real type-4/delegated-account history was captured, so it is not a chain-wide support claim. The TRON 0x09 limitation remains explicit.

Machine-readable evidence: `OPCODE_COVERAGE.json`.

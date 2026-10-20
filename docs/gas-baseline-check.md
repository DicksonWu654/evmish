# Ethereum gas probe baseline against the specification

This checks the Ethereum rows in [`gas-schedule/MATRIX.csv`](../results/2026-10-20/gas-schedule/MATRIX.csv) and [`precompile-sweep/MATRIX.csv`](../results/2026-10-20/precompile-sweep/MATRIX.csv), using the saved 2026-10-20 measurements. The gas probe executes creation init code with `eth_call` and no `to`. For each body, it measures two `GAS` readings, subtracts a control with the same argument pushes, and applies `correction = 2 × (input POPs − output POPs)`; this removes the control POPs but retains the operation itself. A prelude expands memory before timing where noted. `GAS` costs cancel between target and control. See [`run_gas_schedule.py`](../probes/run_gas_schedule.py) (`simple`, `access`, `encode`, `decode`).

`Spec` is the intrinsic opcode or call charge before this harness; `expected` is the returned, control-adjusted result. All amounts are gas. A ✓ means exact equality.

## Gas schedule

| Item | Spec value and source | Expected measured | Measured Ethereum | Match | Explanation |
|---|---|---:|---:|:---:|---|
| `add` | 3 [YP] | 3 | 3 | Yes |  |
| `mul` | 5 [YP] | 5 | 5 | Yes |  |
| `sub` | 3 [YP] | 3 | 3 | Yes |  |
| `div` | 5 [YP] | 5 | 5 | Yes |  |
| `sdiv` | 5 [YP] | 5 | 5 | Yes |  |
| `mod` | 5 [YP] | 5 | 5 | Yes |  |
| `smod` | 5 [YP] | 5 | 5 | Yes |  |
| `addmod` | 8 [YP] | 8 | 8 | Yes |  |
| `mulmod` | 8 [YP] | 8 | 8 | Yes |  |
| `exp-zero` | 10 + 50×0 [YP] | 10 | 10 | Yes |  |
| `exp-one-byte` | 10 + 50×1 [YP] | 60 | 60 | Yes |  |
| `signextend` | 5 [YP] | 5 | 5 | Yes |  |
| `lt` | 3 [YP] | 3 | 3 | Yes |  |
| `gt` | 3 [YP] | 3 | 3 | Yes |  |
| `slt` | 3 [YP] | 3 | 3 | Yes |  |
| `sgt` | 3 [YP] | 3 | 3 | Yes |  |
| `eq` | 3 [YP] | 3 | 3 | Yes |  |
| `iszero` | 3 [YP] | 3 | 3 | Yes |  |
| `and` | 3 [YP] | 3 | 3 | Yes |  |
| `or` | 3 [YP] | 3 | 3 | Yes |  |
| `xor` | 3 [YP] | 3 | 3 | Yes |  |
| `not` | 3 [YP] | 3 | 3 | Yes |  |
| `byte` | 3 [YP] | 3 | 3 | Yes |  |
| `shl` | 3 [YP] | 3 | 3 | Yes |  |
| `shr` | 3 [YP] | 3 | 3 | Yes |  |
| `sar` | 3 [YP] | 3 | 3 | Yes |  |
| `address` | 2 [YP] | 2 | 2 | Yes |  |
| `origin` | 2 [YP] | 2 | 2 | Yes |  |
| `caller` | 2 [YP] | 2 | 2 | Yes |  |
| `callvalue` | 2 [YP] | 2 | 2 | Yes |  |
| `calldataload` | 3 [YP] | 3 | 3 | Yes |  |
| `calldatasize` | 2 [YP] | 2 | 2 | Yes |  |
| `codesize` | 2 [YP] | 2 | 2 | Yes |  |
| `gasprice` | 2 [YP] | 2 | 2 | Yes |  |
| `returndatasize` | 2 [YP] | 2 | 2 | Yes |  |
| `blockhash` | 20 [YP] | 20 | 20 | Yes |  |
| `coinbase` | 2 [YP] | 2 | 2 | Yes |  |
| `timestamp` | 2 [YP] | 2 | 2 | Yes |  |
| `number` | 2 [YP] | 2 | 2 | Yes |  |
| `prevrandao` | 2 [YP] | 2 | 2 | Yes |  |
| `gaslimit` | 2 [YP] | 2 | 2 | Yes |  |
| `chainid` | 2 [EIP-1344] | 2 | 2 | Yes |  |
| `selfbalance` | 5 [EIP-1884] | 5 | 5 | Yes |  |
| `basefee` | 2 [EIP-3198] | 2 | 2 | Yes |  |
| `blobhash` | 3 [EIP-4844] | 3 | 3 | Yes |  |
| `blobbasefee` | 2 [EIP-4844] | 2 | 2 | Yes |  |
| `pop` | 2 [YP] | 2 | 2 | Yes |  |
| `pc` | 2 [YP] | 2 | 2 | Yes |  |
| `msize` | 2 [YP] | 2 | 2 | Yes |  |
| `gas` | 2 [YP] | 2 | 2 | Yes |  |
| `jumpdest` | 1 [YP] | 1 | 1 | Yes |  |
| `push0` | 2 [EIP-3855] | 2 | 2 | Yes |  |
| `push1` | 3 [YP] | 3 | 3 | Yes |  |
| `dup1` | 3 [YP] | 3 | 3 | Yes |  |
| `swap1` | 3 [YP] | 3 | 3 | Yes |  |
| `mload-warm-memory` | 3; memory pre-expanded [YP] | 3 | 3 | Yes |  |
| `mstore-warm-memory` | 3; memory pre-expanded [YP] | 3 | 3 | Yes |  |
| `mstore8-warm-memory` | 3; memory pre-expanded [YP] | 3 | 3 | Yes |  |
| `calldatacopy-32` | 3 + 3×1; memory pre-expanded [YP] | 6 | 6 | Yes |  |
| `codecopy-32` | 3 + 3×1; memory pre-expanded [YP] | 6 | 6 | Yes |  |
| `returndatacopy-0` | 3 + 3×0; memory pre-expanded [YP] | 3 | 3 | Yes |  |
| `jump` | 8; JUMPDEST 1 removed [YP] | 8 | 8 | Yes | Probe correction removes the target JUMPDEST cost. |
| `jumpi` | 10; JUMPDEST 1 removed [YP] | 10 | 10 | Yes | Probe correction removes the target JUMPDEST cost. |
| `memory-expand-1-words` | 3 + (3×1 + ⌊1²/512⌋) [YP] | 6 | 6 | Yes |  |
| `mcopy-1-words` | 3 + 3×1; memory pre-expanded [EIP-5656] | 6 | 6 | Yes |  |
| `memory-expand-32-words` | 3 + (3×32 + ⌊32²/512⌋) [YP] | 101 | 101 | Yes |  |
| `mcopy-32-words` | 3 + 3×32; memory pre-expanded [EIP-5656] | 99 | 99 | Yes |  |
| `memory-expand-1024-words` | 3 + (3×1024 + ⌊1024²/512⌋) [YP] | 5123 | 5123 | Yes |  |
| `mcopy-1024-words` | 3 + 3×1024; memory pre-expanded [EIP-5656] | 3075 | 3075 | Yes |  |
| `memory-expand-32768-words` | 3 + (3×32768 + ⌊32768²/512⌋) [YP] | 2195459 | 2195459 | Yes |  |
| `mcopy-32768-words` | 3 + 3×32768; memory pre-expanded [EIP-5656] | 98307 | 98307 | Yes |  |
| `keccak-0-words` | 30 + 6×0; memory pre-expanded [YP] | 30 | 30 | Yes |  |
| `keccak-1-words` | 30 + 6×1; memory pre-expanded [YP] | 36 | 36 | Yes |  |
| `keccak-2-words` | 30 + 6×2; memory pre-expanded [YP] | 42 | 42 | Yes |  |
| `keccak-4-words` | 30 + 6×4; memory pre-expanded [YP] | 54 | 54 | Yes |  |
| `keccak-32-words` | 30 + 6×32; memory pre-expanded [YP] | 222 | 222 | Yes |  |
| `log0-0-bytes` | 375 + 375×0 + 8×0; memory pre-expanded [YP] | 375 | 375 | Yes |  |
| `log0-1-bytes` | 375 + 375×0 + 8×1; memory pre-expanded [YP] | 383 | 383 | Yes |  |
| `log0-32-bytes` | 375 + 375×0 + 8×32; memory pre-expanded [YP] | 631 | 631 | Yes |  |
| `log0-64-bytes` | 375 + 375×0 + 8×64; memory pre-expanded [YP] | 887 | 887 | Yes |  |
| `log0-256-bytes` | 375 + 375×0 + 8×256; memory pre-expanded [YP] | 2423 | 2423 | Yes |  |
| `log1-0-bytes` | 375 + 375×1 + 8×0; memory pre-expanded [YP] | 750 | 750 | Yes |  |
| `log1-1-bytes` | 375 + 375×1 + 8×1; memory pre-expanded [YP] | 758 | 758 | Yes |  |
| `log1-32-bytes` | 375 + 375×1 + 8×32; memory pre-expanded [YP] | 1006 | 1006 | Yes |  |
| `log1-64-bytes` | 375 + 375×1 + 8×64; memory pre-expanded [YP] | 1262 | 1262 | Yes |  |
| `log1-256-bytes` | 375 + 375×1 + 8×256; memory pre-expanded [YP] | 2798 | 2798 | Yes |  |
| `log2-0-bytes` | 375 + 375×2 + 8×0; memory pre-expanded [YP] | 1125 | 1125 | Yes |  |
| `log2-1-bytes` | 375 + 375×2 + 8×1; memory pre-expanded [YP] | 1133 | 1133 | Yes |  |
| `log2-32-bytes` | 375 + 375×2 + 8×32; memory pre-expanded [YP] | 1381 | 1381 | Yes |  |
| `log2-64-bytes` | 375 + 375×2 + 8×64; memory pre-expanded [YP] | 1637 | 1637 | Yes |  |
| `log2-256-bytes` | 375 + 375×2 + 8×256; memory pre-expanded [YP] | 3173 | 3173 | Yes |  |
| `log3-0-bytes` | 375 + 375×3 + 8×0; memory pre-expanded [YP] | 1500 | 1500 | Yes |  |
| `log3-1-bytes` | 375 + 375×3 + 8×1; memory pre-expanded [YP] | 1508 | 1508 | Yes |  |
| `log3-32-bytes` | 375 + 375×3 + 8×32; memory pre-expanded [YP] | 1756 | 1756 | Yes |  |
| `log3-64-bytes` | 375 + 375×3 + 8×64; memory pre-expanded [YP] | 2012 | 2012 | Yes |  |
| `log3-256-bytes` | 375 + 375×3 + 8×256; memory pre-expanded [YP] | 3548 | 3548 | Yes |  |
| `log4-0-bytes` | 375 + 375×4 + 8×0; memory pre-expanded [YP] | 1875 | 1875 | Yes |  |
| `log4-1-bytes` | 375 + 375×4 + 8×1; memory pre-expanded [YP] | 1883 | 1883 | Yes |  |
| `log4-32-bytes` | 375 + 375×4 + 8×32; memory pre-expanded [YP] | 2131 | 2131 | Yes |  |
| `log4-64-bytes` | 375 + 375×4 + 8×64; memory pre-expanded [YP] | 2387 | 2387 | Yes |  |
| `log4-256-bytes` | 375 + 375×4 + 8×256; memory pre-expanded [YP] | 3923 | 3923 | Yes |  |
| `sload-slot0 (cold)` | 2100 [EIP-2929] | 2100 | 2100 | Yes |  |
| `sload-slot0 (warm)` | 100 [EIP-2929] | 100 | 100 | Yes |  |
| `balance-empty (cold)` | 2600 [EIP-2929] | 2600 | 2600 | Yes |  |
| `balance-empty (warm)` | 100 [EIP-2929] | 100 | 100 | Yes |  |
| `extcodehash-empty (cold)` | 2600 [EIP-2929] | 2600 | 2600 | Yes |  |
| `extcodehash-empty (warm)` | 100 [EIP-2929] | 100 | 100 | Yes |  |
| `extcodesize-empty (cold)` | 2600 [EIP-2929] | 2600 | 2600 | Yes |  |
| `extcodesize-empty (warm)` | 100 [EIP-2929] | 100 | 100 | Yes |  |
| `extcodecopy-empty (cold)` | 2600 access + 3 copy [EIP-2929, YP] | 2603 | 2603 | Yes |  |
| `extcodecopy-empty (warm)` | 100 access + 3 copy [EIP-2929, YP] | 103 | 103 | Yes |  |
| `call-empty (cold)` | 2600 [EIP-2929] | 2600 | 2600 | Yes |  |
| `call-empty (warm)` | 100 [EIP-2929] | 100 | 100 | Yes |  |
| `call-value-empty` | 2600 cold access + 9000 value + 25000 new account [EIP-2929, YP] | 34300 | 34300 | Yes | Unfunded creation context: CALL fails for insufficient balance. The gas price matches, but this is not a successful value transfer; comparisons of value-call success must use the funded probe. |
| `sstore-transitions (zero-to-one)` | 2100 cold + 20000 clean set [EIP-2200, EIP-2929, EIP-3529] | 22100 | 22100 | Yes | GAS deltas exclude refunds; later writes are dirty-slot writes. |
| `sstore-transitions (one-to-two)` | 100 dirty-slot write [EIP-2200, EIP-2929, EIP-3529] | 100 | 100 | Yes | GAS deltas exclude refunds; later writes are dirty-slot writes. |
| `sstore-transitions (two-to-two)` | 100 dirty-slot write [EIP-2200, EIP-2929, EIP-3529] | 100 | 100 | Yes | GAS deltas exclude refunds; later writes are dirty-slot writes. |
| `sstore-transitions (two-to-zero)` | 100 dirty-slot write [EIP-2200, EIP-2929, EIP-3529] | 100 | 100 | Yes | GAS deltas exclude refunds; later writes are dirty-slot writes. |
| `tload-slot0 (cold)` | 100; no cold surcharge [EIP-1153] | 100 | 100 | Yes |  |
| `tload-slot0 (warm)` | 100; no cold surcharge [EIP-1153] | 100 | 100 | Yes |  |
| `tstore-transitions (zero-to-one)` | 100 [EIP-1153] | 100 | 100 | Yes |  |
| `tstore-transitions (one-to-two)` | 100 [EIP-1153] | 100 | 100 | Yes |  |
| `tstore-transitions (two-to-zero)` | 100 [EIP-1153] | 100 | 100 | Yes |  |
| `create-0-bytes` | 32000 + 2×0 initcode [YP, EIP-3860] | 32000 | 32000 | Yes |  |
| `create-1-bytes` | 32000 + 2×1 initcode [YP, EIP-3860] | 32002 | 32002 | Yes |  |
| `create-32-bytes` | 32000 + 2×1 initcode [YP, EIP-3860] | 32002 | 32002 | Yes |  |
| `create-33-bytes` | 32000 + 2×2 initcode [YP, EIP-3860] | 32004 | 32004 | Yes |  |
| `create-256-bytes` | 32000 + 2×8 initcode [YP, EIP-3860] | 32016 | 32016 | Yes |  |
| `create-1024-bytes` | 32000 + 2×32 initcode [YP, EIP-3860] | 32064 | 32064 | Yes |  |
| `create2-0-bytes` | 32000 + 2×0 initcode + 6×0 hash [YP, EIP-3860, EIP-1014] | 32000 | 32000 | Yes |  |
| `create2-1-bytes` | 32000 + 2×1 initcode + 6×1 hash [YP, EIP-3860, EIP-1014] | 32008 | 32008 | Yes |  |
| `create2-32-bytes` | 32000 + 2×1 initcode + 6×1 hash [YP, EIP-3860, EIP-1014] | 32008 | 32008 | Yes |  |
| `create2-33-bytes` | 32000 + 2×2 initcode + 6×2 hash [YP, EIP-3860, EIP-1014] | 32016 | 32016 | Yes |  |
| `create2-256-bytes` | 32000 + 2×8 initcode + 6×8 hash [YP, EIP-3860, EIP-1014] | 32064 | 32064 | Yes |  |
| `create2-1024-bytes` | 32000 + 2×32 initcode + 6×32 hash [YP, EIP-3860, EIP-1014] | 32256 | 32256 | Yes |  |
| `funded-call-value-empty` | 2600 cold access + 9000 value + 25000 new account [EIP-2929, YP] | 34300 | 34300 | Yes | Funded sender, one wei; saved status confirms CALL success. |
| `value-call-stipend (child_gasleft)` | 2300 stipend − 2 GAS [EIP-150, YP] | 2298 | 2298 | Yes | Child returns GAS after paying 2 gas for its own GAS opcode. |

## Precompile sweep

The precompile harness copies input and expands memory before timing. It subtracts a seven-argument POP control and restores its 14 gas, leaving the `CALL` account-access charge in the result. EIP-2929 puts active precompile addresses in the initial warm set, so **each first and second call costs execution gas + 100**. The table reports both timed calls in each row (`first / second`); they are separate measurements. See [`run_precompile_sweep.py`](../probes/run_precompile_sweep.py) (`CALL_CORRECTION`, `harness`, `decode`) and the [input vectors](../probes/precompile_vectors.json).

For malformed inputs that fail, the EVM consumes the complete 10,000,000 gas forwarded to the child; the recorded 10,000,100 is **100 access + 10,000,000 failed-call budget**, not a precompile tariff. Their failure status is also checked in the saved result.

| Item (input) | Spec value and source | Expected measured, first / second | Measured Ethereum, first / second | Match | Explanation |
|---|---|---:|---:|:---:|---|
| `0x01` ECRECOVER (valid) | 3,000 [YP] | 3,100 / 3,100 | 3,100 / 3,100 | Yes | 128-byte signature input. |
| `0x01` ECRECOVER (malformed) | 3,000 [YP] | 3,100 / 3,100 | 3,100 / 3,100 | Yes | Invalid signature yields empty success. |
| `0x02` SHA256 (valid) | 60 + 12×⌈128/32⌉ = 108 [YP] | 208 / 208 | 208 / 208 | Yes | Four input words. |
| `0x02` SHA256 (malformed) | 60 + 12×⌈1/32⌉ = 72 [YP] | 172 / 172 | 172 / 172 | Yes | One byte is valid SHA256 input. |
| `0x03` RIPEMD160 (valid) | 600 + 120×4 = 1,080 [YP] | 1,180 / 1,180 | 1,180 / 1,180 | Yes | Four input words. |
| `0x03` RIPEMD160 (malformed) | 600 + 120×1 = 720 [YP] | 820 / 820 | 820 / 820 | Yes | One byte is valid RIPEMD160 input. |
| `0x04` IDENTITY (valid) | 15 + 3×4 = 27 [YP] | 127 / 127 | 127 / 127 | Yes | Four input words. |
| `0x04` IDENTITY (malformed) | 15 + 3×1 = 18 [YP] | 118 / 118 | 118 / 118 | Yes | One byte is valid IDENTITY input. |
| `0x05` MODEXP (valid) | 16×255 = 4,080 [EIP-7883]; formerly ⌊16×255/3⌋ = 1,360 [EIP-2565] | 4,180 / 4,180 current; 1,460 / 1,460 under EIP-2565 | 4,180 / 4,180 | Yes current; No EIP-2565 | Exponent length 32 bytes, exponent bit length 256. EIP-7883 repriced this vector; the EIP-2565-only expectation would be 1,460 including CALL. |
| `0x05` MODEXP (malformed) | Oversized padded length fails; 10,000,000 forwarded gas consumed [EIP-7823, EIP-150] | 10,000,100 / 10,000,100 | 10,000,100 / 10,000,100 | Yes | A one-byte header pads to an oversized base length. |
| `0x06` BN254_ADD (valid) | 150 [EIP-1108] | 250 / 250 | 250 / 250 | Yes |  |
| `0x06` BN254_ADD (malformed) | Forwarded gas fully consumed on invalid input [EIP-150, EIP-196/EIP-197/EIP-152/EIP-2537/EIP-4844] | 10,000,100 / 10,000,100 | 10,000,100 / 10,000,100 | Yes | Invalid input fails; measured value is the forwarded-gas cap, not the normal execution tariff. |
| `0x07` BN254_MUL (valid) | 6,000 [EIP-1108] | 6,100 / 6,100 | 6,100 / 6,100 | Yes |  |
| `0x07` BN254_MUL (malformed) | Forwarded gas fully consumed on invalid input [EIP-150, EIP-196/EIP-197/EIP-152/EIP-2537/EIP-4844] | 10,000,100 / 10,000,100 | 10,000,100 / 10,000,100 | Yes | Invalid input fails; measured value is the forwarded-gas cap, not the normal execution tariff. |
| `0x08` BN254_PAIRING (valid) | 45,000 + 34,000×2 = 113,000 [EIP-1108] | 113,100 / 113,100 | 113,100 / 113,100 | Yes | Two pairing tuples. |
| `0x08` BN254_PAIRING (malformed) | Forwarded gas fully consumed on invalid input [EIP-150, EIP-196/EIP-197/EIP-152/EIP-2537/EIP-4844] | 10,000,100 / 10,000,100 | 10,000,100 / 10,000,100 | Yes | Invalid input fails; measured value is the forwarded-gas cap, not the normal execution tariff. |
| `0x09` BLAKE2F (valid) | 12 rounds = 12 [EIP-152] | 112 / 112 | 112 / 112 | Yes | 213-byte vector. |
| `0x09` BLAKE2F (malformed) | Forwarded gas fully consumed on invalid input [EIP-150, EIP-196/EIP-197/EIP-152/EIP-2537/EIP-4844] | 10,000,100 / 10,000,100 | 10,000,100 / 10,000,100 | Yes | Invalid input fails; measured value is the forwarded-gas cap, not the normal execution tariff. |
| `0x0a` KZG_POINT_EVALUATION (valid) | 50,000 [EIP-4844] | 50,100 / 50,100 | 50,100 / 50,100 | Yes |  |
| `0x0a` KZG_POINT_EVALUATION (malformed) | Forwarded gas fully consumed on invalid input [EIP-150, EIP-196/EIP-197/EIP-152/EIP-2537/EIP-4844] | 10,000,100 / 10,000,100 | 10,000,100 / 10,000,100 | Yes | Invalid input fails; measured value is the forwarded-gas cap, not the normal execution tariff. |
| `0x0b` BLS_G1ADD (valid) | 375 [EIP-2537] | 475 / 475 | 475 / 475 | Yes |  |
| `0x0b` BLS_G1ADD (malformed) | Forwarded gas fully consumed on invalid input [EIP-150, EIP-196/EIP-197/EIP-152/EIP-2537/EIP-4844] | 10,000,100 / 10,000,100 | 10,000,100 / 10,000,100 | Yes | Invalid input fails; measured value is the forwarded-gas cap, not the normal execution tariff. |
| `0x0c` BLS_G1MSM (valid) | 12,000×1×1000/1000 = 12,000 [EIP-2537] | 12,100 / 12,100 | 12,100 / 12,100 | Yes | One G1 tuple. |
| `0x0c` BLS_G1MSM (malformed) | Forwarded gas fully consumed on invalid input [EIP-150, EIP-196/EIP-197/EIP-152/EIP-2537/EIP-4844] | 10,000,100 / 10,000,100 | 10,000,100 / 10,000,100 | Yes | Invalid input fails; measured value is the forwarded-gas cap, not the normal execution tariff. |
| `0x0d` BLS_G2ADD (valid) | 600 [EIP-2537] | 700 / 700 | 700 / 700 | Yes |  |
| `0x0d` BLS_G2ADD (malformed) | Forwarded gas fully consumed on invalid input [EIP-150, EIP-196/EIP-197/EIP-152/EIP-2537/EIP-4844] | 10,000,100 / 10,000,100 | 10,000,100 / 10,000,100 | Yes | Invalid input fails; measured value is the forwarded-gas cap, not the normal execution tariff. |
| `0x0e` BLS_G2MSM (valid) | 22,500×1×1000/1000 = 22,500 [EIP-2537] | 22,600 / 22,600 | 22,600 / 22,600 | Yes | One G2 tuple. |
| `0x0e` BLS_G2MSM (malformed) | Forwarded gas fully consumed on invalid input [EIP-150, EIP-196/EIP-197/EIP-152/EIP-2537/EIP-4844] | 10,000,100 / 10,000,100 | 10,000,100 / 10,000,100 | Yes | Invalid input fails; measured value is the forwarded-gas cap, not the normal execution tariff. |
| `0x0f` BLS_PAIRING (valid) | 37,700 + 32,600×2 = 102,900 [EIP-2537] | 103,000 / 103,000 | 103,000 / 103,000 | Yes | Two pairing tuples. |
| `0x0f` BLS_PAIRING (malformed) | Forwarded gas fully consumed on invalid input [EIP-150, EIP-196/EIP-197/EIP-152/EIP-2537/EIP-4844] | 10,000,100 / 10,000,100 | 10,000,100 / 10,000,100 | Yes | Invalid input fails; measured value is the forwarded-gas cap, not the normal execution tariff. |
| `0x10` BLS_MAP_FP_TO_G1 (valid) | 5,500 [EIP-2537] | 5,600 / 5,600 | 5,600 / 5,600 | Yes |  |
| `0x10` BLS_MAP_FP_TO_G1 (malformed) | Forwarded gas fully consumed on invalid input [EIP-150, EIP-196/EIP-197/EIP-152/EIP-2537/EIP-4844] | 10,000,100 / 10,000,100 | 10,000,100 / 10,000,100 | Yes | Invalid input fails; measured value is the forwarded-gas cap, not the normal execution tariff. |
| `0x100` P256VERIFY (valid) | 6,900 [EIP-7951]; RIP-7212 specifies 3,450 | 7,000 / 7,000 | 7,000 / 7,000 | Yes | Ethereum uses EIP-7951 pricing. RIP-7212 is a different proposal. |
| `0x100` P256VERIFY (malformed) | 6,900 [EIP-7951] | 7,000 / 7,000 | 7,000 / 7,000 | Yes | 159-byte invalid input returns empty success at full price. |
| `0x11` BLS_MAP_FP2_TO_G2 (valid) | 23,800 [EIP-2537] | 23,900 / 23,900 | 23,900 / 23,900 | Yes |  |
| `0x11` BLS_MAP_FP2_TO_G2 (malformed) | Forwarded gas fully consumed on invalid input [EIP-150, EIP-196/EIP-197/EIP-152/EIP-2537/EIP-4844] | 10,000,100 / 10,000,100 | 10,000,100 / 10,000,100 | Yes | Invalid input fails; measured value is the forwarded-gas cap, not the normal execution tariff. |

## Result and interpretation

- **Current Ethereum rules:** 209/209 individual gas readings match the expected harness output: 137 gas-schedule readings and 72 precompile readings (valid and malformed, first and second). The tables have 173 item rows because each precompile row shows its two calls together.
- **Mismatch against the requested EIP-2565-only MODEXP formula:** the valid MODEXP case is **4,180 measured versus 1,460 expected** (a 2,720 gas difference). This is a **spec fork subtlety**, not a measurement bug: EIP-7883 removed EIP-2565's division by three for this input, giving 4,080 execution + 100 warm access. Against EIP-2565 alone, **207/209 readings (172/173 table rows) match**. The present Ethereum baseline has **no unexplained spec mismatches**.
- **P256 naming subtlety:** 7,000 is 6,900 under Ethereum's EIP-7951 plus 100 warm access. RIP-7212's 3,450 price would predict 3,550, but it is a different schedule; this is **not a mismatch** with Ethereum's spec.
- **Cross-chain contamination risk, despite an exact gas match:** `call-value-empty` runs from an **unfunded creation context**. Its 34,300 gas is the charge for an attempted value transfer to a new account, but the transfer fails. Treating that row as proof of a successful value `CALL` would be a **measurement-interpretation bug**. The separate `funded-call-value-empty` row checks success and measures the same 34,300 gas. The source matrix already labels the unfunded row `unfunded-control-only`.
- **Cross-chain scope:** precompile values are observed `CALL` prices, including address access. An address absent from a chain's active-precompile warm set may cost 2,600 on the first call and 100 on the second under EIP-2929; a first-call difference alone does not identify a different cryptographic tariff. Malformed failures at 10,000,100 are gas-budget exhaustion observations, so comparing them as implementation prices would also contaminate conclusions. The one-byte SHA256, RIPEMD160, and IDENTITY “malformed” vectors actually succeed; ECRECOVER and P256 invalid vectors return empty success. Compare status and output alongside gas.
- **Refund scope:** `GAS` deltas for SSTORE do not include transaction-level refunds. The 100 gas dirty writes are correct under EIP-2200/EIP-2929; EIP-3529 affects refunds, not these timer deltas.

## Specification citations

- [YP]: [Ethereum Yellow Paper, Appendix G/H and equation for memory cost](https://ethereum.github.io/yellowpaper/paper.pdf): opcode tiers, `C_mem(w)=3w+⌊w²/512⌋`, LOG charges, call, CREATE, and original precompile prices.
- [EIP-150]: [Gas cost changes for IO-heavy operations](https://eips.ethereum.org/EIPS/eip-150#specification): CALL gas forwarding and 2,300 value stipend.
- [EIP-1014]: [CREATE2](https://eips.ethereum.org/EIPS/eip-1014#specification): six gas per initcode word for hashing.
- [EIP-1344]: [CHAINID](https://eips.ethereum.org/EIPS/eip-1344#specification).
- [EIP-1884]: [SELFBalance](https://eips.ethereum.org/EIPS/eip-1884#specification).
- [EIP-2200]: [SSTORE gas metering](https://eips.ethereum.org/EIPS/eip-2200#specification).
- [EIP-2929]: [Cold/warm account and storage access](https://eips.ethereum.org/EIPS/eip-2929#specification), including initial warm precompile addresses.
- [EIP-3198]: [BASEFEE](https://eips.ethereum.org/EIPS/eip-3198#specification).
- [EIP-3529]: [Refund reductions](https://eips.ethereum.org/EIPS/eip-3529#specification).
- [EIP-3855]: [PUSH0](https://eips.ethereum.org/EIPS/eip-3855#specification).
- [EIP-3860]: [Initcode word cost](https://eips.ethereum.org/EIPS/eip-3860#specification).
- [EIP-5656]: [MCOPY](https://eips.ethereum.org/EIPS/eip-5656#specification).
- [EIP-1153]: [Transient storage](https://eips.ethereum.org/EIPS/eip-1153#specification).
- [EIP-196/EIP-197]: [BN254 operations](https://eips.ethereum.org/EIPS/eip-196#specification) and [pairing](https://eips.ethereum.org/EIPS/eip-197#specification), including invalid-input failure.
- [EIP-1108]: [BN254 repricing](https://eips.ethereum.org/EIPS/eip-1108#specification).
- [EIP-152]: [BLAKE2F gas and invalid input](https://eips.ethereum.org/EIPS/eip-152#specification).
- [EIP-2565]: [Earlier MODEXP gas formula](https://eips.ethereum.org/EIPS/eip-2565#specification).
- [EIP-7883]: [Current MODEXP repricing](https://eips.ethereum.org/EIPS/eip-7883#specification).
- [EIP-7823]: [MODEXP input length cap](https://eips.ethereum.org/EIPS/eip-7823#specification).
- [EIP-4844]: [Point evaluation precompile](https://eips.ethereum.org/EIPS/eip-4844#point-evaluation-precompile) and blob opcodes.
- [EIP-2537]: [BLS12-381 precompile gas schedule](https://eips.ethereum.org/EIPS/eip-2537#gas-schedule).
- [EIP-7951]: [Ethereum P256VERIFY precompile](https://eips.ethereum.org/EIPS/eip-7951#specification); [RIP-7212](https://github.com/ethereum/RIPs/blob/master/RIPS/rip-7212.md) has a different price.

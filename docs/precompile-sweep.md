# Precompile known-answer and gas sweep — 2026-10-20

The [per-chain matrix](../results/2026-10-20/precompile-sweep/MATRIX.csv) has
468 address/chain rows: 18 addresses (`0x01`–`0x11` and `0x100`) on 26 RPC
scopes. Each row reports the real-vector output check, first and second CALL
gas, Ethereum reference gas, a malformed or short-input result, the later-block
repeat, the listed second endpoint, and JSON pointers into the [raw evidence
directory](../results/2026-10-20/precompile-sweep/). Evmos has no no-key public
RPC in the [registry](../probes/chains.json), so it has a recorded reason rather
than a fabricated row. Curated focused-probe-30 findings are now in the catalog; the
independent review's [round-4 review](verification/round-4-sample.md) sampled new catalog rows, and the [top-ten review](verification/round-4-top10.md) replayed valid G1ADD.

## Method and scope

The [vector manifest](../probes/precompile_vectors.json) pins geth commit
`943517bd622a05c70185e5154916aff43b1964d8` and execution-spec-tests
commit `10eaa63d5da2f50b63d4359968f36542212f9f50`; it links each valid and
invalid or short-input vector to the source file. Sources were accessed
2026-10-20. The [runner](../probes/run_precompile_sweep.py) executes only
`eth_call` creation code. It copies the vector into memory, makes two CALLs to
the address, and returns the output bytes, CALL success bits, return lengths,
and measured gas. A no-op control with the same stack setup is subtracted; a
14-gas correction removes its seven POPs. The numbers include CALL account
access and precompile execution; first and second calls can differ because of
cold/warm access. They are **not** transaction fees or isolated handler costs.
The raw JSON retains the URL, chain ID, sampled block header, block tag, request
and response bodies, HTTP status, and observation time. Response headers are
omitted because public RPCs can include transient cookies.

Each CALL forwards at most 10 million gas so a failed operation can return its
status to the outer creation call. If a **valid** vector exhausted that limit,
the runner retried one CALL with 25 million forwarded gas and saved both raw
attempts. A CALL failure that spends the cap is a bounded failure, **not** an
exact precompile price or proof that the address lacks an implementation. For
SHA-256 (`0x02`), RIPEMD-160 (`0x03`), and identity (`0x04`), every byte string
is a valid input; the second vector is a one-byte length control, not a
malformed input. Other second vectors exercise an invalid signature, point,
field value, or required length. `empty-success` means CALL returned success
with zero bytes; `call-failed` means the inner CALL returned zero; an outer
JSON-RPC error is kept separately. None alone proves that a precompile is
unsupported.

## Measured observations

| Chain or group | Real-vector observation | CALL-inclusive gas example and boundary |
|---|---|---|
| Ethereum | 18/18 expected outputs matched. | BLS G1ADD (`0x0b`) 475 on both calls; malformed zero-length G1ADD failed and consumed the 10M forwarded-gas cap. |
| Polygon PoS | 17/18 matched; KZG (`0x0a`) returned empty success. | G1ADD 1,150 versus Ethereum 475; pairing (`0x0f`) 298,510 versus 103,000. The listed second endpoint agreed. |
| zkSync Era | 8/18 matched; RIPEMD-160, BLAKE2F, KZG, and seven BLS vectors returned CALL failure. | G1ADD failed with 2,600 then 100 gas; P256 (`0x100`) matched on both endpoints, whose first-call gas differed by 4. The cost difference is an endpoint disagreement. |
| Scroll | 8/18 matched; RIPEMD-160 and BLAKE2F failed, while KZG and seven BLS vectors returned empty success. | G1ADD 2,600 then 100 gas, a no-output call; no second endpoint is listed. |
| Avalanche C-Chain, Blast, HyperEVM | Real BLS vectors at `0x0b`–`0x11` returned empty success. | A first empty-account-style call used 2,600 gas and a repeated call 100; no second endpoint was in the original registry. The independent review later [replayed Avalanche G1ADD on PublicNode](verification/round-4-top10.md#3-avalanche-g1add). These CALL-inclusive figures are not a handler tariff. |
| MegaETH | 18/18 matched. | G1ADD used 2,975 then 475 gas: a 2,500 first-call surcharge. The second endpoint agreed for G1ADD; its KZG request timed out under a free-plan limit. |
| Somnia | 16/18 matched. Valid pairing (`0x08`) and P256 (`0x100`) returned CALL failure even on separate 25M-gas attempts; this does not establish their absence. | G1ADD used 482,500 then 82,500 gas; the listed second endpoint agreed. |
| Monad | 17/18 matched; the KZG call returned JSON-RPC `unexpected error`. | G1ADD matched Ethereum at 475; BN254 pairing used 565,100 versus Ethereum 113,100. The listed second endpoint reproduced the KZG error. |
| TRON | The official endpoint rejected every no-`to` creation call with `invalid address`. | This method supplies no precompile behavior or gas evidence for TRON. |
| Tempo | 17/18 matched; the primary KZG call had a transport error on both sampled blocks. | The listed second endpoint returned the correct KZG output at 50,100 gas. The primary error is an endpoint gap, not a chain difference. |

The matrix also retains all matching chains, smaller price changes (including
MODEXP and P256), and every other status. Every one of the 468 valid/short-input
row pairs repeated with the same interpretation at a later sampled block.
There were 11 usable listed second-endpoint scopes, 15 scopes without one,
and one unusable Ethereum second endpoint: Cloudflare returned errors for block
context. Among the 198 usable second-endpoint rows, 195 valid-vector cells had
the same status, output and gas fields (including recurring error classes),
zkSync P256 differed by four gas, and the Tempo and MegaETH KZG rows
had endpoint errors on one side. Malformed-input results can differ by endpoint
error class; the matrix shows these separately. Later-block repetition does not
prove that a provider honors historical block tags, especially on HyperEVM.

Run the initial sweep and matrix with `./probes/run.sh`; to repeat these
confirmations, use `python3 probes/run_precompile_sweep.py --phase confirm`
then `--phase secondary`, followed by
`python3 probes/build_precompile_matrix.py`. No public transaction was signed,
sent, or deployed. Curated measured differences are in the catalog; the raw
matrix keeps failed, capped, and matching controls separately.

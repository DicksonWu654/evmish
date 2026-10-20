# EVMish

Where EVM-compatible chains quietly differ from Ethereum.

We compare sampled EVM execution, RPC simulation, and chain documentation. The catalog, blog, raw results, examples, and static site describe observations recorded on 2026-10-18 and 2026-10-19.

## Run the probe kit

Python 3 and a public RPC connection are required. Run `./probes/run.sh` from this directory (use `--help` for chain selection). This performs read-only calls; it never signs, sends a transaction, or deploys a contract to a public network. Public third-party providers are explicitly labeled in `probes/chains.json`. Requests are rate limited and raw responses cached.

An `eth_call` with no `to` field executes the supplied `data` as contract-creation init code. The init code can return opcode and chain-context observations without deploying a contract. Provider restrictions and VM execution failures are recorded separately.

## Open the site

Run `node site/tools/serve.mjs 4173` and open `http://localhost:4173`. See `site/package.json` for data-build commands. No dependency install is required to serve the static site. Run public validators with `for script in scripts/validate_*.py; do python3 "$script"; done`.

## Result classes

`probe-verified` means recorded probe evidence supports the scoped observation. `source-verified` means a pinned implementation source supports the claim. `doc-only` means documentation or an unresolved observation supports only a limited statement. An RPC rejection, execution failure, unavailable endpoint, or unobserved behavior is not proof of unsupported protocol behavior. Matrix states also distinguish account state, unstable historical tags, and RPC simulation from VM divergence.

## Limits and corrections

Results apply to the recorded dates, endpoint hosts, request bodies, and sampled blocks. Read-only calls do not reproduce all transaction, fee, cross-domain, or lifecycle behavior. Legacy empty-input precompile probes test dispatch only; the [known-answer sweep](docs/precompile-sweep.md) checks real vectors and measures CALL gas separately. The [lifecycle sweep](docs/lifecycle-sweep.md) tests size boundaries and same-call state, with gas-bound and post-transaction limits labeled. The public export removes HTTP response headers and legacy MegaETH testnet evidence; request and response bodies, status codes, endpoint hosts, and timestamps remain. Active MegaETH evidence is mainnet. See `docs/verification.md` and `docs/endpoint-audit.md`.

## Prior art and feedback

We credit [mds1/evm-diff](https://github.com/mds1/evm-diff), [shemnon/evm-directory](https://github.com/shemnon/evm-directory), chain documentation, and the linked EIPs and client sources. To request a probe or report an error, open an issue at https://github.com/DicksonWu654/evmish, including the chain, endpoint host, block, request, raw response, and the disputed catalog row. Do not include credentials.

## License

Code is licensed under [MIT](LICENSE). Data and writing in `results/`, `CATALOG.md`, `docs/`, `blog/post.md`, and `site/data/` are licensed under [CC BY 4.0](LICENSE-DATA).

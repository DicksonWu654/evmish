/* Shared data model for the site and the launch cards. Reads data/data.json
   (see data/SCHEMA.md); numbers are never typed here. */
(function (g) {
  "use strict";
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

  async function loadData(base) {
    base = base || "";
    if (location.protocol !== "file:") {
      try {
        const r = await fetch(base + "data/data.json", { cache: "no-store" });
        if (r.ok) return await r.json();
      } catch (e) { /* fall through to bundled copy */ }
    }
    if (!window.EVM_DATA) {
      await new Promise((res, rej) => { const sc = document.createElement("script"); sc.src = base + "assets/data.js"; sc.onload = res; sc.onerror = () => rej(new Error("Could not load data. Run `npm run build` in site/, or serve the repository over http.")); document.head.appendChild(sc); });
    }
    return window.EVM_DATA;
  }


  const CLASSES = {
    reference: { name: "ethereum", short: "Reference", text: "Ethereum's own answer. Every other cell is compared with this column." },
    same: { name: "same", short: "Same", text: "The chain returned the same normalized answer as Ethereum." },
    differs: { name: "differs", short: "Differs", text: "The chain ran the probe and returned a different value or relationship than Ethereum." },
    "execution-failure": { name: "execution-failure", short: "Execution failure", text: "The endpoint accepted the call and the VM failed on code that Ethereum runs, such as an invalid opcode." },
    "rpc-rejected": { name: "rpc-rejected", short: "RPC rejected", text: "The endpoint refused the request before any code ran. It describes the RPC adapter; the VM never saw the probe." },
    "endpoint-artifact": { name: "endpoint-artifact", short: "Endpoint artifact", text: "Kept but left out of the comparison: the endpoint ignored the requested block, or the RPC simulated the field." },
    "state-only": { name: "state-only", short: "State only", text: "A fact about one fixed address on this chain, such as whether it holds code. Kept out of the comparison." },
    unavailable: { name: "unavailable", short: "Unavailable", text: "No usable endpoint result was recorded for this chain." },
  };
  const CLASS_MAP = { "unsupported/execution-failure": "execution-failure" };
  const ATTENTION = new Set(["differs", "execution-failure"]);

  // Finding copy. Chains, probe outputs and numbers come from data; prose and code are written here.
  const COPY = {
    bls: {
      title: () => "A valid BLS G1ADD call returns empty success",
      assume: "Prague shipped the BLS12-381 precompiles at 0x0b to 0x11, so any chain on a recent fork has them.",
      why: "The tested G1ADD call returned success with zero output bytes on these endpoints. A verifier that checks only the success flag could continue without a valid point; the effect depends on its later output checks.",
      unsafe: `(bool ok, bytes memory out) = address(0x0b).staticcall(input);
require(ok, "precompile failed");
// the recorded mismatch returned empty output`,
      safe: `// deploy time: known-answer test with a fixed vector proves 0x0b is G1ADD
constructor() {
    (bool ok, bytes memory out) = address(0x0b).staticcall(KAT_INPUT);
    require(ok && keccak256(out) == KAT_HASH, "G1ADD vector mismatch");
}

// runtime: arbitrary input, so check the call and the output size
(bool ok, bytes memory out) = address(0x0b).staticcall(input);
require(ok && out.length == 128, "wrong G1ADD output"); // G1ADD returns 128 bytes`,
    },
    ripemd: {
      title: (f, listNames) => `RIPEMD160 fails on ${listNames(f.chains)}`,
      assume: "RIPEMD160 at 0x03 has been on Ethereum since launch, so every EVM chain has it.",
      why: "The outer call completes and the precompile call inside it fails. Bitcoin-style address derivation in a bridge compiles, passes every Ethereum test, and then reverts or misreads output on the target chain.",
      unsafe: `function btcHash160(bytes memory pubkey) internal pure returns (bytes20) {
    return ripemd160(abi.encodePacked(sha256(pubkey)));
}`,
      safe: `constructor() {
    // known-answer test on the target chain: RIPEMD160("abc")
    require(
        ripemd160("abc") == bytes20(hex"8eb208f7e05d987a9b044a8e98c6b087f15a0bfc"),
        "RIPEMD160 unavailable"
    );
}`,
    },
    number: {
      title: (f, listNames) => `On ${listNames(f.chains)}, block.number is the L1 block number`,
      assume: "block.number counts this chain's own blocks, the same number the block explorer and RPC header show.",
      why: "Off-chain code that reads the L2 header and on-chain code that reads block.number are using two different clocks. A timelock or vote window computed from one and checked against the other opens at the wrong time.",
      unsafe: `// window computed off-chain from the L2 header
require(block.number >= proposal.startBlock, "not started");
require(block.number <= proposal.startBlock + VOTING_BLOCKS, "ended");`,
      safe: `// pick the unit on purpose: seconds are explicit
require(block.timestamp >= proposal.start, "not started");
require(block.timestamp <= proposal.start + VOTING_PERIOD, "ended");
// write down sequencer and finality assumptions separately`,
    },
    prevrandao: {
      title: (f, listNames) => `PREVRANDAO is a constant on ${listNames(f.chains)}`,
      assume: "block.prevrandao comes from the beacon chain, so it is a usable seed for low-stakes randomness.",
      why: "On these chains the opcode returns a fixed number that anyone can read in advance. A raffle, mint order or game seeded from it has a predictable outcome.",
      unsafe: `uint256 winner = uint256(
    keccak256(abi.encode(block.prevrandao, round))
) % entrants.length;`,
      safe: `// request randomness from a verifiable source; use it only in the callback
function fulfillRandomness(uint256 requestId, uint256 randomness) internal override {
    winner = entrants[randomness % entrants.length];
}`,
    },
    gas: {
      title: (f, listNames) => `Cold access on ${listNames(f.chains)} costs about ${f.ratio}x Ethereum`,
      assume: "Gas costs match Ethereum's schedule, so a stipend tuned on Ethereum works everywhere.",
      why: "Hardcoded gas stipends, relayer budgets and “this loop fits in a block” estimates tuned on Ethereum come up short. A hook that runs fine on Ethereum can run out of gas on the target.",
      unsafe: `// stipend tuned against Ethereum's cold-access price
(bool ok, ) = hook.call{gas: HOOK_GAS}(payload);
require(ok, "hook failed");`,
      safe: `// budget measured on the target chain, set per deployment
uint256 public immutable hookGas;
constructor(uint256 measuredHookGas) { hookGas = measuredHookGas; }

function runHook(bytes calldata payload) internal {
    (bool ok, ) = hook.call{gas: hookGas}(payload);
    require(ok, "hook failed");
}`,
    },
  };

  // Second-sweep copy. h = { F: format a data number, name: chain id -> name, grab }.
  // Every number in a title is read from data: gas values, outcome fields, or the item/probe id.
  const SWEEP_COPY = {
    "tempo-create": {
      family: "Gas schedule · CREATE",
      title: (x, h) => `An empty CREATE costs ${h.F(x.g.val)} gas on ${h.name(x.chain)}`,
      scope: "Measured inside a read-only creation call. The child is STOP-only with zero runtime bytes, so this is creation base cost, not code deposit, and not a transaction fee.",
      card: "Factory and deployer budgets copied from Ethereum can run out before the child exists.",
    },
    "somnia-sstore": {
      family: "Gas schedule · SSTORE",
      title: (x, h) => `A first storage write costs ${h.F(x.g.val)} gas on ${h.name(x.chain)}`,
      scope: "The zero-to-nonzero write of a fresh slot inside a read-only creation call. Refunds are not measured.",
      card: (x, h) => { const gate = h.grab(x.row && x.row.consequence, /at least ([\d,]+) gas remaining/); return gate ? `The write also needs at least ${gate} gas left before it runs. A smaller cap fails even when it covers the charge.` : "A hook or relayer with a fixed allowance can fail on the first write."; },
    },
    "bls-valid": {
      family: "Precompile vectors · G1ADD",
      title: () => "A valid G1ADD vector returns empty success",
      scope: "Ranked third in the sweep. The full card with every affected chain is finding 01 above.",
    },
    "somnia-runtime": {
      family: "Lifecycle · runtime size",
      title: (x, h) => `${h.name(x.chain)}'s simulation created a ${h.F(x.tgt.outcome.code_size)}-byte runtime child`,
      scope: "A read-only simulation. It does not show that a transaction with that gas limit would be admitted.",
    },
    "monad-init": {
      family: "Lifecycle · init-code size",
      title: (x, h) => `${h.name(x.chain)} created a child from ${h.F(h.grab(x.probe, /init-(\d+)/))}-byte init code`,
      scope: "A read-only simulation of the inner CREATE. Ethereum's control failed at the outer call, so it gave no inner CREATE status to compare.",
    },
    "zksync-selfdestruct": {
      family: "Lifecycle · SELFDESTRUCT",
      title: (x, h) => `A same-call SELFDESTRUCT returns status ${x.tgt.outcome.kill_status} on ${h.name(x.chain)}`,
      scope: "The kill failed closed: the child kept its code and the beneficiary gained nothing in the returned state. Post-transaction deletion is not measured.",
    },
    "kaia-value": {
      family: "Lifecycle · precompile value",
      title: (x, h) => `On ${h.name(x.chain)}, a value CALL to the identity precompile fails`,
      scope: "One tested read-only call carrying one wei, not a general rule for native value.",
    },
    "monad-memory": {
      family: "Gas schedule · memory",
      title: (x, h) => `Expanding memory to ${h.F(h.grab(x.item, /memory-expand-(\d+)-words/))} words costs ${h.F(x.g.val)} gas on ${h.name(x.chain)}`,
      scope: "An isolated MSTORE expansion inside a read-only creation call. Cheaper expansion below the cap is not unbounded memory and not a whole-transaction cost.",
      card: (x, h) => { const cap = h.grab(x.row && x.row.consequence, /(\d+\s?MB) memory cap/); return `Quadratic memory cost is no longer a brake on input size.${cap ? ` Monad caps memory at ${cap} instead.` : ""}`; },
    },
    "megaeth-log": {
      family: "Gas schedule · LOG",
      title: (x, h) => `LOG4 with ${h.F(h.grab(x.item, /log4-(\d+)-bytes/))} data bytes costs ${h.F(x.g.val)} gas on ${h.name(x.chain)}`,
      scope: "Memory was expanded first, so this prices the LOG itself. The read-only call discards the log; receipts are not measured.",
      card: "Event-heavy relayers and callbacks capped from an Ethereum test can run out of gas.",
    },
    "sei-sstore": {
      family: "Gas schedule · SSTORE",
      title: (x, h) => `A first storage write costs ${h.F(x.g.val)} gas on ${h.name(x.chain)}`,
      scope: "Sei's write price is set by governance, so this is a dated measurement.",
    },
  };

  // Maps data.json (see data/SCHEMA.md) onto the shape the views use.
  // Headline slugs -> probes and how to name the affected chains.
  const HEADLINES = {
    "bls-precompiles-missing": { id: "bls", probes: ["precompile-vector/0x0b/valid"], chains: "lines", category: "Precompiles" },
    "ripemd160-zksync-scroll": { id: "ripemd", probes: ["precompile-0x03-ripemd160"], chains: "matrix-all", category: "Precompiles" },
    "arbitrum-number-l1": { id: "number", probes: ["number"], chains: "lines", category: "Block context" },
    "prevrandao-constants": { id: "prevrandao", probes: ["prevrandao"], chains: "lines", category: "Randomness" },
    "monad-cold-access": { id: "gas", probes: ["cold-warm-extcodesize"], chains: "lines", category: "Gas" },
  };
  const ORDER = ["bls", "ripemd", "number", "prevrandao", "gas"];
  const CAT_LABEL = { "opcodes": "Opcodes", "block context": "Block context", "precompiles": "Precompiles", "addresses": "Addresses", "account code": "Account code", "gas/fees": "Gas and fees", "gas schedule": "Gas schedule", "precompile vectors": "Precompile vectors", "lifecycle": "Lifecycle" };

  function adapt(d) {
    const ref = "ethereum";
    // A chain's primary raw result file: the evidence path of its own cells that sits in its own folder.
    const chainEv = {};
    d.matrix.cells.forEach((c) => { if (!chainEv[c.chain]) { const p = (c.evidence || []).find((x) => x.includes(`/${c.chain}/`)); if (p) chainEv[c.chain] = p; } });
    const evFor = (id) => chainEv[id] || null;
    const hosts = Object.fromEntries(((d.meta.endpoints || {}).hosts || []).map((h) => (typeof h === "string" ? [h, { host: h }] : [h.host, h])));
    const chains = d.chains.map((c) => ({ id: c.id, name: c.name, chainId: c.chain_id, block: c.block, timestamp: c.timestamp, status: c.profile_status, rpc: c.endpoint, rpcLabel: hostLabel(hosts[c.endpoint] || (c.endpoint ? { host: c.endpoint } : null)), evidence: evFor(c.id), note: c.note || null }));
    // Ethereum first, then the rest in data order.
    chains.sort((a, b) => (a.id === ref ? -1 : b.id === ref ? 1 : 0));
    const probes = d.probes.map((p) => ({ id: p.id, label: p.id.replace(/^precompile-/, "").replace(/-address-[0-9a-f]+$/, ""), name: p.name, category: CAT_LABEL[p.category] || p.category, meaning: p.description, initCode: p.init_code || null }));
    // group rows by category while keeping result order inside a category
    const catOrder = [...new Set(probes.map((p) => p.category))];
    probes.sort((a, b) => catOrder.indexOf(a.category) - catOrder.indexOf(b.category));
    const cells = {};
    d.matrix.cells.forEach((c) => {
      const cls = c.chain === ref ? "reference" : CLASS_MAP[c.class] || c.class;
      (cells[c.chain] = cells[c.chain] || {})[c.probe] = { class: cls, rawClass: c.class, v: c.value, value: summarize(c.value), evidence: c.evidence || [], block: c.block || null, sampleDate: c.sample_date || null };
    });
    const catalogRows = d.findings.filter((f) => f.number != null);
    const catalog = catalogRows.map((f) => ({
      n: f.number, label: f.label, chain: f.chain_scope, title: f.behavior, consequence: f.consequence, date: f.date,
      evidence: (f.evidence_paths && f.evidence_paths.length ? f.evidence_paths : [f.evidence_path]).filter(Boolean).map((p) => ({ label: p.replace(/^results\/[^/]+\//, ""), path: p })),
    }));
    const findings = [];
    d.findings.filter((f) => f.headline && f.slug && HEADLINES[f.slug]).forEach((f) => {
      const h = HEADLINES[f.slug], hc = f.headline_content || {};
      let ids;
      if (h.chains === "matrix-all") {
        ids = chains.filter((c) => c.id !== ref && h.probes.every((p) => ATTENTION.has((cells[c.id] || {})[p]?.class))).map((c) => c.id);
      } else {
        const txt = (hc.raw_lines || "").toLowerCase();
        ids = chains.filter((c) => c.id !== ref && (txt.includes(c.name.toLowerCase()) || txt.includes(c.name.split(" ")[0].toLowerCase() + " block"))).map((c) => c.id);
        if (!ids.length && cells[f.chain_scope]) ids = [f.chain_scope];
      }
      { // order chains as the raw lines mention them, then the rest
        const txt = (hc.raw_lines || "").toLowerCase();
        const at = (i) => { const n = chains.find((k) => k.id === i).name.toLowerCase(); let j = txt.indexOf(n); if (j < 0) j = txt.indexOf(n.split(" ")[0] + " block"); return j < 0 ? 1e9 : j; };
        ids.sort((x, y) => at(x) - at(y));
      }
      const lines = parseLines(hc.raw_lines || "", chains);
      const ev = new Set(f.evidence_paths || [f.evidence_path]);
      ids.forEach((id) => { const p = evFor(id); if (p) ev.add(p); });
      const out = { id: h.id, slug: f.slug, n: f.number, category: h.category, probes: h.probes, chains: ids, lines, rawLines: hc.raw_lines || "", title: hc.title, unsafe: hc.solidity_unsafe, safe: hc.solidity_safe,
        evidence: [...ev].map((p) => ({ label: p.replace(/^results\/[^/]+\//, ""), path: p })) };
      if (h.id === "gas") {
        const t = cells[ids[0]]?.["cold-warm-extcodesize"]?.v, e = cells[ref]?.["cold-warm-extcodesize"]?.v;
        if (t && e && Number(e.gas_delta)) { out.ratio = Math.round(Number(t.gas_delta) / Number(e.gas_delta)); out.target = t; out.eth = e; }
      }
      findings.push(out);
    });
    findings.sort((a, b) => ORDER.indexOf(a.id) - ORDER.indexOf(b.id));
    const st = d.findings.find((f) => f.slug === "zksync-create2-docs-stale");
    let staleNote = null;
    if (st) {
      const cz = cells[st.chain_scope]?.create2?.v, ce = cells[ref]?.create2?.v;
      const docs = [...String(st.headline_content?.note || "").matchAll(/\[([^\]]+)\]\((https?:[^)]+)\)/g)].map((m) => ({ label: m[1], path: m[2] }));
      staleNote = { chain: st.chain_scope, probe: "create2", label: st.label, docs,
        lines: [ce && { chain: ref, block: chains[0].block, text: `create2 -> formula_matches=${ce.formula_matches}` }, cz && { chain: st.chain_scope, block: chains.find((c) => c.id === st.chain_scope)?.block, text: `create2 -> formula_matches=${cz.formula_matches}` }].filter(Boolean),
        evidence: docs.concat((st.evidence_paths || [st.evidence_path]).map((p) => ({ label: p.replace(/^results\/[^/]+\//, ""), path: p }))) };
    }
    // confirmed differences = cells where the VM answered differently from Ethereum
    let differences = 0;
    Object.values(cells).forEach((row) => Object.values(row).forEach((c) => { if (ATTENTION.has(c.class)) differences++; }));
    const verification = (d.meta.verification_rounds || []).map((r) => ({ round: r.round, date: r.date, seed: r.seed, sampled: r.sampled, correct: r.correct, wrong: r.wrong, unverifiable: r.unverifiable, result: r.result }));
    const exSup = EXAMPLE;
    const exProbe = d.probes.find((p) => p.id === exSup.probe);
    const exCell = cells[exSup.chain]?.[exSup.probe]?.v;
    const exChain = chains.find((c) => c.id === exSup.chain);
    const example = exCell && exChain && exProbe && exProbe.init_code ? { chain: exSup.chain, probe: exSup.probe, initCode: exProbe.init_code, block: exChain.block, rawReturn: exCell.raw_return, evidence: cells[exSup.chain][exSup.probe].evidence } : null;
    const checklist = (d.checklist || []).map((t) => esc(t).replace(/`([^`]+)`/g, "<code>$1</code>"));
    const gas = adaptGas(d, chains, cells);
    const sweep = adaptSweep(d, gas, cells, catalog);
    // BLS: chains where the same valid vector failed closed (CALL failure, no empty success).
    findings.forEach((f) => { if (f.id === "bls") { const p = f.probes[0]; f.failClosed = chains.filter((c) => c.id !== ref && cells[c.id]?.[p]?.v?.status === "call-failed").map((c) => c.id); const e = cells[ref]?.[p]?.v; f.ethBytes = e && e.output ? (e.output.length - 2) / 2 : null; } });
    return {
      meta: { date: d.meta.latest_probe_date || d.meta.probe_date, dateLong: (d.meta.evidence_dates || []).join(" to ") || d.meta.probe_date, chains: d.meta.chain_count, probes: d.meta.probe_count, differences, endpoints: d.meta.endpoints?.count, hosts: Object.values(hosts).map(hostLabel), secondary: ((d.meta.endpoints || {}).secondary || []).map((h) => ({ chain: h.chain, label: hostLabel(h), usedFor: h.used_for })), kit: d.meta.kit_command, author: d.meta.author },
      refChain: ref, chains, probes, categories: catOrder, cells, catalog, findings, staleNote, verification, example, checklist, gas, sweep,
      counts: { catalog: catalog.length, byLabel: catalog.reduce((a, r) => ((a[r.label] = (a[r.label] || 0) + 1), a), {}) },
    };
  }
  // Gas schedule (data.gas_schedule): chain x item, ratio = chain gas / Ethereum gas.
  const GAS_FAMILY = { simple: "Arithmetic and context", memory: "Memory expansion", copy: "Copies", flow: "Jumps", mcopy: "MCOPY", keccak: "KECCAK256", log: "Logs", "cold-warm": "Cold and warm access", "call-value": "Value calls", storage: "SSTORE", transient: "Transient storage", create: "CREATE and CREATE2", stipend: "Call stipend" };
  const NO_MEASURE = new Set(["rpc-rejected", "no-public-rpc", "synthetic-balance-rpc", "target-state-rpc-error"]);
  function gasKind(c, isRef) {
    if (!c) return "none";
    if (c.status === "execution-failure") return "failed";
    if (NO_MEASURE.has(c.status) || c.val == null) return "none";
    if (c.ratio == null) return "control";
    if (isRef) return "baseline";
    return c.ratio === 1 ? "same" : c.ratio < 1 ? "cheaper" : "pricier";
  }
  function adaptGas(d, chains, mcells) {
    const gs = d.gas_schedule; if (!gs) return null;
    const ref = "ethereum";
    const items = gs.items.map((i) => ({ id: i.id, name: i.name, short: i.name.replace(/ · operation$/, "").replace(" · ", " "), family: i.family, famLabel: GAS_FAMILY[i.family] || i.family, phase: i.phase, metric: i.metric, eth: i.ethereum_value }));
    const families = [...new Set(items.map((i) => i.family))].map((f) => ({ id: f, label: GAS_FAMILY[f] || f, n: items.filter((i) => i.family === f).length }));
    const cells = {};
    gs.cells.forEach((c) => {
      const x = { chain: c.chain, item: c.item, eth: c.ethereum_value, val: c.chain_value, ratio: c.ratio == null ? null : Number(c.ratio), ratioText: c.ratio, status: c.status, metric: c.metric, evidence: c.evidence || [] };
      const mc = mcells[c.chain]?.[c.item]?.v;
      if (mc && typeof mc === "object") { x.note = mc.note || null; x.block = mc.block_tag || mcells[c.chain][c.item].block || null; x.confirm = mc.confirmation_gas ?? null; x.second = mc.second_endpoint_gas ?? null; }
      x.kind = gasKind(x, c.chain === ref);
      (cells[c.chain] = cells[c.chain] || {})[c.item] = x;
    });
    const stat = {};
    gs.chain_ids.forEach((id) => { const row = Object.values(cells[id] || {}); stat[id] = { diff: row.filter((x) => x.kind === "cheaper" || x.kind === "pricier").length, measured: row.filter((x) => x.kind !== "none").length }; });
    const order = gs.chain_ids.slice().sort((a, b) => (a === ref ? -1 : b === ref ? 1 : 0) || (stat[b].measured > 0) - (stat[a].measured > 0) || stat[b].diff - stat[a].diff);
    const gchains = order.map((id) => chains.find((c) => c.id === id) || { id, name: id });
    const diffs = Object.values(cells).flatMap((r) => Object.values(r)).filter((x) => x.kind === "cheaper" || x.kind === "pricier");
    const hi = diffs.reduce((a, x) => (!a || x.ratio > a.ratio ? x : a), null), lo = diffs.reduce((a, x) => (!a || x.ratio < a.ratio ? x : a), null);
    const lowNZ = diffs.filter((x) => x.ratio > 0).reduce((a, x) => (!a || x.ratio < a.ratio ? x : a), null);
    // Coverage: chains that matched on every item they could price, those among them with gaps, and those never measured.
    const matching = order.filter((id) => id !== ref && stat[id].measured > 0 && stat[id].diff === 0);
    const partial = matching.filter((id) => Object.values(cells[id] || {}).some((x) => x.kind === "none" || x.kind === "failed"));
    const unmeasured = order.filter((id) => id !== ref && stat[id].measured === 0);
    // The lowest price: is the same operation also zero on repeat (warm) access?
    const loWarm = lo && lo.ratio === 0 && /\/cold$/.test(lo.item) ? cells[lo.chain]?.[lo.item.replace(/\/cold$/, "/warm")] : null;
    return { date: gs.date, items, families, cells, chains: gchains, stat, matching, partial, unmeasured, loWarmZero: !!(loWarm && loWarm.ratio === 0), diffCount: diffs.length, diffChains: order.filter((id) => stat[id].diff > 0).length, diffItems: new Set(diffs.map((x) => x.item)).size, hi, lo, lowNZ };
  }

  // Second sweep (docs/new-findings.md order). Values come from the gas grid or matrix cells;
  // behaviour and consequence text come from the matching catalog row.
  const SWEEP = [
    { id: "tempo-create", kind: "gas", chain: "tempo", item: "gas/create-0-bytes/operation", card: true },
    { id: "somnia-sstore", kind: "gas", chain: "somnia", item: "gas/sstore-transitions/zero-to-one", card: true },
    { id: "bls-valid", kind: "see", chain: "avalanche-c-chain", probe: "precompile-vector/0x0b/valid", see: "bls", match: /G1ADD/ },
    { id: "somnia-runtime", kind: "life", chain: "somnia", probe: "lifecycle/runtime-24577", match: /runtime bytes/ },
    { id: "monad-init", kind: "life", chain: "monad", probe: "lifecycle/init-49153", match: /init code/ },
    { id: "zksync-selfdestruct", kind: "life", chain: "zksync-era", probe: "lifecycle/selfdestruct-funded", match: /SELFDESTRUCT/, card: true },
    { id: "kaia-value", kind: "life", chain: "kaia", probe: "lifecycle/precompile-value", match: /identity-precompile/ },
    { id: "monad-memory", kind: "gas", chain: "monad", item: "gas/memory-expand-32768-words/operation", card: true },
    { id: "megaeth-log", kind: "gas", chain: "megaeth", item: "gas/log4-256-bytes/operation", card: true },
    { id: "sei-sstore", kind: "gas", chain: "sei-evm", item: "gas/sstore-transitions/zero-to-one" },
  ];
  function adaptSweep(d, gas, cells, catalog) {
    const ref = "ethereum";
    return SWEEP.map((s) => {
      const probe = s.item || s.probe;
      const key = s.item ? s.item.split("/").slice(1).join("/") : null; // "create-0-bytes/operation"
      const row = catalog.find((r) => r.chain === s.chain && r.evidence.some((e) => e.path.includes(s.kind === "gas" ? "/gas-schedule/" : s.kind === "life" ? "/lifecycle/" : "/precompile-sweep/")) &&
        (key ? r.title.startsWith(`${key.split("/")[0]} (${key.split("/")[1]})`) : s.match.test(r.title)));
      const tc = cells[s.chain]?.[probe], ec = cells[ref]?.[probe];
      const others = Object.keys(cells).filter((c) => c !== s.chain && c !== ref && cells[c][probe] && ATTENTION.has(cells[c][probe].class));
      const out = { ...s, probe, row: row || null, tgt: tc ? tc.v : null, eth: ec ? ec.v : null, others, evidence: row ? row.evidence : (tc ? tc.evidence.map((p) => ({ label: p.replace(/^results\/[^/]+\//, ""), path: p })) : []) };
      if (s.kind === "gas" && gas) out.g = gas.cells[s.chain]?.[s.item] || null;
      return out;
    });
  }
  // Numbers quoted inside catalog text (e.g. a documented limit) are read from that text, never typed here.
  const grab = (txt, re) => { const m = String(txt || "").match(re); return m ? m[1] : null; };

  function parseLines(txt, chains) {
    // "Chain block 0x..: rest" blocks, continuation lines indented.
    const out = []; let cur = null;
    txt.split("\n").forEach((ln) => {
      const m = ln.match(/^(\S.*?) block(?: tag)? (0x[0-9a-f]+):\s*(.*)$/i);
      if (m) {
        const c = chains.find((x) => x.name.toLowerCase() === m[1].toLowerCase()) || chains.find((x) => x.name.toLowerCase().startsWith(m[1].toLowerCase()));
        cur = { chain: c ? c.id : m[1], block: m[2], text: m[3].trim() }; out.push(cur);
      } else if (cur && ln.trim()) cur.text += (cur.text && !cur.text.endsWith(",") && !cur.text.endsWith("->") ? "  " : " ") + ln.trim();
    });
    return out;
  }
  const EXAMPLE = { chain: "zksync-era", probe: "prevrandao" }; // the probe walked through in "How a probe works"
  function hostLabel(h) {
    if (!h) return null;
    if (h.operator === "third-party") return `${h.host} (${h.provider ? h.provider + ", " : ""}third-party)`;
    if (h.operator === "chain") return `${h.host} (chain-operated)`;
    return h.host;
  }
  // Values are decimal strings for EVM numbers; arrays print without quotes.
  function show(x) {
    if (Array.isArray(x)) return "[" + x.map(show).join(", ") + "]";
    if (x && typeof x === "object") return JSON.stringify(x);
    return String(x);
  }
  const SUM_KEYS = ["reason", "uint256", "header_value", "header_matches", "precompile_call_status", "precompile_output_words", "gas_delta", "warm_gas_delta", "formula_matches", "matches_expected_zero", "code_size", "status"];
  function summarize(v) {
    if (v == null) return null;
    if (typeof v !== "object") return String(v);
    if (v.reason) return String(v.reason);
    if ("metric" in v) {
      if (v.gas == null) return `status=${v.status}`;
      if (v.status === "unfunded-control-only") return `unfunded control only · ${v.metric}=${v.gas} gas · no successful value-transfer price measured`;
      return `${v.metric}=${v.gas} gas · Ethereum=${v.ethereum_gas} · Δ=${v.delta_gas}`;
    }
    if ("first_call_gas" in v) {
      if (v.gas_scope === "cap-exhausted-not-price") return `status=${v.status} · forwarded-gas cap exhausted; no price measured`;
      if (v.gas_scope === "bounded-failure-not-price") return `status=${v.status} · CALL failed; no price measured`;
      return `status=${v.status} · output=${v.output ? (v.output.length - 2) / 2 + " bytes" : "none"} · cold/warm CALL-inclusive=${v.first_call_gas}/${v.second_call_gas} gas`;
    }
    if ("outcome" in v) return `status=${v.status} · ${Object.entries(v.outcome || {}).filter(([k]) => k !== "status").map(([k, x]) => `${k}=${show(x)}`).join(" · ")}`;
    const parts = [];
    if ("precompile_call_status" in v) parts.push(`status=${v.precompile_call_status}`, `words=${show(v.precompile_output_words)}`);
    else if ("gas_delta" in v) parts.push(`cold=${v.gas_delta}`, `warm=${v.warm_gas_delta}`);
    else if ("formula_matches" in v) parts.push(`formula_matches=${v.formula_matches}`);
    else {
      if ("uint256" in v && String(v.uint256).length <= 80) parts.push(`value=${v.uint256}`);
      if ("header_value" in v) parts.push(`header=${v.header_value}`);
      if ("header_matches" in v) parts.push(`match=${v.header_matches}`);
      if (!parts.length) SUM_KEYS.forEach((k) => { if (k in v && k !== "status" && String(v[k]).length < 80) parts.push(`${k}=${show(v[k])}`); });
      if (!parts.length && v.status) parts.push(`status=${v.status}`);
    }
    return parts.join("  ");
  }


  g.EVM = { loadData, show, adapt, CLASSES, CLASS_MAP, ATTENTION, COPY, SWEEP_COPY, summarize, esc, grab, GAS_FAMILY };
})(window);

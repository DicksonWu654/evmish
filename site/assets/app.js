/* EVMish site. Every number shown is read from data/data.json (or its
   bundled copy assets/data.js for file:// use). Copy lives here; data does not. */
(function () {
  "use strict";

  // Evidence paths in data.json are repo-relative ("results/2026-10-18/...").
  // Set the public repository URL here at deploy time.
  const REPO_BASE = "https://github.com/DicksonWu654/evmish/blob/main/";

  const $ = (s, r = document) => r.querySelector(s);
  const $$ = (s, r = document) => Array.from(r.querySelectorAll(s));
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const fmt = (n) => (typeof n === "number" ? n.toLocaleString("en-US") : /^\d+$/.test(String(n ?? "")) ? BigInt(n).toLocaleString("en-US") : String(n ?? ""));
  // Ratios to Ethereum, three significant figures: 15.625 -> "15.6", 0.0075 -> "134" (as 1/x).
  const ratioX = (r) => String(Number((r >= 1 ? r : 1 / r).toPrecision(3)));
  const evHref = (p) => (/^https?:/.test(p) ? p : REPO_BASE + String(p).replace(/^\.?\//, ""));
  const store = {
    get(k) { try { return localStorage.getItem(k); } catch (e) { return null; } },
    set(k, v) { try { localStorage.setItem(k, v); } catch (e) {} },
  };

  /* ------------------------------------------------------------------ theme */
  const themeBtn = $("#themeBtn");
  function currentTheme() {
    const t = document.documentElement.getAttribute("data-theme");
    if (t) return t;
    return matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
  }
  themeBtn.addEventListener("click", () => {
    const next = currentTheme() === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    store.set("evmish-theme", next);
    document.dispatchEvent(new Event("themechange"));
  });
  matchMedia("(prefers-color-scheme: dark)").addEventListener("change", () => document.dispatchEvent(new Event("themechange")));

  /* ------------------------------------------------------------------- data */
  /* ------------------------------------------------- shared model (assets/model.js) */
  const { CLASSES, ATTENTION, COPY, SWEEP_COPY, show } = window.EVM;
  const loadData = () => window.EVM.loadData("");
  const adapt = window.EVM.adapt;

  const LIMITS = [
    ["Sender aliasing", "L1 to L2 address aliasing appears only when a real cross-domain message is delivered."],
    ["Finality", "Finality windows and reorg depth need time and real blocks, not one simulated call."],
    ["Rebasing balances", "Native balances that rebase (Blast) change between blocks and need a funded account to watch."],
    ["Fee tokens", "Paying fees in another token (Celo, Tempo) only happens inside a signed transaction."],
    ["Code-size limits", "Exact deploy limits need a real deployment. An eth_call gas cap can hide the size rule."],
  ];

  const CREDITS = [
    ["mds1/evm-diff", "https://github.com/mds1/evm-diff/tree/6beeefe8a91484cf9e3c23d59b364ef3bba673b4"],
    ["shemnon/evm-directory", "https://github.com/shemnon/evm-directory/tree/f06b85450e87772221ff636aa3df29ae20f563b6"],
    ["Each chain's own documentation, linked per row in the catalog", null],
  ];

  /* --------------------------------------------------------------- helpers */
  let M; // normalized model
  function chainName(id) { const c = M.chainById[id]; return c ? c.name : id; }
  function listNames(ids) {
    const n = ids.map(chainName);
    if (n.length <= 1) return n.join("");
    if (n.length === 2) return `${n[0]} and ${n[1]}`;
    return `${n.slice(0, -1).join(", ")} and ${n[n.length - 1]}`;
  }
  function cell(chain, probe) { return (M.cells[chain] || {})[probe] || { class: "unavailable" }; }

  /* ------------------------------------------------------------- bindings */
  function bindStats() {
    const m = M.meta;
    const vals = {
      chains: fmt(m.chains), probes: fmt(m.probes), differences: fmt(m.differences), date: m.date,
      dateLong: m.dateLong || m.date,
      findingsRail: `${M.findings.length} of ${fmt(m.differences)}`,
      matrixRail: `${fmt(M.chains.length)} × ${fmt(M.probes.length)}`,
      gasRail: M.gas ? `${fmt(M.gas.chains.length)} × ${fmt(M.gas.items.length)}` : "",
      sweepRail: M.gas ? M.gas.date : "",
    };
    $$("[data-bind]").forEach((el) => { const k = el.dataset.bind; if (k in vals) el.textContent = vals[k]; });
    if (m.author) $("#authorSlot").textContent = m.author;
  }

  /* ---------------------------------------------------------- hero scope */
  function tokens() {
    const cs = getComputedStyle(document.documentElement);
    const g = (n) => cs.getPropertyValue(n).trim();
    return { same: g("--same"), diff: g("--diff"), fail: g("--fail"), rej: g("--rej"), ref: g("--ref"), rejSoft: g("--rej-soft"), rule: g("--rule"), ink: g("--ink"), muted: g("--muted"), sheet: g("--sheet") };
  }
  // prog in [0, 1]: a left-to-right probe sweep; differences land last, just behind the sweep line.
  function drawScope(prog = 1) {
    const cv = $("#scope"); if (!cv) return;
    const cols = M.chains, rows = M.probes;
    const W = cv.clientWidth || 560;
    const labelH = 0, pad = 2;
    const cw = Math.max(6, Math.floor((W - pad * 2) / cols.length));
    const ch = Math.max(2, Math.min(Math.round(cw * 0.62), Math.floor(Math.min(520, innerHeight * 0.62) / rows.length)));
    const thin = ch < 5;
    const H = rows.length * ch + labelH + pad * 2;
    const dpr = window.devicePixelRatio || 1;
    cv.width = Math.round(W * dpr); cv.height = Math.round(H * dpr); cv.style.height = H + "px";
    const x = cv.getContext("2d"); x.setTransform(dpr, 0, 0, dpr, 0, 0); x.clearRect(0, 0, W, H);
    const t = tokens();
    const ox = Math.floor((W - cw * cols.length) / 2);
    rows.forEach((p, ri) => cols.forEach((c, ci) => {
      const k = cell(c.id, p.id).class;
      const X = ox + ci * cw, Y = pad + labelH + ri * ch;
      const g = 1, gy = thin ? 0 : 1;
      const at = (ci + 0.5) / cols.length * 0.82 + (ri / rows.length) * 0.08 + (ATTENTION.has(k) ? 0.1 : 0);
      if (prog < 1 && at > prog) return;
      if (k === "differs" || k === "execution-failure") {
        x.fillStyle = k === "differs" ? t.diff : t.fail; x.fillRect(X + g, Y + gy, cw - 2 * g, ch - 2 * gy);
      } else if (k === "reference") {
        x.fillStyle = t.ref; x.globalAlpha = 0.85; x.fillRect(X + g, Y + gy, cw - 2 * g, ch - 2 * gy); x.globalAlpha = 1;
      } else if (k === "rpc-rejected") {
        if (thin) { x.fillStyle = t.rej; x.globalAlpha = 0.35; x.fillRect(X + g, Y, cw - 2 * g, ch); x.globalAlpha = 1; }
        else {
          x.strokeStyle = t.rej; x.lineWidth = 1; x.strokeRect(X + g + 0.5, Y + g + 0.5, cw - 2 * g - 1, ch - 2 * g - 1);
          x.beginPath(); x.moveTo(X + g, Y + ch - g); x.lineTo(X + cw - g, Y + g); x.stroke();
        }
      } else if (k === "unavailable") {
        if (!thin) { x.fillStyle = t.rejSoft; x.fillRect(X + cw / 2 - 1, Y + ch / 2 - 1, 2, 2); }
      } else if (k === "endpoint-artifact" || k === "state-only") {
        x.fillStyle = t.rejSoft; x.fillRect(X + g, Y + gy, cw - 2 * g, ch - 2 * gy);
      } else {
        x.fillStyle = t.same; x.fillRect(X + g + 1, Y + gy, cw - 2 * g - 2, ch - 2 * gy);
      }
    }));
    if (prog < 1) {
      const sx = ox + Math.min(1, prog / 0.9) * cw * cols.length;
      x.fillStyle = t.ref; x.globalAlpha = 0.9; x.fillRect(Math.round(sx), 0, 2, H); x.globalAlpha = 0.12; x.fillRect(Math.round(sx) - 18, 0, 18, H); x.globalAlpha = 1;
    }
    const nd = countAttention();
    $("#scopeCaption").textContent = `${fmt(cols.length)} chains × ${fmt(rows.length)} probe cases`;
    $("#scopeLegend").innerHTML = [
      ["reference", "Ethereum"], ["differs", "Differs"], ["execution-failure", "VM failure"], ["rpc-rejected", "RPC rejected"], ["same", "Same"],
    ].map(([k, l]) => `<span class="chip"><span class="sw ${k}"></span>${l}</span>`).join("") +
      `<span class="chip muted">${fmt(nd)} differing cells</span>`;
    cv.onclick = (e) => {
      const r = cv.getBoundingClientRect();
      const ci = Math.floor((e.clientX - r.left - ox) / cw), ri = Math.floor((e.clientY - r.top - pad) / ch);
      if (cols[ci] && rows[ri]) { if (!visibleProbes().some((p) => p.id === rows[ri].id)) { mx.cat = ""; $("#mxCat").value = ""; renderMatrix(); } pick(cols[ci].id, rows[ri].id, true); }
      $("#matrix").scrollIntoView();
    };
  }
  function revealScope() {
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduce) return drawScope(1);
    const T = 1500, t0 = performance.now();
    const step = (now) => {
      const p = Math.min(1, (now - t0) / T);
      drawScope(1 - Math.pow(1 - p, 2.2));
      if (p < 1) requestAnimationFrame(step);
    };
    requestAnimationFrame(step);
  }
  function countAttention() {
    let n = 0;
    M.chains.forEach((c) => M.probes.forEach((p) => { if (ATTENTION.has(cell(c.id, p.id).class)) n++; }));
    return n;
  }

  /* ------------------------------------------------------- probe machine */
  const OPS = { 0x00: "STOP", 0x01: "ADD", 0x02: "MUL", 0x03: "SUB", 0x04: "DIV", 0x10: "LT", 0x11: "GT", 0x14: "EQ", 0x15: "ISZERO", 0x16: "AND", 0x17: "OR", 0x19: "NOT", 0x1b: "SHL", 0x1c: "SHR", 0x20: "KECCAK256", 0x30: "ADDRESS", 0x31: "BALANCE", 0x32: "ORIGIN", 0x33: "CALLER", 0x34: "CALLVALUE", 0x35: "CALLDATALOAD", 0x36: "CALLDATASIZE", 0x38: "CODESIZE", 0x39: "CODECOPY", 0x3a: "GASPRICE", 0x3b: "EXTCODESIZE", 0x3c: "EXTCODECOPY", 0x3d: "RETURNDATASIZE", 0x3e: "RETURNDATACOPY", 0x3f: "EXTCODEHASH", 0x40: "BLOCKHASH", 0x41: "COINBASE", 0x42: "TIMESTAMP", 0x43: "NUMBER", 0x44: "PREVRANDAO", 0x45: "GASLIMIT", 0x46: "CHAINID", 0x47: "SELFBALANCE", 0x48: "BASEFEE", 0x49: "BLOBHASH", 0x4a: "BLOBBASEFEE", 0x50: "POP", 0x51: "MLOAD", 0x52: "MSTORE", 0x53: "MSTORE8", 0x54: "SLOAD", 0x55: "SSTORE", 0x56: "JUMP", 0x57: "JUMPI", 0x5a: "GAS", 0x5b: "JUMPDEST", 0x5c: "TLOAD", 0x5d: "TSTORE", 0x5e: "MCOPY", 0x5f: "PUSH0", 0xf0: "CREATE", 0xf1: "CALL", 0xf3: "RETURN", 0xf4: "DELEGATECALL", 0xf5: "CREATE2", 0xfa: "STATICCALL", 0xfd: "REVERT", 0xfe: "INVALID" };
  const OP_NOTE = { PREVRANDAO: "read block randomness", NUMBER: "read block number", PUSH1: "push constant", MSTORE: "write word to memory", RETURN: "hand memory back", BASEFEE: "read base fee", CHAINID: "read chain id" };
  function disasm(hex) {
    const b = hex.replace(/^0x/, "").match(/../g).map((h) => parseInt(h, 16));
    const out = [];
    for (let i = 0; i < b.length; i++) {
      const o = b[i];
      if (o >= 0x60 && o <= 0x7f) {
        const n = o - 0x5f; const arg = b.slice(i + 1, i + 1 + n).map((v) => v.toString(16).padStart(2, "0")).join("");
        out.push({ op: "PUSH" + n, arg: "0x" + arg, byte: o }); i += n;
      } else if (o >= 0x80 && o <= 0x8f) out.push({ op: "DUP" + (o - 0x7f), byte: o });
      else if (o >= 0x90 && o <= 0x9f) out.push({ op: "SWAP" + (o - 0x8f), byte: o });
      else out.push({ op: OPS[o] || "0x" + o.toString(16), byte: o });
    }
    return out;
  }
  const big = (hex) => { try { return BigInt(hex).toString(); } catch (e) { return hex; } };

  function buildProbe() {
    const ex = M.example; // {chain, probe, initCode, block, rawReturn, value}
    const ops = disasm(ex.initCode);
    const steps = [
      ["Write init code", `A few bytes of EVM code. This one is the <code>${esc(ex.probe)}</code> probe: read the value, store it in memory, return it.`],
      ["Call with no to", "Send it as the <code>data</code> of an <code>eth_call</code> and leave out <code>to</code>. The node treats it as contract creation."],
      ["The chain runs it", "The target chain executes the init code at the requested block, with its own opcodes, precompiles and gas rules."],
      ["Read the answer", "Whatever the code returned comes back as the call result, with the endpoint, block and raw bytes recorded."],
      ["Nothing is written", "No transaction, no signature, no deploy. The chain state is unchanged, so anyone can run it against a public RPC."],
    ];
    const ol = $("#steps");
    ol.innerHTML = steps.map(([t, d], i) => `<li><button role="tab" type="button" id="step${i}" aria-selected="${i === 0}" aria-controls="machine"><span><span class="t">${t}</span><span class="d">${d}</span></span></button></li>`).join("");
    const req = { jsonrpc: "2.0", method: "eth_call", params: [{ data: ex.initCode }, ex.block] };
    const value = big(ex.rawReturn);
    $("#machine").innerHTML = `
      <div class="mhead"><span>${esc(chainName(ex.chain))} · block ${esc(ex.block)}</span><span>${esc(M.meta.date)}</span></div>
      <div class="lane">
        <div class="panel" data-p="0"><div class="ph"><span>init code</span><span>${(ex.initCode.length - 2) / 2} bytes</span></div>
          <pre><span class="k-num">${esc(ex.initCode)}</span></pre></div>
        <div class="panel" data-p="1"><div class="ph"><span>json-rpc request</span><span>no "to"</span></div>
          <pre>{ <span class="k-key">"method"</span>: <span class="k-str">"eth_call"</span>,
  <span class="k-key">"params"</span>: [{ <span class="k-key">"data"</span>: <span class="k-str">"${esc(ex.initCode)}"</span> },
             <span class="k-str">"${esc(ex.block)}"</span>] }</pre></div>
        <div class="panel" data-p="2"><div class="ph"><span>execution as a deploy</span><span id="execTrace">stack: []</span></div>
          <div class="ops" id="ops">${ops.map((o, i) => `<span class="op" data-i="${i}"><b>${o.op}${o.arg ? " " + o.arg : ""}</b><i>${esc(OP_NOTE[o.op] || "")}</i></span>`).join("")}</div></div>
        <div class="panel" data-p="3"><div class="ph"><span>result</span><span>uint256</span></div>
          <pre><span class="k-dim">${esc(ex.rawReturn)}</span>
<span class="k-ok">= ${esc(value)}</span></pre></div>
        <div class="panel" data-p="4"><div class="ph"><span>chain state</span><span>unchanged</span></div>
          <div class="chainstate"><span class="blocks" aria-hidden="true"><span></span><span></span><span></span><span></span></span><span>no transaction · no signature · no deploy</span></div></div>
      </div>`;
    void req;
    let cur = 0, timer = null, opTimer = null, user = false;
    const reduce = matchMedia("(prefers-reduced-motion: reduce)").matches;
    function show(i) {
      cur = i;
      $$("#steps button").forEach((b, j) => b.setAttribute("aria-selected", String(j === i)));
      $$("#machine .panel").forEach((p) => { const j = +p.dataset.p; p.classList.toggle("on", j === i); p.classList.toggle("dim", j > i); });
      clearInterval(opTimer);
      const opEls = $$("#ops .op");
      opEls.forEach((o) => o.classList.remove("hot"));
      if (i === 2) runOps(opEls); else $("#execTrace").textContent = i > 2 ? "returned 32 bytes" : "stack: []";
    }
    function runOps(opEls) {
      if (reduce) { opEls.forEach((o) => o.classList.add("hot")); $("#execTrace").textContent = "returned 32 bytes"; return; }
      let k = 0; const stack = [];
      const tick = () => {
        opEls.forEach((o, j) => o.classList.toggle("hot", j === k));
        const o = ops[k];
        if (/^PUSH/.test(o.op)) stack.push(String(parseInt(o.arg, 16)));
        else if (o.op === "MSTORE" || o.op === "RETURN") { stack.pop(); stack.pop(); }
        else stack.push(o.op === "PREVRANDAO" || o.byte >= 0x40 && o.byte <= 0x4a ? short(value) : "·");
        $("#execTrace").textContent = o.op === "RETURN" ? "returned 32 bytes" : "stack: [" + stack.slice().reverse().join(", ") + "]";
        k++; if (k >= ops.length) clearInterval(opTimer);
      };
      tick(); opTimer = setInterval(tick, 520);
    }
    const short = (s) => (s.length > 12 ? s.slice(0, 6) + "…" + s.slice(-4) : s);
    function auto() { if (user || reduce) return; timer = setTimeout(() => { show((cur + 1) % steps.length); auto(); }, cur === 2 ? 4200 : 3000); }
    ol.addEventListener("click", (e) => {
      const b = e.target.closest("button"); if (!b) return;
      user = true; clearTimeout(timer); show(+b.id.replace("step", ""));
    });
    ol.addEventListener("keydown", (e) => {
      if (!/Arrow(Up|Down)/.test(e.key)) return; e.preventDefault(); user = true; clearTimeout(timer);
      const n = (cur + (e.key === "ArrowDown" ? 1 : steps.length - 1)) % steps.length; show(n); $("#step" + n).focus();
    });
    show(0);
    // start autoplay when visible
    const io = new IntersectionObserver((en) => { if (en[0].isIntersecting) { auto(); io.disconnect(); } }, { threshold: 0.4 });
    io.observe($("#machine"));
  }

  /* ----------------------------------------------------------- findings */
  function outRows(lines) {
    return lines.map((l) => `<div class="row"><span class="who ${l.chain === "ethereum" ? "eth" : "tgt"}">${esc(chainName(l.chain))} ${esc(l.block || "")}</span><span class="val">${esc(l.text)}</span></div>`).join("");
  }
  function codeBlock(kind, src) {
    return `<div class="code ${kind}"><div class="ch"><span>${kind === "unsafe" ? "Unsafe" : "Safer"}</span><span class="mono">.sol</span></div><pre><code>${window.solHighlight(src)}</code></pre></div>`;
  }
  function renderFindings() {
    $("#findingList").innerHTML = M.findings.map((f, i) => {
      const c = COPY[f.id] || {};
      return `<article class="finding" id="finding-${esc(f.id)}">
        <div class="f-main">
          <div class="f-top"><span class="f-num">${String(i + 1).padStart(2, "0")} / ${String(M.findings.length).padStart(2, "0")}</span><span class="label">${esc(f.category || "")}</span></div>
          <h3>${esc(c.title ? c.title(f, listNames) : f.title)}</h3>
          <div class="assume"><span class="label">The assumption</span><p>${esc(c.assume || f.assumption || "")}</p></div>
          <div><span class="label">Probe output</span><div class="out" style="margin-top:8px">${outRows(f.lines)}</div></div>
          <div><span class="label">Chains affected</span><div class="chains" style="margin-top:8px">${f.chains.map((id) => `<a class="cpill" href="#chains" data-chain="${esc(id)}">${esc(chainName(id))}</a>`).join("")}</div></div>
          ${f.failClosed && f.failClosed.length ? `<div class="closed"><span class="label">Fails closed instead</span><div class="chains" style="margin-top:8px">${f.failClosed.map((id) => `<a class="cpill quiet" href="#chains" data-chain="${esc(id)}">${esc(chainName(id))}</a>`).join("")}</div>
            <p>${f.failClosed.map((id) => { const r = M.catalog.find((x) => x.chain === id && /G1ADD/.test(x.title)); const c = cell(id, f.probes[0]); return `${esc(chainName(id))} returned <code>${esc(c.v && c.v.status)}</code> for the same vector. ${r ? esc(r.consequence) : ""}`; }).join(" ")}</p></div>` : ""}
        </div>
        <div class="f-side">
          <div class="why"><span class="label">Why it breaks contracts</span><p>${esc(c.why || f.why || "")}</p></div>
          ${codeBlock("unsafe", f.unsafe || c.unsafe || "")}
          ${codeBlock("safe", c.safe || f.safe || "")}
          <div><span class="label">Evidence</span><div class="ev" style="margin-top:6px">${f.evidence.map((e) => `<a href="${esc(evHref(e.path))}">${esc(e.label)}</a>`).join("")}</div></div>
        </div>
      </article>`;
    }).join("") + (M.staleNote ? staleNote() : "");
    $$("#findingList .cpill").forEach((a) => a.addEventListener("click", () => selectChain(a.dataset.chain)));
  }
  function staleNote() {
    const s = M.staleNote;
    return `<aside class="finding stale"><div class="f-main">
      <div class="f-top"><span class="label">Docs are stale</span><span class="label mono">${esc(s.probe)}</span></div>
      <h3 style="font-size:1.35rem">CREATE2 on ${esc(chainName(s.chain))} matches Ethereum for EVM bytecode</h3>
      <p style="max-width:70ch">The usual checklist line says zkSync's CREATE2 addresses differ from Ethereum's. For EVM bytecode the probe got the Ethereum formula, the same result as on Ethereum and Arbitrum. The different formula applies to EraVM-native contracts. Keep the check, aimed at the right kind of contract.</p>
      <div class="out">${outRows(s.lines)}</div>
      <div class="ev">${s.evidence.map((e) => `<a href="${esc(evHref(e.path))}">${esc(e.label)}</a>`).join("")}</div>
    </div></aside>`;
  }

  /* -------------------------------------------------------------- matrix */
  const CORE = "__core"; // every category except the gas schedule, which has its own heatmap
  const mx = { cat: CORE, chain: "", hl: true, only: false, picked: null };
  function visibleChains() {
    let cs = M.chains;
    if (mx.chain) cs = cs.filter((c) => c.id === mx.chain || c.id === M.refChain);
    if (mx.only) cs = cs.filter((c) => c.id === M.refChain || visibleProbes(true).some((p) => ATTENTION.has(cell(c.id, p.id).class)));
    return cs;
  }
  function visibleProbes(ignoreOnly) {
    let ps = M.probes;
    if (mx.cat === CORE) ps = ps.filter((p) => p.category !== "Gas schedule");
    else if (mx.cat) ps = ps.filter((p) => p.category === mx.cat);
    if (mx.only && !ignoreOnly) {
      const cs = mx.chain ? [mx.chain] : M.chains.map((c) => c.id);
      ps = ps.filter((p) => cs.some((c) => ATTENTION.has(cell(c, p.id).class)));
    }
    return ps;
  }
  function renderMatrix() {
    const cs = visibleChains(), ps = visibleProbes();
    const t = $("#mxTable");
    t.classList.toggle("hl", mx.hl);
    let h = `<thead><tr><th class="corner"><span class="label">Probe \\ chain</span></th>${cs.map((c) => `<th class="colh${c.id === M.refChain ? " eth" : ""}${c.id === mx.chain ? " sel" : ""}" scope="col"><span data-chain="${esc(c.id)}"${c.note ? ` title="${esc(c.note)}"` : ""}>${esc(c.name)}</span></th>`).join("")}</tr></thead><tbody>`;
    let lastCat = null;
    ps.forEach((p) => {
      if (p.category !== lastCat) { lastCat = p.category; h += `<tr class="cat"><th colspan="1">${esc(p.category)}</th><td colspan="${cs.length}"></td></tr>`; }
      h += `<tr><th scope="row" title="${esc(p.meaning)}">${esc(p.label || p.id)}</th>`;
      cs.forEach((c) => {
        const k = cell(c.id, p.id).class;
        const picked = mx.picked && mx.picked[0] === c.id && mx.picked[1] === p.id;
        h += `<td class="c ${k}${c.id === M.refChain ? " col-eth" : ""}${picked ? " picked" : ""}"><button type="button" data-c="${esc(c.id)}" data-p="${esc(p.id)}" aria-label="${esc(c.name)}, ${esc(p.id)}: ${esc(CLASSES[k] ? CLASSES[k].short : k)}"></button></td>`;
      });
      h += "</tr>";
    });
    t.innerHTML = h + "</tbody>";
    let n = 0; cs.forEach((c) => ps.forEach((p) => { if (ATTENTION.has(cell(c.id, p.id).class)) n++; }));
    $("#mxCount").textContent = `${fmt(cs.length)} chains × ${fmt(ps.length)} probes · ${fmt(n)} differing cells`;
  }
  function fieldsHtml(v) {
    if (v == null) return "no result";
    if (typeof v !== "object") return esc(v);
    return Object.entries(v).filter(([k, x]) => x !== null && k !== "precompile_output_hex" && k !== "formula_nonce_candidates").sort((a, b) => (a[0] === "raw_return") - (b[0] === "raw_return"))
      .map(([k, x]) => { let t = show(x); if (t.length > 160) t = t.slice(0, 80) + "…" + t.slice(-24); return `<span class="muted">${esc(k)}</span> ${esc(t)}`; }).join("<br>");
  }
  function inspect(cid, pid) {
    const c = cell(cid, pid), e = cell(M.refChain, pid), p = M.probeById[pid], ch = M.chainById[cid];
    const k = c.class, info = CLASSES[k] || { name: k, text: "" };
    const ic = p.initCode;
    $("#inspector").innerHTML = `
      <div><span class="label">${esc(p.category)}</span><h4>${esc(ch.name)} · <span class="mono" style="font-weight:600">${esc(pid)}</span></h4>
      <div class="sub">${esc(p.name || "")}</div><p style="font-size:.95rem;margin-top:6px">${esc(p.meaning || "")}</p></div>
      <div class="cls"><span class="sw ${k}"></span>${esc(c.rawClass && c.rawClass !== k && k !== "reference" ? c.rawClass : info.name)}</div>
      <p style="font-size:.92rem;color:var(--ink-2)">${esc(info.text)}</p>
      ${k === "unavailable" && ch.note ? `<p style="font-size:.92rem"><b>${esc(ch.name)}:</b> ${esc(ch.note)}</p>` : ""}
      <div class="kv">
        <div><span class="label">${esc(ch.name)} returned</span><div class="v tgt">${fieldsHtml(c.v)}</div></div>
        ${cid !== M.refChain ? `<div><span class="label">Ethereum returned</span><div class="v eth">${fieldsHtml(e.v)}</div></div>` : ""}
        ${ic ? `<div><span class="label">Init code · ${fmt((ic.length - 2) / 2)} bytes</span><div class="v">${esc(ic.length > 132 ? ic.slice(0, 130) + "…" : ic)}</div></div>` : ""}
        <div><span class="label">Evidence${c.sampleDate ? " · " + esc(c.sampleDate) : ""}${c.block ? " · block " + esc(c.block) : ""}</span>${(c.evidence || []).map((x) => `<a class="path" href="${esc(evHref(x))}">${esc(x)}</a>`).join("<br>") || '<span class="muted">none recorded</span>'}</div>
      </div>`;
  }
  function pick(cid, pid, scrollTo) {
    mx.picked = [cid, pid];
    $$("#mxTable td.picked").forEach((td) => td.classList.remove("picked"));
    const b = $(`#mxTable button[data-c="${CSS.escape(cid)}"][data-p="${CSS.escape(pid)}"]`);
    if (b) { b.parentElement.classList.add("picked"); if (scrollTo) b.scrollIntoView({ block: "nearest", inline: "center" }); }
    inspect(cid, pid);
  }
  function initMatrix() {
    $("#mxCat").insertAdjacentHTML("beforeend", M.categories.map((c) => `<option value="${esc(c)}">${esc(c)}${c === "Gas schedule" ? " (also the heatmap below)" : ""}</option>`).join(""));
    $("#mxChain").insertAdjacentHTML("beforeend", M.chains.filter((c) => c.id !== M.refChain).map((c) => `<option value="${esc(c.id)}">${esc(c.name)}</option>`).join(""));
    $("#mxCat").addEventListener("change", (e) => { mx.cat = e.target.value; renderMatrix(); });
    $("#mxChain").addEventListener("change", (e) => { mx.chain = e.target.value; renderMatrix(); });
    $("#mxHl").addEventListener("change", (e) => { mx.hl = e.target.checked; renderMatrix(); });
    $("#mxOnly").addEventListener("change", (e) => { mx.only = e.target.checked; renderMatrix(); });
    $("#mxTable").addEventListener("click", (e) => {
      const b = e.target.closest("button[data-c]");
      if (b) return pick(b.dataset.c, b.dataset.p);
      const s = e.target.closest("span[data-chain]");
      if (s && s.dataset.chain !== M.refChain) { mx.chain = mx.chain === s.dataset.chain ? "" : s.dataset.chain; $("#mxChain").value = mx.chain; renderMatrix(); }
    });
    $("#mxLegend").innerHTML = ["differs", "execution-failure", "rpc-rejected", "same", "reference", "endpoint-artifact", "state-only", "unavailable"]
      .map((k) => `<div class="lg"><span class="sw ${k}"></span><span><b>${CLASSES[k].name}</b>${esc(CLASSES[k].text)}</span></div>`).join("");
    renderMatrix();
    const first = M.findings[0];
    if (first) pick(first.chains[0], first.probes[0]);
    $("#mxScroll").scrollTop = 0;
  }


  /* -------------------------------------------------------- second sweep */
  const hctx = () => ({ F: fmt, name: chainName, grab: window.EVM.grab });
  function sweepCompare(x) {
    if (x.kind === "gas" && x.g && x.g.val != null) {
      const t = Number(x.g.val), e = Number(x.g.eth), top = Math.max(t, e);
      const w = (v) => Math.max(0.8, (v / top) * 100).toFixed(2) + "%";
      const r = x.g.ratio;
      const rel = r === 1 ? "same as Ethereum" : r > 1 ? `${ratioX(r)}× Ethereum` : `1/${ratioX(r)} of Ethereum's cost`;
      return `<div class="bars" role="img" aria-label="${esc(chainName(x.chain))} ${esc(fmt(x.g.val))} gas, Ethereum ${esc(fmt(x.g.eth))} gas">
        <div class="bar t"><span class="bn">${esc(chainName(x.chain))}</span><span class="bt"><i style="width:${w(t)}"></i></span><span class="bv">${esc(fmt(x.g.val))}</span></div>
        <div class="bar e"><span class="bn">Ethereum</span><span class="bt"><i style="width:${w(e)}"></i></span><span class="bv">${esc(fmt(x.g.eth))}</span></div>
        <div class="ratio ${r > 1 ? "up" : "down"}">${esc(rel)} <span class="muted">· gas used by the operation</span></div></div>`;
    }
    if (x.kind === "life" && x.tgt && x.eth) {
      const a = x.tgt.outcome || {}, b = x.eth.outcome || {};
      const keys = [...new Set([...Object.keys(a), ...Object.keys(b)])];
      const val = (o, k) => (k in o ? show(o[k]) : "not returned");
      return `<table class="cmp"><thead><tr><th scope="col">Returned state</th><th scope="col">${esc(chainName(x.chain))}</th><th scope="col">Ethereum</th></tr></thead><tbody>${keys.map((k) => {
        const p = val(a, k), q = val(b, k);
        return `<tr${p !== q ? ' class="d"' : ""}><th scope="row">${esc(k)}</th><td>${esc(p)}</td><td>${esc(q)}</td></tr>`; }).join("")}</tbody></table>`;
    }
    return "";
  }
  function renderSweep() {
    const box = $("#sweepList"); if (!box || !M.sweep) return;
    const h = hctx();
    const nVec = M.probes.filter((p) => p.category === "Precompile vectors").length, nLife = M.probes.filter((p) => p.category === "Lifecycle").length;
    $("#sweepLede").textContent = `On ${M.gas ? M.gas.date : M.meta.date} a second pass priced ${fmt(M.gas ? M.gas.items.length : 0)} operations, sent ${fmt(nVec)} pinned precompile inputs with known answers, and pushed ${fmt(nLife)} creation and call limits. These ${fmt(M.sweep.length)} results come first in review order. Each is a read-only eth_call, re-run at a later block, with a second endpoint where one was listed.`;
    box.innerHTML = M.sweep.map((x, i) => {
      const c = SWEEP_COPY[x.id] || {};
      const num = String(i + 1).padStart(2, "0");
      let title = ""; try { title = c.title(x, h); } catch (e) { title = x.id; }
      if (x.kind === "see") {
        const f = M.findings.find((y) => y.id === x.see); const fi = M.findings.indexOf(f) + 1;
        return `<li class="sx see"><div class="sw-n"><span class="mono">${num}</span><span class="label">${esc(c.family || "")}</span></div>
          <div class="sw-body"><h3>${esc(title)}</h3><p class="sw-scope">${f ? `On ${esc(listNames(f.chains))}. ` : ""}${esc(c.scope || "")}</p>
          <p><a href="#finding-${esc(x.see)}">Read finding ${String(fi).padStart(2, "0")}</a></p></div></li>`;
      }
      const row = x.row;
      return `<li class="sx${x.card ? " feat" : ""}" id="sweep-${esc(x.id)}">
        <div class="sw-n"><span class="mono">${num}</span><span class="label">${esc(c.family || "")}</span></div>
        <div class="sw-body">
          <h3>${esc(title)}</h3>
          ${sweepCompare(x)}
          ${x.others.length ? `<p class="sw-also">The same probe also differs on ${x.others.map((id) => `<a class="cpill" href="#chains" data-chain="${esc(id)}">${esc(chainName(id))}</a>`).join(" ")}</p>` : ""}
        </div>
        <div class="sw-side">
          ${row ? `<div><span class="label">Why it matters</span><p>${esc(row.consequence)}</p></div>` : ""}
          <div><span class="label">Scope</span><p class="sw-scope">${esc(c.scope || "")}</p></div>
          ${row ? `<div><span class="label">Catalog #${esc(row.n)}</span><p class="sw-rec">${esc(row.title)}</p></div>` : ""}
          <div class="ev">${x.evidence.map((e) => `<a href="${esc(evHref(e.path))}">${esc(e.label)}</a>`).join("")}</div>
        </div></li>`;
    }).join("");
    $$("#sweepList .cpill").forEach((a) => a.addEventListener("click", () => selectChain(a.dataset.chain)));
  }

  /* ---------------------------------------------------------- gas heatmap */
  const gx = { fam: "", only: true, picked: null };
  const SCALE = 6; // colour ramp spans 2^-6 .. 2^6 times Ethereum; beyond that it saturates
  const GAS_STATUS = {
    "ethereum-baseline": "Ethereum's measured cost. Every other cell in this column is divided by it.",
    "same-as-ethereum": "The same gas as Ethereum.",
    "confirmed-two-endpoints": "Differs from Ethereum. A later block and a second endpoint returned the same value.",
    "unfunded-control-only": "Control only. The call sent value from an unfunded account, so it is not the price of a successful value transfer. Left out of the colour scale.",
    "execution-failure": "The VM failed on this operation, so there is no price to compare.",
    "rpc-rejected": "The endpoint refused the request before any code ran.",
    "no-public-rpc": "No public RPC endpoint answered for this chain.",
    "synthetic-balance-rpc": "The endpoint reports a synthetic native balance and refused the funded value call, so no price was recorded.",
    "target-state-rpc-error": "The endpoint failed while reading the target account state, so no price was recorded.",
  };
  const GAS_KIND = { pricier: "Pricier than Ethereum", cheaper: "Cheaper than Ethereum", same: "Same as Ethereum", baseline: "Ethereum baseline", control: "Not a price", failed: "VM failure", none: "Not measured" };
  const gcell = (c, i) => (M.gas.cells[c] || {})[i] || { kind: "none", status: "no-public-rpc", evidence: [] };
  function heatBg(x) {
    if (x.kind !== "cheaper" && x.kind !== "pricier") return "";
    const t = x.ratio <= 0 ? 1 : Math.min(1, Math.abs(Math.log2(x.ratio)) / SCALE);
    const p = 0.14 + 0.86 * Math.pow(t, 0.85);
    const [a, b] = x.kind === "pricier" ? ["--hw1", "--hw2"] : ["--hc1", "--hc2"];
    return p < 0.5 ? `background:color-mix(in oklab, var(${a}) ${(p / 0.5 * 100).toFixed(1)}%, var(--h0))` : `background:color-mix(in oklab, var(${b}) ${((p - 0.5) / 0.5 * 100).toFixed(1)}%, var(${a}))`;
  }
  function gasItems() {
    let it = M.gas.items;
    if (gx.fam) it = it.filter((i) => i.family === gx.fam);
    if (gx.only) it = it.filter((i) => M.gas.chains.some((c) => /cheaper|pricier/.test(gcell(c.id, i.id).kind)));
    return it;
  }
  function renderGas() {
    const G = M.gas, items = gasItems(), chains = G.chains;
    const bands = []; items.forEach((i) => { const l = bands[bands.length - 1]; if (l && l.f === i.family) l.n++; else bands.push({ f: i.family, label: i.famLabel, n: 1 }); });
    let h = `<thead><tr class="fam"><th class="corner" rowspan="2"><span class="label">Chain</span><span class="label">differs</span></th>${bands.map((b) => `<th colspan="${b.n}" scope="colgroup" title="${esc(b.label)}"><span>${esc(b.label)}</span></th>`).join("")}</tr>
      <tr class="items">${items.map((i, j) => `<th scope="col" class="${j && items[j - 1].family !== i.family ? "fs" : ""}" title="${esc(i.name)}"><span>${esc(i.short)}</span></th>`).join("")}</tr></thead><tbody>`;
    chains.forEach((c) => {
      const st = G.stat[c.id], isRef = c.id === M.refChain;
      h += `<tr${isRef ? ' class="eth"' : ""}><th scope="row"><span class="rh"><span class="cn">${esc(c.name)}</span>${isRef ? '<span class="n ref">base</span>' : st.measured ? `<span class="n${st.diff ? "" : " z"}">${fmt(st.diff)}</span>` : '<span class="n z">none</span>'}</span></th>`;
      items.forEach((i, j) => {
        const x = gcell(c.id, i.id);
        const pk = gx.picked && gx.picked[0] === c.id && gx.picked[1] === i.id;
        h += `<td class="${x.kind}${x.ratio === 0 ? " zero" : ""}${j && items[j - 1].family !== i.family ? " fs" : ""}${pk ? " picked" : ""}"><button type="button" data-c="${esc(c.id)}" data-i="${esc(i.id)}" style="${heatBg(x)}" aria-label="${esc(c.name)}, ${esc(i.name)}: ${esc(GAS_KIND[x.kind])}${x.ratio != null && !isRef ? ", " + esc(x.ratio === 0 ? "0 gas" : (x.ratio >= 1 ? ratioX(x.ratio) + " times" : "1/" + ratioX(x.ratio) + " of") + " Ethereum") : ""}"></button></td>`;
      });
      h += "</tr>";
    });
    $("#gasTable").innerHTML = h + "</tbody>";
    let n = 0; chains.forEach((c) => items.forEach((i) => { if (/cheaper|pricier/.test(gcell(c.id, i.id).kind)) n++; }));
    $("#gasCount").textContent = `${fmt(chains.length)} chains × ${fmt(items.length)} operations · ${fmt(n)} measured prices differ`;
    $$("#gasFam button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.f === gx.fam)));
  }
  function gasDetail(cid, iid) {
    const x = gcell(cid, iid), i = M.gas.items.find((y) => y.id === iid), isRef = cid === M.refChain;
    const metric = x.metric === "child_gasleft" ? "Gas left in the child, not a price. Left out of the colour scale." : null;
    const ratio = x.ratio == null ? "not compared" : x.ratio === 0 ? "0×" : x.ratio >= 1 ? `${ratioX(x.ratio)}×` : `1/${ratioX(x.ratio)}`;
    const extra = [x.note && ["Probe note", x.note], x.block && ["Block", x.block], x.confirm != null && ["Later block", fmt(x.confirm)], x.second != null && ["Second endpoint", fmt(x.second)]].filter(Boolean);
    return `<div class="gi-head"><span class="label">${esc(i.famLabel)} · ${esc(i.phase)}</span><h4>${esc(chainName(cid))} · <span class="mono">${esc(i.short)}</span></h4></div>
      <div class="gi-nums">
        <div><span class="label">${esc(chainName(cid))}</span><b class="${x.kind}">${x.val == null ? "none" : esc(fmt(x.val))}</b></div>
        ${isRef ? "" : `<div><span class="label">Ethereum</span><b class="eth">${esc(fmt(x.eth))}</b></div>
        <div><span class="label">Ratio</span><b class="${x.kind}">${esc(ratio)}</b></div>`}
      </div>
      <div class="gi-txt"><div class="cls"><span class="hsw ${x.kind}"${x.kind === "pricier" || x.kind === "cheaper" ? ` style="${heatBg(x)}"` : ""}></span>${esc(GAS_KIND[x.kind])} · <span class="mono">${esc(x.status)}</span></div>
        <p>${esc(metric || GAS_STATUS[x.status] || "")}</p>
        ${extra.length ? `<dl>${extra.map(([k, v]) => `<dt>${esc(k)}</dt><dd>${esc(v)}</dd>`).join("")}</dl>` : ""}
        <div class="ev">${(x.evidence || []).map((p) => `<a href="${esc(evHref(p))}">${esc(p.replace(/^results\/[^/]+\//, ""))}</a>`).join("")}</div></div>`;
  }
  function gasPick(cid, iid) {
    gx.picked = [cid, iid];
    $$("#gasTable td.picked").forEach((td) => td.classList.remove("picked"));
    const b = $(`#gasTable button[data-c="${CSS.escape(cid)}"][data-i="${CSS.escape(iid)}"]`);
    if (b) b.parentElement.classList.add("picked");
    $("#gasInsp").innerHTML = gasDetail(cid, iid);
  }
  // What a zero-gas item measures, so the stat never reads as "calls are free".
  const LOW_LABEL = { "call-empty": "a zero-value CALL to an empty address" };
  function initGas() {
    const G = M.gas; if (!G || !$("#gas")) return;
    const name = (x) => `${chainName(x.chain)} ${G.items.find((i) => i.id === x.item).short}`;
    $("#gasLede").textContent = `Each square is one operation measured on one chain, divided by what the same operation costs on Ethereum. Warm squares cost more, cool squares cost less, and neutral squares match. Measured on ${G.date} inside read-only creation calls: operation gas, not transaction fees.`;
    $("#gasStats").innerHTML = [
      [fmt(G.diffCount), "measured prices differ from Ethereum", "hot"],
      [fmt(G.diffChains), `chains, across ${fmt(G.diffItems)} operations`, ""],
      G.hi ? [`${ratioX(G.hi.ratio)}×`, `highest: ${name(G.hi)}`, "hot"] : null,
      G.lo ? [G.lo.ratio === 0 ? "0 gas" : `1/${ratioX(G.lo.ratio)}`, G.lo.ratio === 0 && LOW_LABEL[G.lo.item.split("/")[1]] ? `${LOW_LABEL[G.lo.item.split("/")[1]]} on ${chainName(G.lo.chain)}${G.loWarmZero ? " (first and repeat access)" : ""}` : `lowest: ${name(G.lo)}`, "cool"] : null,
    ].filter(Boolean).map(([v, l, k]) => `<div class="gs"><span class="v ${k}">${esc(v)}</span><span class="l">${esc(l)}</span></div>`).join("");
    $("#gasFam").innerHTML = `<button type="button" data-f="" aria-pressed="true">All</button>` + G.families.map((f) => `<button type="button" data-f="${esc(f.id)}" aria-pressed="false">${esc(f.label)}<span class="n">${fmt(f.n)}</span></button>`).join("");
    $("#gasFam").addEventListener("click", (e) => { const b = e.target.closest("button"); if (!b) return; gx.fam = b.dataset.f; renderGas(); });
    $("#gasOnly").addEventListener("change", (e) => { gx.only = e.target.checked; renderGas(); });
    const steps = [-SCALE, -SCALE / 2, 0, SCALE / 2, SCALE];
    $("#gasScale").innerHTML = `<span class="gl">cheaper</span><span class="ramp" aria-hidden="true"></span><span class="gl">pricier</span>
      <span class="ticks" aria-hidden="true">${steps.map((s) => `<i>${s === 0 ? "1×" : s < 0 ? `1/${2 ** -s}` : `${2 ** s}×`}</i>`).join("")}</span>`;
    $("#gasLegend").innerHTML = [["same", "Same as Ethereum", "Neutral. The chain charged exactly Ethereum's gas."], ["baseline", "Ethereum", "The baseline row every ratio is measured against."],
      ["control", "Not a price", "A control or a gas-left reading, such as the unfunded value call. Shown, never coloured."], ["failed", "VM failure", "The operation failed, so it has no price."], ["none", "Not measured", "The endpoint refused the call or was unavailable."]]
      .map(([k, a, b]) => `<div class="lg"><span class="hsw ${k}"></span><span><b>${esc(a)}</b>${esc(b)}</span></div>`).join("");
    const tbl = $("#gasTable"), tip = $("#gasTip");
    tbl.addEventListener("click", (e) => { const b = e.target.closest("button[data-c]"); if (b) gasPick(b.dataset.c, b.dataset.i); });
    if (matchMedia("(hover: hover) and (pointer: fine)").matches) {
      tbl.addEventListener("mousemove", (e) => {
        const b = e.target.closest("button[data-c]");
        if (!b) { tip.hidden = true; return; }
        const x = gcell(b.dataset.c, b.dataset.i), i = G.items.find((y) => y.id === b.dataset.i);
        tip.innerHTML = `<b>${esc(chainName(b.dataset.c))}</b> · ${esc(i.short)}<br>${x.val == null ? esc(GAS_KIND[x.kind]) : `${esc(fmt(x.val))} gas`}${b.dataset.c !== M.refChain ? ` <span>vs Ethereum ${esc(fmt(x.eth))}</span>` : ""}${x.ratio != null && b.dataset.c !== M.refChain && x.ratio !== 1 ? `<br><em class="${x.kind}">${x.ratio === 0 ? "0×" : x.ratio > 1 ? ratioX(x.ratio) + "×" : "1/" + ratioX(x.ratio)}</em>` : ""}`;
        tip.hidden = false;
        const fr = $("#gasFrame").getBoundingClientRect();
        let L = e.clientX - fr.left + 14, T = e.clientY - fr.top + 14;
        if (L + tip.offsetWidth > fr.width) L = e.clientX - fr.left - tip.offsetWidth - 14;
        tip.style.transform = `translate(${Math.round(L)}px, ${Math.round(T)}px)`;
      });
      tbl.addEventListener("mouseleave", () => { tip.hidden = true; });
    }
    const nm = (ids) => listNames(ids);
    $("#gasNote").textContent = [G.matching.length ? `${fmt(G.matching.length)} chains match Ethereum on every item we could measure.` : "",
      G.partial.length ? `${nm(G.partial)} had partial opcode coverage;` : "",
      G.unmeasured.length ? `${nm(G.unmeasured)} couldn't be measured with this method.` : ""].filter(Boolean).join(" ");
    renderGas();
    // open on the most extreme price so the panel shows what a cell holds
    const seed = M.sweep && M.sweep[0] && M.sweep[0].g ? M.sweep[0].g : G.hi;
    if (seed) gasPick(seed.chain, seed.item);
  }

  /* ----------------------------------------------------------- per chain */
  let curChain = null;
  const CV_PAGE = 14;
  function chainDiffs(id) { return M.probes.filter((p) => ATTENTION.has(cell(id, p.id).class)); }
  function selectChain(id) {
    curChain = id;
    $$("#chainPick button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.chain === id)));
    const pk = $("#chainPick"), pb = $(`#chainPick button[data-chain="${CSS.escape(id)}"]`);
    if (pb && pk.scrollWidth > pk.clientWidth) pk.scrollLeft = Math.max(0, pb.offsetLeft - pk.offsetLeft - 24);
    const ch = M.chainById[id];
    const diffs = chainDiffs(id);
    const tally = {}; M.probes.forEach((p) => { const k = cell(id, p.id).class; tally[k] = (tally[k] || 0) + 1; });
    const tcol = { same: "var(--same)", differs: "var(--diff)", "execution-failure": "var(--fail)", "rpc-rejected": "var(--rej)", unavailable: "transparent", "endpoint-artifact": "var(--rej-soft)", "state-only": "var(--rej-soft)", reference: "var(--ref)" };
    const order = ["differs", "execution-failure", "rpc-rejected", "endpoint-artifact", "state-only", "unavailable", "same", "reference"];
    const cat = M.catalog.filter((r) => r.chain === id);
    const rej = M.probes.filter((p) => cell(id, p.id).class === "rpc-rejected");
    $("#chainView").innerHTML = `
      <div class="cv-meta">
        <h3>${esc(ch.name)}</h3>
        <div class="tally" role="img" aria-label="Probe classes on ${esc(ch.name)}">${order.filter((k) => tally[k]).map((k) => `<span style="flex:${tally[k]};background:${tcol[k]}" title="${esc(CLASSES[k].short)}: ${tally[k]}"></span>`).join("")}</div>
        <div class="chains">${order.filter((k) => tally[k]).map((k) => `<span class="chip"><span class="sw ${k}"></span>${esc(CLASSES[k].short)} ${fmt(tally[k])}</span>`).join("")}</div>
        <dl>
          ${ch.chainId != null ? `<dt>Chain ID</dt><dd>${esc(ch.chainId)}</dd>` : ""}
          ${ch.block ? `<dt>Block</dt><dd>${esc(ch.block)}</dd>` : ""}
          ${ch.status ? `<dt>Status</dt><dd>${esc(ch.status)}</dd>` : ""}
          ${ch.rpc ? `<dt>RPC</dt><dd>${esc(ch.rpcLabel || ch.rpc)}</dd>` : ""}
          ${ch.evidence ? `<dt>Raw</dt><dd><a href="${esc(evHref(ch.evidence))}">${esc(ch.evidence)}</a></dd>` : ""}
        </dl>
        ${ch.note ? `<p class="muted" style="font-size:.92rem">${esc(ch.note)}</p>` : ""}
      </div>
      <div style="min-width:0">
        ${id === M.refChain ? `<p class="cv-empty">Ethereum is the reference. Pick another chain to compare it with Ethereum.</p>` :
        diffs.length ? `<div class="cv-list"><div class="cv-row head"><span>Probe</span><span>${esc(ch.name)}</span><span>Ethereum</span></div>
          ${diffs.map((p, i) => { const c = cell(id, p.id), e = cell(M.refChain, p.id); return `<div class="cv-row"${i >= CV_PAGE ? " hidden" : ""}>
            <div class="p"><b>${esc(p.id)}</b><span class="cls"><span class="sw ${c.class}"></span>${esc(c.class)}</span><span class="muted" style="font-size:.88rem">${esc(p.meaning || "")}</span></div>
            <div class="val t" data-l="${esc(ch.name)}">${esc(c.value ?? "")}</div>
            <div class="val e" data-l="Ethereum">${esc(e.value ?? "")}</div></div>`; }).join("")}</div>
          ${diffs.length > CV_PAGE ? `<button class="btn ghost more" type="button" id="cvMore">Show all ${fmt(diffs.length)} differences</button>` : ""}`
        : M.probes.every((p) => cell(id, p.id).class === "unavailable") ? `<p class="cv-empty">No probe results were recorded for ${esc(ch.name)}.</p>`
        : `<p class="cv-empty">Every probe that ran on ${esc(ch.name)} matched Ethereum.</p>`}
        ${rej.length ? `<p class="muted" style="margin-top:14px;font-size:.92rem">${fmt(rej.length)} ${rej.length === 1 ? "probe was" : "probes were"} rejected by the endpoint before execution and are left out of this list.</p>` : ""}
        ${cat.length ? `<p style="margin-top:14px;font-size:.95rem"><a href="#catalog" data-catchain="${esc(id)}">${fmt(cat.length)} catalog ${cat.length === 1 ? "row" : "rows"} for ${esc(ch.name)}</a></p>` : ""}
      </div>`;
    const more = $("#cvMore");
    if (more) more.addEventListener("click", () => { $$("#chainView .cv-row[hidden]").forEach((r) => (r.hidden = false)); more.remove(); });
    const a = $("#chainView a[data-catchain]");
    if (a) a.addEventListener("click", () => { $("#catChain").value = id; cat_.chain = id; renderCatalog(); });
  }
  function initChains() {
    $("#chainPick").innerHTML = M.chains.map((c) => {
      const n = c.id === M.refChain ? null : chainDiffs(c.id).length;
      return `<button type="button" data-chain="${esc(c.id)}" aria-pressed="false">${esc(c.name)}${n == null ? "" : `<span class="n${n ? "" : " z"}">${fmt(n)}</span>`}</button>`;
    }).join("");
    $("#chainPick").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b) selectChain(b.dataset.chain); });
    const most = M.chains.filter((c) => c.id !== M.refChain).sort((a, b) => chainDiffs(b.id).length - chainDiffs(a.id).length)[0];
    selectChain(most.id);
  }

  /* ------------------------------------------------------------- catalog */
  const cat_ = { q: "", label: "", chain: "", all: false };
  const PAGE = 24;
  function renderCatalog() {
    const q = cat_.q.trim().toLowerCase().split(/\s+/).filter(Boolean);
    const rows = M.catalog.filter((r) => (!cat_.label || r.label === cat_.label) && (!cat_.chain || r.chain === cat_.chain) && q.every((w) => r._s.includes(w)));
    const shown = cat_.all || q.length || cat_.label || cat_.chain ? rows : rows.slice(0, PAGE);
    $("#catCount").textContent = `${fmt(rows.length)} of ${fmt(M.catalog.length)} rows`;
    $("#catList").innerHTML = shown.map((r) => `<details class="cat-item"><summary><span class="no">#${esc(r.n)}</span><span class="ch">${esc(chainName(r.chain))}</span><span class="ti">${esc(r.title)}</span><span class="badge ${esc(r.label)}">${esc(r.label)}</span></summary>
      <div class="cat-body"><p>${esc(r.consequence)}</p><div class="ev">${r.evidence.map((e) => `<a href="${esc(evHref(e.path))}">${esc(e.label)}</a>`).join("")}</div></div></details>`).join("") || `<p class="cv-empty">No rows match. Try a chain name, an opcode or an address like 0x0b.</p>`;
    $("#catMore").hidden = shown.length >= rows.length;
    $("#catMore").textContent = `Show all ${fmt(rows.length)} rows`;
  }
  function initCatalog() {
    M.catalog.forEach((r) => { r._s = [r.n, r.label, r.chain, chainName(r.chain), r.title, r.consequence].join(" ").toLowerCase(); });
    const labels = [...new Set(M.catalog.map((r) => r.label))];
    $("#catLabel").insertAdjacentHTML("beforeend", labels.map((l) => `<option value="${esc(l)}">${esc(l)} (${fmt(M.catalog.filter((r) => r.label === l).length)})</option>`).join(""));
    const chains = [...new Set(M.catalog.map((r) => r.chain))].sort((a, b) => chainName(a).localeCompare(chainName(b)));
    $("#catChain").insertAdjacentHTML("beforeend", chains.map((c) => `<option value="${esc(c)}">${esc(chainName(c))}</option>`).join(""));
    $("#catQ").addEventListener("input", (e) => { cat_.q = e.target.value; renderCatalog(); });
    $("#catLabel").addEventListener("change", (e) => { cat_.label = e.target.value; renderCatalog(); });
    $("#catChain").addEventListener("change", (e) => { cat_.chain = e.target.value; renderCatalog(); });
    $("#catMore").addEventListener("click", () => { cat_.all = true; renderCatalog(); });
    renderCatalog();
  }

  /* ----------------------------------------------------------- checklist */
  function initChecklist() {
    let saved = {}; try { saved = JSON.parse(store.get("evmish-check") || "{}"); } catch (e) {}
    $("#checkGrid").innerHTML = `<ul>${M.checklist.map((it, i) => { const id = `ck-${i}`; return `<li><input type="checkbox" id="${id}"${saved[id] ? " checked" : ""}><label for="${id}">${it}</label></li>`; }).join("")}</ul>`;
    const upd = () => {
      const b = $$("#checkGrid input"); const n = b.filter((x) => x.checked).length;
      $("#checkProgress").textContent = `${n} of ${b.length} checked`;
    };
    $("#checkGrid").addEventListener("change", (e) => { saved[e.target.id] = e.target.checked; store.set("evmish-check", JSON.stringify(saved)); upd(); });
    upd();
  }

  /* -------------------------------------------------------------- method */
  function initMethod() {
    const m = M.meta;
    $("#methodLede").textContent = `From ${m.dateLong} we ran ${fmt(m.probes)} probe cases on ${fmt(m.chains)} chains through ${fmt(m.endpoints)} public RPC endpoints, some run by the chain and some by third-party providers. Calls were read-only and rate-limited, and every result keeps the endpoint, block, timestamp and raw response. Every difference was confirmed a second time, on a second endpoint or at a later block.`;
    const R = M.verification || [];
    $("#rounds").innerHTML = `<div class="rtable-wrap"><table class="rtable">
      <thead><tr><th scope="col">Round</th><th scope="col" class="hide-sm">Date</th><th scope="col" class="n">Sampled</th><th scope="col" class="n">Correct</th><th scope="col" class="n">Wrong</th><th scope="col" class="n">Unverifiable</th><th scope="col" class="hide-sm">Rows</th></tr></thead>
      <tbody>${R.map((r) => {
        const cells = [...Array(r.wrong).fill("err"), ...Array(r.unverifiable).fill("unv"), ...Array(Math.max(0, r.correct)).fill("ok")];
        return `<tr><th scope="row">${esc(r.round)}</th><td class="mono hide-sm">${esc(r.date)}</td><td class="n">${fmt(r.sampled)}</td><td class="n">${fmt(r.correct)}</td><td class="n${r.wrong ? " bad" : ""}">${fmt(r.wrong)}</td><td class="n${r.unverifiable ? " unv" : ""}">${fmt(r.unverifiable)}</td>
          <td class="hide-sm"><span class="track" role="img" aria-label="${r.correct} correct, ${r.wrong} wrong, ${r.unverifiable} unverifiable">${cells.map((c) => `<i class="${c}"></i>`).join("")}</span></td></tr>
          <tr class="res"><td colspan="7" class="span">${esc(r.result)}</td></tr>`;
      }).join("")}</tbody></table></div>
      <div class="scope-foot"><span class="chip"><span class="sw" style="background:var(--diff)"></span>Wrong</span><span class="chip"><span class="sw" style="background:var(--fail)"></span>Unverifiable</span><span class="chip"><span class="sw" style="background:var(--safe)"></span>Correct</span></div>`;
    $("#roundsNote").textContent = "An independent checker re-ran random samples of catalog rows against live RPCs, a fresh sample each round. The latest round also re-derived Ethereum's gas baseline and adversarially reviewed the ranked second-sweep results.";
    $("#limits").innerHTML = LIMITS.map(([a, b]) => `<li><b>${esc(a)}</b><span>${esc(b)}</span></li>`).join("");
    $("#credits").innerHTML = CREDITS.map(([n, u]) => (u ? `<a href="${esc(u)}" rel="noopener">${esc(n)}</a>` : `<span>${esc(n)}</span>`)).join("");
    $("#endpoints").innerHTML = `<li class="label">Primary endpoints</li>` + (m.hosts || []).map((h) => `<li>${esc(h)}</li>`).join("");
    const sec = m.secondary || [];
    if (sec.length) $("#endpoints").insertAdjacentHTML("beforeend", `<li class="label" style="margin-top:8px">Second endpoints</li>` + sec.map((h) => `<li>${esc(h.label)} · ${esc(chainName(h.chain))} · ${esc(h.usedFor || "")}</li>`).join(""));
    $("#endpointsSum").textContent = `All ${fmt((m.hosts || []).length + sec.length)} RPC endpoints used`;
  }

  /* --------------------------------------------------------------- boot */
  loadData().then((raw) => {
    M = adapt(raw);
    M.chainById = Object.fromEntries(M.chains.map((c) => [c.id, c]));
    M.probeById = Object.fromEntries(M.probes.map((p) => [p.id, p]));
    if (!M.categories) M.categories = [...new Set(M.probes.map((p) => p.category))];
    bindStats();
    revealScope();
    buildProbe();
    renderFindings();
    renderSweep();
    initMatrix();
    initGas();
    initChains();
    initCatalog();
    initChecklist();
    initMethod();
    let rz; addEventListener("resize", () => { clearTimeout(rz); rz = setTimeout(() => drawScope(1), 120); });
    document.addEventListener("themechange", () => drawScope(1));
    document.documentElement.dataset.ready = "1";
  }).catch((err) => {
    console.warn(err);
    $$(".loading").forEach((el) => (el.textContent = err.message));
    document.documentElement.dataset.ready = "error";
  });
})();

/* Launch cards. Text and numbers come from data/data.json through assets/model.js. */
(async function () {
  "use strict";
  const { loadData, adapt, ATTENTION, COPY, SWEEP_COPY, esc, grab } = window.EVM;
  const id = new URLSearchParams(location.search).get("c") || "cover";
  const M = adapt(await loadData("../"));
  const byId = Object.fromEntries(M.chains.map((c) => [c.id, c]));
  const name = (i) => (byId[i] ? byId[i].name : i);
  const names = (ids) => { const n = ids.map(name); return n.length < 2 ? n.join("") : n.length === 2 ? `${n[0]} and ${n[1]}` : `${n.slice(0, -1).join(", ")} and ${n[n.length - 1]}`; };
  const fmt = (n) => (typeof n === "number" ? n.toLocaleString("en-US") : /^\d+$/.test(String(n)) ? BigInt(n).toLocaleString("en-US") : String(n));
  const cell = (c, p) => (M.cells[c] || {})[p] || { class: "unavailable" };
  const card = document.getElementById("card");
  const m = M.meta;
  const nDiff = m.differences;

  const WM = `<span class="wm"><span class="wm-evm">EVM</span><span class="wm-ish">ish</span></span>`;
  const top = (tag) => `<div class="top"><span class="brand">${WM}</span><span class="tag">${tag}</span></div>`;
  const foot = (left) => `<div class="foot"><span class="k">${left || `<b>${fmt(m.chains)}</b> chains · <b>${fmt(m.probes)}</b> probe cases · <b>${fmt(nDiff)}</b> confirmed differences`}</span><span class="k">${esc(m.date)}</span></div>`;

  function tokens() {
    const cs = getComputedStyle(document.documentElement);
    const g = (n) => cs.getPropertyValue(n).trim();
    return { same: g("--same"), diff: g("--diff"), fail: g("--fail"), rej: g("--rej"), ref: g("--ref"), soft: g("--rej-soft"), ink: g("--ink"), muted: g("--muted") };
  }
  // Draw the matrix. transpose=false: chains are columns, probes rows.
  function drawMatrix(cv, W, H, transpose) {
    const t = tokens();
    const rows = transpose ? M.chains : M.probes, cols = transpose ? M.probes : M.chains;
    // Fractional cells: with hundreds of probe cases a cell can be under 2px, so gaps run only along the wider axis.
    const cw = W / cols.length, ch = H / rows.length;
    const dpr = 2; cv.width = W * dpr; cv.height = H * dpr;
    cv.style.width = W + "px"; cv.style.height = H + "px";
    const x = cv.getContext("2d"); x.scale(dpr, dpr);
    const gx = cw >= 4 ? 1 : 0, gy = ch >= 4 ? 1 : 0;
    rows.forEach((r, ri) => cols.forEach((c, ci) => {
      const chain = transpose ? r.id : c.id, probe = transpose ? c.id : r.id;
      const k = chain === M.refChain ? "reference" : cell(chain, probe).class;
      // snap to half-pixels (the canvas is 2x) so hairline rows tile without seams
      const sn = (v) => Math.round(v * 2) / 2;
      const X = sn(ci * cw) + gx, Y = sn(ri * ch) + gy, w = sn((ci + 1) * cw) - sn(ci * cw) - 2 * gx, h = sn((ri + 1) * ch) - sn(ri * ch) - 2 * gy;
      if (k === "differs" || k === "execution-failure") { x.fillStyle = k === "differs" ? t.diff : t.fail; x.fillRect(X, Y, w, h); }
      else if (k === "reference") { x.fillStyle = t.ref; x.fillRect(X, Y, w, h); }
      else if (k === "rpc-rejected") { x.fillStyle = t.rej; x.globalAlpha = 0.35; x.fillRect(X, Y, w, h); x.globalAlpha = 1; }
      else if (k === "unavailable") { /* blank */ }
      else if (k === "same") { x.fillStyle = t.same; x.fillRect(X, Y, w, h); }
      else { x.fillStyle = t.soft; x.fillRect(X, Y, w, h); }
    }));
  }
  const legend = () => `<div style="display:flex;flex-wrap:wrap;gap:6px 16px">${[["reference", "Ethereum"], ["differs", "Differs"], ["execution-failure", "VM failure"], ["rpc-rejected", "RPC rejected"], ["same", "Same"]].map(([k, l]) => `<span class="chip" style="font-size:15px"><span class="sw ${k}" style="width:14px;height:14px"></span>${l}</span>`).join("")}</div>`;

  const CARD_WHY = {
    bls: "A verifier that checks only the success flag keeps going with no point.",
    ripemd: "It compiles and passes on Ethereum, then fails after deploy.",
    number: "Two clocks. A timelock built on one opens at the wrong time.",
    prevrandao: "Same value at every block we checked. A fixed seed anyone can read in advance.",
    gas: "Stipends and budgets tuned on Ethereum can run out of gas.",
  };

  // Big comparison numbers, read from the matrix cell values.
  function bigBlock(f) {
    const v = (c, p) => cell(c, p).v || {};
    const row = (n, who, cls) => `<span class="big n ${cls}">${esc(fmt(n))}</span><span class="who">${esc(who)}</span>`;
    let label, rows;
    if (f.id === "gas") {
      const t = v(f.chains[0], "cold-warm-extcodesize"), e = v(M.refChain, "cold-warm-extcodesize");
      label = "Cold access gas"; rows = row(t.gas_delta, name(f.chains[0]), "t") + row(e.gas_delta, "Ethereum", "e");
    } else if (f.id === "number") {
      const t = v(f.chains[0], "number");
      label = `${name(f.chains[0])}, one block`; rows = row(t.uint256, "block.number", "t") + row(t.header_value, "L2 header", "i");
    } else return "";
    return `<div><span class="lbl">${esc(label)}</span><div class="vs">${rows}</div></div>`;
  }

  if (id === "cover") {
    card.classList.add("cover");
    card.innerHTML = `<div class="top"><span class="brand big-wm">${WM}</span><span class="tag">Live probe study · ${esc(m.date)}</span></div>
      <div class="col" style="gap:8px;align-content:center">
        <h1 class="thesis" style="font-size:50px"><span class="a">EVM-compatible</span><span class="b">isn't EVM-<span class="k">equivalent.</span></span></h1>
        <p class="sub" style="font-size:19px">Where EVM-compatible chains quietly differ from Ethereum.</p>
        <div style="display:grid;grid-template-columns:auto 1fr;gap:28px;align-items:end">
          <div style="display:flex;gap:22px;align-items:baseline">
            <div><span class="big" style="font-size:50px">${fmt(m.chains)}</span><span class="lbl" style="margin:4px 0 0">chains</span></div>
            <div class="big" style="font-size:40px;color:var(--muted)">/</div>
            <div><span class="big" style="font-size:50px">${fmt(m.probes)}</span><span class="lbl" style="margin:4px 0 0">probe cases</span></div>
          </div>
          <div style="justify-self:end"><canvas id="cv"></canvas></div>
        </div>
      </div>${foot(`<b>${fmt(nDiff)}</b> confirmed differences · raw evidence for each`)}`;
    drawMatrix(document.getElementById("cv"), 430, 135, true);
  } else if (id === "method") {
    const ex = M.example;
    const v = BigInt(ex.rawReturn).toString();
    card.innerHTML = `${top("How a probe works")}
      <div class="col" style="gap:18px">
        <h2 class="ttl">Init code goes in. The result comes back. Nothing is written.</h2>
        <div class="steps3">
          <div class="box"><span class="lbl" style="margin:0">1 · init code</span><code>${esc(ex.initCode)}</code><span class="sub" style="font-size:16px">PREVRANDAO, MSTORE, RETURN</span></div>
          <span class="arrow">→</span>
          <div class="box"><span class="lbl" style="margin:0">2 · eth_call, no <span style="text-transform:none">to</span></span><code>${esc(name(ex.chain))}<br>block ${esc(ex.block)}</code><span class="sub" style="font-size:16px">runs as a deploy</span></div>
          <span class="arrow">→</span>
          <div class="box"><span class="lbl" style="margin:0">3 · result</span><code style="color:var(--diff);font-weight:700">${esc(v)}</code><span class="sub" style="font-size:16px">returned, not stored</span></div>
        </div>
        <p class="sub">No transaction, no signature, no deploy. Any public RPC can answer it.</p>
      </div>${foot()}`;
  } else if (id === "matrix") {
    card.innerHTML = `${top("The matrix")}
      <div class="row" style="grid-template-columns: 270px 1fr; align-items:center">
        <div class="col">
          <h2 class="ttl" style="font-size:40px">${fmt(m.chains)} chains × ${fmt(m.probes)} probe cases</h2>
          <p class="sub"><b style="color:var(--diff)">${fmt(nDiff)}</b> cells differ from Ethereum. Each one confirmed a second time.</p>
          ${legend()}
        </div>
        <div style="justify-self:end"><canvas id="cv"></canvas></div>
      </div>${foot()}`;
    drawMatrix(document.getElementById("cv"), 440, 300, false);
  } else if (id === "gasmap") {
    const G = M.gas, t = tokens();
    const hot = G.chains.filter((c) => c.id === M.refChain || G.stat[c.id].diff > 0);
    const rest = G.matching.length;
    const rx = (r) => String(Number((r >= 1 ? r : 1 / r).toPrecision(3)));
    card.innerHTML = `${top("Gas schedule · " + esc(G.date))}
      <div class="col" style="gap:12px">
        <div class="row" style="grid-template-columns: minmax(0,1fr) auto; align-items:end; gap:20px">
          <h2 class="ttl" style="font-size:44px">Same opcode,<br>different price.</h2>
          <div class="gstat"><span class="big" style="font-size:64px;color:var(--diff)">${fmt(G.diffCount)}</span><span class="sub" style="font-size:18px;line-height:1.2">measured prices differ<br>on ${fmt(G.diffChains)} chains</span></div>
        </div>
        <div class="hm"><div class="hm-l">${hot.map((c) => `<span class="${c.id === M.refChain ? "e" : ""}">${esc(c.name)}</span>`).join("")}</div><canvas id="cv"></canvas></div>
        <div class="hm-f"><span class="hm-k"><i style="background:var(--hc2)"></i>cheaper</span><span class="hm-ramp"></span><span class="hm-k">pricier<i style="background:var(--hw2)"></i></span>
          <span class="sub" style="font-size:15px;margin-left:auto">Up to <b style="color:var(--diff)">${rx(G.hi.ratio)}×</b> Ethereum · ${fmt(rest)} chains match on every item we could measure</span></div>
      </div>${foot(`<b>${fmt(G.items.length)}</b> operations · <b>${fmt(G.chains.length)}</b> chains · read-only eth_call`)}`;
    const cv = document.getElementById("cv"), W = 600, rh = 21, H = hot.length * rh;
    cv.width = W * 2; cv.height = H * 2; cv.style.width = W + "px"; cv.style.height = H + "px";
    const x = cv.getContext("2d"); x.scale(2, 2);
    const cs = getComputedStyle(document.documentElement), v = (n) => cs.getPropertyValue(n).trim();
    const items = G.items, cw = W / items.length;
    hot.forEach((c, ri) => items.forEach((it, ci) => {
      const g = (G.cells[c.id] || {})[it.id] || { kind: "none" };
      const X = ci * cw, Y = ri * rh + 2, w = Math.max(1, cw - 0.8), h = rh - 4;
      if (g.kind === "pricier" || g.kind === "cheaper") {
        const tt = g.ratio <= 0 ? 1 : Math.min(1, Math.abs(Math.log2(g.ratio)) / 6), p = 0.14 + 0.86 * Math.pow(tt, 0.85);
        x.fillStyle = mix(g.kind === "pricier" ? [v("--h0"), v("--hw1"), v("--hw2")] : [v("--h0"), v("--hc1"), v("--hc2")], p);
      } else if (g.kind === "baseline") x.fillStyle = mix([v("--h0"), v("--ref"), v("--ref")], 0.22);
      else if (g.kind === "same") x.fillStyle = v("--h0");
      else return;
      x.fillRect(X, Y, w, h);
    }));
    void t;
  } else if (SWEEP_COPY[id] && M.sweep.find((s) => s.id === id)) {
    const s = M.sweep.find((y) => y.id === id), c = SWEEP_COPY[id], g = s.g;
    const h = { F: fmt, name, grab };
    const tv = Number(g.val), ev = Number(g.eth), mx = Math.max(tv, ev);
    const gate = id === "somnia-sstore" ? grab(s.row && s.row.consequence, /at least ([\d,]+) gas remaining/) : null;
    const scaleTop = Math.max(mx, gate ? Number(gate.replace(/,/g, "")) : 0);
    const w = (n) => Math.max(0.6, n / scaleTop * 100).toFixed(2) + "%";
    const r = g.ratio, rel = r > 1 ? `${String(Number(r.toPrecision(3)))}×` : `1/${String(Number((1 / r).toPrecision(3)))}`;
    const why = typeof c.card === "function" ? c.card(s, h) : c.card;
    const idx = M.sweep.indexOf(s) + 1;
    card.innerHTML = `${top(`Second sweep ${String(idx).padStart(2, "0")} · ${esc(c.family)}`)}
      <div class="col" style="gap:16px">
        <h2 class="ttl" style="font-size:36px">${esc(c.title(s, h))}</h2>
        <div class="row" style="grid-template-columns: minmax(0, 1.25fr) minmax(0, 1fr); align-items:start">
          <div class="cbars ${r > 1 ? "up" : "down"}">
            <div class="cb t"><span class="cn">${esc(name(s.chain))}</span><span class="ct"><i style="width:${w(tv)}"></i></span><span class="cv">${esc(fmt(g.val))}</span></div>
            <div class="cb e"><span class="cn">Ethereum</span><span class="ct"><i style="width:${w(ev)}"></i></span><span class="cv">${esc(fmt(g.eth))}</span></div>
            ${gate ? `<div class="cb g"><span class="cn">Gas left needed</span><span class="ct"><i style="width:${w(Number(gate.replace(/,/g, "")))}"></i></span><span class="cv">${esc(gate)}</span></div>` : ""}
            <div class="cr"><span class="big">${esc(rel)}</span><span class="sub" style="font-size:18px">${r > 1 ? "Ethereum's gas" : "of Ethereum's gas"}</span></div>
          </div>
          <div class="col">
            <div><span class="lbl">Why it matters</span><p class="sub">${esc(why)}</p></div>
          </div>
        </div>
      </div>${foot(`read-only eth_call · later block and second endpoint agree`)}`;
  } else {
    const idx = M.findings.findIndex((f) => f.id === id);
    const f = M.findings[idx];
    if (!f) throw new Error("unknown card " + id);
    const c = COPY[f.id];
    // Many chains with the same precompile output: one aligned row per chain, values copied from the raw lines.
    const pc = [...(f.rawLines || "").matchAll(/^(\S.*?) block (0x[0-9a-f]+): (\S+) ->\s*precompile_call_status=(\d+), precompile_output_words=(\[[^\]]*\])/gim)];
    const compact = pc.length > 2 ? `<span class="d">${esc(pc[0][3])} -> call_status, output_words</span>\n` + pc.map((m) => {
      const who = (m[1] + " ").padEnd(19, " ");
      return `<span class="${/^Ethereum/.test(m[1]) ? "e" : "t"}">${esc(who)}</span>${esc(m[4])}  ${esc(m[5])}`;
    }).join("\n") : null;
    // Valid-vector lines: "<Chain> block 0x..: G1ADD 0x0b valid vector -> status, output_bytes=N"
    const vv = [...(f.rawLines || "").matchAll(/^(\S.*?) block (0x[0-9a-f]+): (.+?) -> ([\w-]+), output_bytes=(\d+)/gim)];
    const pad = (t, n) => (t + " ").padEnd(n, " ");
    const vrows = vv.length > 2 ? `<span class="d">${esc(vv[0][3])}\n${pad("chain", 19)}${pad("status", 15)}bytes</span>\n` + vv.map((m) => `<span class="${/^Ethereum/.test(m[1]) ? "e" : "t"}">${esc(pad(m[1], 19))}</span>${esc(pad(m[4], 15))}${esc(m[5])}`).join("\n") +
      (f.failClosed || []).map((id) => { const v = cell(id, f.probes[0]).v || {}; return `\n<span class="d">${esc(pad(name(id), 19))}${esc(pad(v.status, 15))}${esc(v.output ? (v.output.length - 2) / 2 : "")}</span>`; }).join("") : null;
    const lines = vrows || compact || (f.rawLines || "").split("\n").flatMap((ln) => {
      const m = ln.match(/^(\S.*? block(?: tag)? 0x[0-9a-f]+:)\s+(.+)$/i);
      return m && ln.length > 40 ? [m[1], "  " + m[2]] : [ln];
    }).map((ln) => {
      const isEth = /^Ethereum/.test(ln);
      return /^\S/.test(ln) ? `<span class="${isEth ? "e" : "t"}">${esc(ln)}</span>` : esc(ln);
    }).join("\n");
    card.innerHTML = `${top(`Finding ${String(idx + 1).padStart(2, "0")} / ${String(M.findings.length).padStart(2, "0")} · ${esc(f.category)}`)}
      <div class="col" style="gap:16px">
        <h2 class="ttl">${esc(c.title(f, names))}</h2>
        <div class="row" style="grid-template-columns: minmax(0, 1.35fr) minmax(0, 1fr); align-items:start">
          <div class="term">${lines}</div>
          <div class="col">
            ${bigBlock(f) || `<div><span class="lbl">Chains affected</span><div class="pills">${f.chains.map((i) => `<span class="pill">${esc(name(i))}</span>`).join("")}</div></div>`}
            <div><span class="lbl">Why it matters</span><p class="sub">${esc(CARD_WHY[f.id])}</p></div>
          </div>
        </div>
      </div>${foot()}`;
  }
  function mix(stops, p) { // stops [neutral, mid, end] as hex; p in 0..1
    const hex = (h) => { h = h.replace("#", ""); return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)); };
    const [a, b] = p < 0.5 ? [hex(stops[0]), hex(stops[1])] : [hex(stops[1]), hex(stops[2])];
    const q = p < 0.5 ? p / 0.5 : (p - 0.5) / 0.5;
    return `rgb(${a.map((v, i) => Math.round(v + (b[i] - v) * q)).join(",")})`;
  }
  await document.fonts.ready;
  document.documentElement.dataset.ready = "1";
})().catch((e) => { document.body.textContent = "card error: " + e.message; document.documentElement.dataset.ready = "error"; console.error(e); });

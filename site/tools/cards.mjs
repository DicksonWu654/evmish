// Renders the launch cards to PNG: 800x450 CSS px at 2x = 1600x900.
// Usage: node tools/cards.mjs [previewDir]   (previewDir gets 600px-wide copies for a readability check)
import { chromium } from "playwright";
import { serve } from "./serve.mjs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const site = fileURLToPath(new URL("..", import.meta.url));
const CARDS = (process.env.C || "cover,method,bls,ripemd,number,prevrandao,gas,matrix,gasmap,tempo-create,somnia-sstore,megaeth-log,monad-memory").split(",");
const NAMES = { cover: "01-cover", method: "02-how-a-probe-works", bls: "03-bls-precompiles", ripemd: "04-ripemd160", number: "05-arbitrum-block-number", prevrandao: "06-prevrandao", gas: "07-monad-cold-access", matrix: "08-matrix", gasmap: "09-gas-heatmap", "tempo-create": "10-tempo-create", "somnia-sstore": "11-somnia-sstore", "megaeth-log": "12-megaeth-log", "monad-memory": "13-monad-memory" };
const PORT = 4181;
const server = await serve(PORT, join(site, ".."));
const browser = await chromium.launch();
const preview = process.argv[2];
let bad = 0;
for (const c of CARDS) {
  const ctx = await browser.newContext({ viewport: { width: 800, height: 450 }, deviceScaleFactor: 2, colorScheme: "light" });
  const page = await ctx.newPage();
  const errs = [];
  page.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") errs.push(m.text()); });
  page.on("pageerror", (e) => errs.push(e.message));
  await page.goto(`http://127.0.0.1:${PORT}/site/cards/card.html?c=${c}`, { waitUntil: "networkidle" });
  await page.waitForFunction(() => document.documentElement.dataset.ready);
  const fit = await page.evaluate(() => {
    const card = document.getElementById("card"); const r = card.getBoundingClientRect(); const out = [];
    card.querySelectorAll("*").forEach((el) => { const b = el.getBoundingClientRect(); if (b.width && (b.right > r.right + 0.5 || b.bottom > r.bottom + 0.5)) out.push(el.tagName + "." + el.className); });
    const foot = card.querySelector(".foot").getBoundingClientRect(); const body = card.children[1].getBoundingClientRect();
    if (body.bottom > foot.top + 0.5) out.push("body overlaps footer by " + Math.round(body.bottom - foot.top));
    return out;
  });
  if (errs.length || fit.length) { bad++; console.log(c, errs, fit.slice(0, 6)); }
  const file = join(site, "cards", NAMES[c] + ".png");
  await page.screenshot({ path: file });
  if (preview) {
    const p2 = await browser.newPage({ viewport: { width: 600, height: 338 } });
    await p2.goto("file://" + file);
    await p2.evaluate(() => { const i = document.images[0]; document.body.style.margin = "0"; i.style.cssText = "width:600px;height:auto;display:block;margin:0"; });
    await p2.screenshot({ path: join(preview, NAMES[c] + "-600.png") }); await p2.close();
  }
  await ctx.close();
}
await browser.close(); server.close();
console.log(bad ? `${bad} cards with problems` : "cards ok");

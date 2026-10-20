// Screenshot + layout checks. Usage: node tools/shots.mjs [outDir] [--full]
import { chromium } from "playwright";
import { serve } from "./serve.mjs";
import { mkdirSync } from "node:fs";
import { join } from "node:path";
import { fileURLToPath } from "node:url";

const site = fileURLToPath(new URL("..", import.meta.url));
const out = process.argv[2] || join(site, "screenshots");
mkdirSync(out, { recursive: true });
const PORT = 4179;
// Serve the repository root so ../results evidence links resolve like in a real checkout.
const server = await serve(PORT, join(site, ".."));
const base = `http://127.0.0.1:${PORT}/site/`;
const browser = await chromium.launch();
const widths = (process.env.W || "1440,390,360").split(",").map(Number);
const themes = (process.env.T || "light,dark").split(",");
const ALL = ["top", "probe", "findings", "sweep", "matrix", "gas", "chains", "catalog", "checklist", "method"];
let problems = 0;
for (const theme of themes) {
  for (const w of widths) {
    const ctx = await browser.newContext({ viewport: { width: w, height: w > 800 ? 900 : 800 }, deviceScaleFactor: Number(process.env.DSF || (w > 800 ? 1 : 2)), colorScheme: theme });
    const page = await ctx.newPage();
    const errs = [];
    page.on("console", (m) => { if (m.type() === "error" || m.type() === "warning") errs.push(`${m.type()}: ${m.text()}`); });
    page.on("pageerror", (e) => errs.push("pageerror: " + e.message));
    page.on("requestfailed", (r) => errs.push("requestfailed: " + r.url()));
    await page.goto(base, { waitUntil: "networkidle" });
    await page.waitForFunction(() => document.documentElement.dataset.ready);
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(1700); // hero sweep animation
    const ov = await page.evaluate(() => {
      const W = document.documentElement.clientWidth; const bad = [];
      document.querySelectorAll("body *").forEach((el) => {
        const r = el.getBoundingClientRect();
        if (!el.closest(".skip") && r.width && (r.right > W + 1 || r.left < -1)) {
          // ignore content inside scroll containers
          let p = el.parentElement, inside = false;
          while (p && p !== document.body) { const cs = getComputedStyle(p); if (/(auto|scroll|hidden)/.test(cs.overflowX)) { inside = true; break; } p = p.parentElement; }
          if (!inside) bad.push(el.tagName + "." + el.className + " " + Math.round(r.left) + ".." + Math.round(r.right));
        }
      });
      return { sw: document.documentElement.scrollWidth, W, bad: bad.slice(0, 8) };
    });
    if (ov.sw > ov.W || ov.bad.length) { problems++; console.log(`[${theme} ${w}] OVERFLOW scrollWidth=${ov.sw} W=${ov.W}`, ov.bad); }
    if (errs.length) { problems++; console.log(`[${theme} ${w}] console:`, errs); }
    const tag = `${w}-${theme}`;
    if (process.argv.includes("--full")) await page.screenshot({ path: join(out, `full-${tag}.png`), fullPage: true });
    const sections = process.env.S ? process.env.S.split(",") : ALL;
    for (const s of sections) {
      await page.evaluate((id) => { const el = document.getElementById(id); window.scrollTo({ top: id === "top" ? 0 : el.getBoundingClientRect().top + window.scrollY - 52, behavior: "instant" }); }, s);
      await page.waitForTimeout(250);
      await page.screenshot(process.env.JPG ? { path: join(out, `${tag}-${s}.jpg`), type: "jpeg", quality: Number(process.env.Q || 62) } : { path: join(out, `${tag}-${s}.png`) });
    }
    await ctx.close();
  }
}
await browser.close();
server.close();
console.log(problems ? `${problems} problem groups` : "no overflow, no console errors");

// Bundles data/data.json into assets/data.js so index.html also works when opened from disk.
// Run from site/: node tools/build-data.mjs
import { readFileSync, writeFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { join } from "node:path";

const site = fileURLToPath(new URL("..", import.meta.url));
const data = JSON.parse(readFileSync(join(site, "data/data.json"), "utf8"));
writeFileSync(join(site, "assets/data.js"), `window.EVM_DATA = ${JSON.stringify(data)};\n`);
console.log("wrote assets/data.js");

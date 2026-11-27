// Size of the build, gzipped. "Initial JS" = the scripts index.html loads before anything else (entry + modulepreload),
// to compare with the budget of 200 KB. The other chunks are loaded later (lazy pages). Detail: stats.html.
import { readdirSync, readFileSync, statSync } from "node:fs";
import { join } from "node:path";
import { gzipSync } from "node:zlib";

const DIST = new URL("../dist/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
const BUDGET_KB = 200;
const kb = (n) => (n / 1024).toFixed(1);
const gz = (file) => gzipSync(readFileSync(join(DIST, file)), { level: 9 }).length;

const html = readFileSync(join(DIST, "index.html"), "utf8");
const initial = [...html.matchAll(/(?:src|href)="\/(assets\/[^"]+\.js)"/g)].map((m) => m[1]);
const css = [...html.matchAll(/href="\/(assets\/[^"]+\.css)"/g)].map((m) => m[1]);
const all = readdirSync(join(DIST, "assets")).map((f) => `assets/${f}`);
const lazy = all.filter((f) => f.endsWith(".js") && !initial.includes(f));
const fonts = all.filter((f) => /\.(woff2?|ttf)$/.test(f));

const initialJs = initial.reduce((s, f) => s + gz(f), 0);
console.log("\nTaille du build (gzip) :");
for (const f of initial) console.log(`  initial  ${kb(gz(f)).padStart(7)} KB  ${f}`);
for (const f of lazy) console.log(`  différé  ${kb(gz(f)).padStart(7)} KB  ${f}`);
for (const f of css) console.log(`  css      ${kb(gz(f)).padStart(7)} KB  ${f}`);
console.log(
  `  polices  ${kb(fonts.reduce((s, f) => s + statSync(join(DIST, f)).size, 0)).padStart(7)} KB  ${fonts.length} fichiers (téléchargés seulement si la page en a besoin)`,
);
console.log(`JS initial : ${kb(initialJs)} KB gzip (budget ${BUDGET_KB} KB)`);
if (initialJs > BUDGET_KB * 1024) {
  console.error("Budget dépassé");
  process.exit(1);
}

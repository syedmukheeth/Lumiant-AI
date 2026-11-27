// First-load JavaScript per route, gzipped, from the production build (Next 16 / Turbopack writes the chunk list to
// .next/diagnostics/route-bundle-stats.json; `next build` itself no longer prints sizes).
//
//   node scripts/bundle-report.mjs                 print the table
//   node scripts/bundle-report.mjs --budget        fail if a route grows past its recorded size + 10 %
//   node scripts/bundle-report.mjs --write-budget  record the current sizes in bundle-budget.json
//
// Run after `pnpm build`. Sizes are deterministic for a given build, so the budget is safe to check in CI.
import { existsSync, readFileSync, writeFileSync } from "node:fs";
import { join, resolve } from "node:path";
import { gzipSync } from "node:zlib";

const root = resolve(import.meta.dirname, "..");
const statsPath = join(root, ".next", "diagnostics", "route-bundle-stats.json");
const budgetPath = join(root, "bundle-budget.json");
const HEADROOM = 1.1;

if (!existsSync(statsPath)) {
  console.error(`No ${statsPath}. Run \`pnpm build\` first.`);
  process.exit(2);
}

const stats = JSON.parse(readFileSync(statsPath, "utf8"));
const gzCache = new Map();
const gzipBytes = (chunk) => {
  const file = join(root, chunk.replaceAll("\\", "/"));
  if (!gzCache.has(file)) gzCache.set(file, gzipSync(readFileSync(file)).length);
  return gzCache.get(file);
};

const rows = stats
  .map((s) => ({
    route: s.route,
    rawKb: s.firstLoadUncompressedJsBytes / 1024,
    gzKb: s.firstLoadChunkPaths.reduce((sum, c) => sum + gzipBytes(c), 0) / 1024,
  }))
  .sort((a, b) => b.gzKb - a.gzKb);

const kb = (n) => n.toFixed(1).padStart(8);
console.log(`${"route".padEnd(32)} ${"raw KB".padStart(8)} ${"gzip KB".padStart(8)}`);
for (const r of rows) console.log(`${r.route.padEnd(32)} ${kb(r.rawKb)} ${kb(r.gzKb)}`);

const args = new Set(process.argv.slice(2));
if (args.has("--write-budget")) {
  const budget = Object.fromEntries(rows.map((r) => [r.route, Number(r.gzKb.toFixed(1))]));
  writeFileSync(budgetPath, `${JSON.stringify(budget, null, 2)}\n`);
  console.log(`\nRecorded ${rows.length} routes in bundle-budget.json`);
}
if (args.has("--budget")) {
  const budget = JSON.parse(readFileSync(budgetPath, "utf8"));
  const over = rows.filter((r) => budget[r.route] !== undefined && r.gzKb > budget[r.route] * HEADROOM);
  const unknown = rows.filter((r) => budget[r.route] === undefined).map((r) => r.route);
  if (unknown.length) console.log(`\nNo budget yet for: ${unknown.join(", ")}`);
  if (over.length) {
    console.error("\nOver budget (recorded size + 10 %):");
    for (const r of over) console.error(`  ${r.route}: ${r.gzKb.toFixed(1)} KB > ${(budget[r.route] * HEADROOM).toFixed(1)} KB`);
    process.exit(1);
  }
  console.log("\nAll routes within budget.");
}

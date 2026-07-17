// Build+preflight every theme using the example configs — the template's
// acceptance for fixed-layer changes (a boutique-only build never renders the
// other themes' branches).
import { readFileSync, writeFileSync, readdirSync } from "node:fs";
import { execSync } from "node:child_process";

const SITE = "src/config/site.json";
const original = readFileSync(SITE, "utf8");
const themes = new Map([["boutique", original]]);
for (const f of readdirSync("src/config/examples").filter((f) => f.endsWith(".json"))) {
  const theme = f.split(".")[0];
  if (!themes.has(theme)) themes.set(theme, readFileSync(`src/config/examples/${f}`, "utf8"));
}

let failed = false;
try {
  for (const [theme, cfg] of themes) {
    writeFileSync(SITE, cfg);
    try {
      execSync("npm run ship", { stdio: "pipe" });
      console.log(`matrix ${theme}: OK`);
    } catch (e) {
      failed = true;
      console.error(`matrix ${theme}: FAIL\n${e.stdout?.toString().split("\n").filter((l) => l.includes("- ") || l.includes("FAIL") || l.includes("error")).slice(0, 12).join("\n")}`);
    }
  }
} finally {
  writeFileSync(SITE, original);
}
process.exit(failed ? 1 : 0);

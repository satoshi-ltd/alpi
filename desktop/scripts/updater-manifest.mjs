import { readdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, resolve } from "node:path";

import { pinManifest } from "../src/lib/updater-manifest.mjs";

const [, , file, tag] = process.argv;
if (!file || !tag) {
  console.error("usage: updater-manifest.mjs <latest.json> <desktop-vX.Y.Z>");
  process.exit(2);
}

const path = resolve(file);
const manifest = JSON.parse(readFileSync(path, "utf8"));
const assets = readdirSync(dirname(path));
const { manifest: pinned, missing } = pinManifest(manifest, tag, assets);
if (missing.length) {
  console.error(`updater manifest names assets the release does not carry:\n  ${missing.join("\n  ")}`);
  process.exit(1);
}
writeFileSync(path, `${JSON.stringify(pinned, null, 2)}\n`);
for (const [platform, entry] of Object.entries(pinned.platforms)) console.log(`${platform} -> ${entry.url}`);

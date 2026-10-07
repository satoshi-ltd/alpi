import { readdirSync, readFileSync, statSync } from "node:fs";
import { join, relative } from "node:path";
import { describe, expect, it } from "vitest";

const SRC = import.meta.dirname;
const VERB = "(?:loading|syncing|fetching)";
const ELLIPSIS = new RegExp(`^\\s*${VERB}\\b[^\\n]*?(?:…|\\.\\.\\.)\\s*$`, "i");
const BARE = new RegExp(`^\\s*${VERB}(?:\\s+\\w+)?\\s*$`, "i");
const LEADS = new RegExp(`^\\s*${VERB}\\b`, "i");
const SHOWN = /(?:\?\??|\|\||&&|\breturn|\{|[)"'`\]]\s*:|\s:)\s*$/;
const IN_ATTRIBUTE = /\b[\w-]+=\{[^{}]*$/;

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const p = join(dir, name);
    if (statSync(p).isDirectory()) walk(p, out);
    else if (/\.(jsx?|mjs)$/.test(name) && !/\.test\./.test(name)) out.push(p);
  }
  return out;
}

function spokenWaits(source) {
  const found = [];
  for (const m of source.matchAll(/"([^"\\\n]*)"|'([^'\\\n]*)'|`([^`\\]*)`/g)) {
    const text = (m[1] ?? m[2] ?? m[3]).replace(/\$\{[^}]*\}/g, "x");
    const before = source.slice(Math.max(0, m.index - 120), m.index);
    if (ELLIPSIS.test(text) || (BARE.test(text) && SHOWN.test(before) && !IN_ATTRIBUTE.test(before))) found.push(text.trim());
  }
  for (const m of source.matchAll(/(?:>|\})([^<>{}]+)(?=<|\{)/g)) {
    if (LEADS.test(m[1]) && !m[1].includes("=")) found.push(m[1].trim());
  }
  return found;
}

describe("waits never speak in a bare word", () => {
  it.each([
    ['<div>Loading…</div>', true],
    ['<span>loading...</span>', true],
    ['{busy ? "loading…" : value}', true],
    ["{busy ? 'Syncing notifications…' : null}", true],
    ["{`Fetching ${name}…`}", true],
    ['{busy ? "Loading" : value}', true],
    ['{busy ? value : "loading"}', true],
    ['<div>{icon} Loading…</div>', true],
    ['<div>{icon} Loading flow</div>', true],
    ['<span>Loading flow</span>', true],
    ['{ready ? null : "Loading flow"}', true],
    ['<span>Syncing…</span>', true],
    ['{busy && "Fetching…"}', true],
    ['return "Syncing";', true],
    ['<Chip>{busy ? "Loading" : label}</Chip>', true],
    ['<b>Loading</b>', true],
    ['<Busy label="Reaching the daemon" />', false],
    ['<SkeletonRows label="Loading connections" />', false],
    ['aria-label="Loading the pipeline"', false],
    ['`Connected to ${name} — syncing profiles…`', false],
    ['placeholder="Search skills…"', false],
    ['notify({ kind: "loading", key })', false],
    ['const isLoading = ttsKind === "loading";', false],
    ['loadingLabel = "Loading",', false],
    ['{busy ? <Busy label="Loading the pipeline" /> : null}', false],
    ['<div>{count} items loaded</div>', false],
    ['if (state.kind === "loading") return;', false],
    ['const label = busy ? "Read aloud" : "Stop";', false],
    ['<Skeleton label="Loading usage" />', false],
    ['loadingLabel={busy ? "Loading skills" : "Loading skill detail"}', false],
    ['<Button loading={saving} onClick={save}>Save</Button>', false],
    ['notify({ kind: "loading", key, accent });', false],
  ])("classifies %s", (source, flagged) => {
    expect(spokenWaits(source).length > 0).toBe(flagged);
  });

  it("no source under src renders a waiting word on its own", () => {
    const offenders = walk(SRC).flatMap((path) => spokenWaits(readFileSync(path, "utf8")).map((t) => `${relative(SRC, path)}: ${t}`));
    expect(offenders).toEqual([]);
  });
});

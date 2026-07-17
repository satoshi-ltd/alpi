// Deterministic pre-flight audit of dist/ — pixel runs this AFTER `npm run build`
// and BEFORE handoff. It catches MECHANICAL launch-blockers (broken images,
// placeholder domain, missing locales, empty pages) cheaply, so QA (lens) is
// left to EDITORIAL judgment only — not to grep for `<img src="">`. Exits
// non-zero and prints every blocker so pixel can report the exact artifact.
import { readFileSync, existsSync, readdirSync, statSync, renameSync, rmSync } from "node:fs";
import { join } from "node:path";

const DIST = "dist";
const PLACEHOLDER = "example-hotel.com";
const site = JSON.parse(readFileSync("src/config/site.json", "utf8"));
const locales = site.locales || [];
const problems = [];

if (!existsSync(DIST)) {
  console.error("preflight: no dist/ — run `npm run build` first");
  process.exit(2);
}

function walk(dir) {
  const out = [];
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    if (statSync(p).isDirectory()) out.push(...walk(p));
    else if (e.endsWith(".html")) out.push(p);
  }
  return out;
}
const htmls = walk(DIST);

// 1. Structural artifacts present.
for (const f of ["sitemap.xml", "robots.txt"]) {
  if (!existsSync(join(DIST, f))) problems.push(`missing dist/${f}`);
}

// 2. Every declared locale rendered a home page.
for (const l of locales) {
  if (!existsSync(join(DIST, l, "index.html"))) {
    problems.push(`declared locale '${l}' has no dist/${l}/index.html`);
  }
}

// 3. No placeholder domain leaked into robots / sitemap.
for (const f of ["robots.txt", "sitemap.xml"]) {
  const p = join(DIST, f);
  if (existsSync(p) && readFileSync(p, "utf8").includes(PLACEHOLDER)) {
    problems.push(`dist/${f} contains placeholder domain '${PLACEHOLDER}' — set site.json "url" to the real domain`);
  }
}

// i18n namespaces derived from the bundles: a leaked key prints as "ns.key" text
// (useT falls back to the key), so the key itself is by definition NOT in any
// bundle — match by namespace pattern, not by bundle membership.
const I18N_DIR = "src/i18n";
let i18nLeakRe = null;
if (existsSync(I18N_DIR)) {
  const ns = new Set();
  for (const file of readdirSync(I18N_DIR).filter((n) => n.endsWith(".json"))) {
    for (const k of Object.keys(JSON.parse(readFileSync(join(I18N_DIR, file), "utf8")))) {
      const dot = k.indexOf(".");
      if (dot > 0) ns.add(k.slice(0, dot));
    }
  }
  if (ns.size) i18nLeakRe = new RegExp(`\\b(?:${[...ns].join("|")})\\.[A-Za-z][\\w-]*`, "g");
}

// 4. Per-page mechanical checks.
for (const f of htmls) {
  const h = readFileSync(f, "utf8");
  // The root `/index.html` is a redirect to the default locale — NOT an
  // editorial page. It has no <main> and carries no SEO by design; skip the
  // page-level checks for it (its only job is a correct redirect).
  const isRootRedirect = f.replace(/\\/g, "/").slice(DIST.length + 1) === "index.html";
  // 4a. Every <img> has a non-empty src (no broken image tags)…
  for (const tag of h.match(/<img\b[^>]*>/gi) || []) {
    if (!/\bsrc\s*=\s*["'][^"']+["']/i.test(tag)) {
      problems.push(`${f}: <img> without src — ${tag.slice(0, 70)}`);
    } else if (/\balt\s*=\s*["']\s*["']/i.test(tag)) {
      // …and a non-empty alt (content image without alt = a11y blocker). The
      // template derives alts, so this only fires on a regression.
      problems.push(`${f}: <img> with empty alt="" — ${tag.slice(0, 70)}`);
    }
  }
  // 4b. No placeholder domain in canonical / OG / JSON-LD.
  if (h.includes(PLACEHOLDER)) {
    problems.push(`${f}: placeholder domain '${PLACEHOLDER}' in head/canonical/JSON-LD`);
  }
  // 4c. <main> not near-empty: flag only when there's neither real text NOR any
  // visual content. A branded placeholder tile renders a `class="ph"` div (no
  // <img>), so it counts as visual — a placeholder gallery is not "empty".
  // Catches a genuinely empty page (e.g. offers with zero cards). Root redirect
  // exempt (no <main>).
  const m = isRootRedirect ? null : h.match(/<main[^>]*>([\s\S]*?)<\/main>/i);
  if (m) {
    const inner = m[1];
    const text = inner.replace(/<[^>]+>/g, " ").replace(/\s+/g, " ").trim();
    const visual = (inner.match(/<img\b/gi) || []).length
      + (inner.match(/class="ph[\s"]/gi) || []).length;
    if (text.length < 70 && visual === 0) {
      problems.push(`${f}: <main> empty (${text.length} chars, no visual) — unfilled page/section`);
    }
  }
  // 4d. Every internal link resolves to a generated page (no nav 404s, e.g. a
  // nav linking a degraded/ungenerated gallery page).
  for (const mt of h.matchAll(/href\s*=\s*["'](\/[^"'#?]*)/gi)) {
    let p = mt[1].replace(/\/$/, "");
    if (!p || /\.[a-z0-9]+$/i.test(p)) continue; // root or an asset/file (own check)
    const asDir = join(DIST, p, "index.html");
    const asFile = join(DIST, p + ".html");
    if (!existsSync(asDir) && !existsSync(asFile)) {
      problems.push(`${f}: internal link ${mt[1]} resolves to no generated page (dead nav/link)`);
    }
  }
  // 4e. Badge text must not glue "label value" → "labelvalue" (Astro drops the
  // literal space between two {expr}: a letter stuck to a digit, e.g. "Palma700").
  for (const b of h.matchAll(/<span class="badge[^"]*"[^>]*>([\s\S]*?)<\/span>/gi)) {
    const txt = b[1].replace(/<[^>]+>/g, "").replace(/\s+/g, " ").trim();
    if (/[A-Za-zÀ-ÿ][0-9]/.test(txt)) {
      problems.push(`${f}: badge text glued (missing space) — "${txt.slice(0, 40)}"`);
    }
  }
  // 4f. No raw i18n key rendered as visible text (a missing bundle entry makes
  // useT() print the key itself, e.g. "cta.reservar" in the header).
  if (i18nLeakRe && !isRootRedirect) {
    const visible = h
      .replace(/<(script|style)\b[\s\S]*?<\/\1>/gi, " ")
      .replace(/<[^>]+>/g, " ");
    for (const k of new Set(visible.match(i18nLeakRe) || [])) {
      problems.push(`${f}: raw i18n key rendered as text — "${k}" (missing from the locale bundles)`);
    }
  }
  // 4g. Exactly one <h1> per page (heading hierarchy + a11y + SEO).
  if (!isRootRedirect) {
    const h1s = (h.match(/<h1[\s>]/gi) || []).length;
    if (h1s !== 1) problems.push(`${f}: expected exactly one <h1>, found ${h1s}`);
  }
  // 4h. Every anchor href resolves to an id — same-page (#x) or cross-page (/path#x).
  for (const mt of h.matchAll(/href\s*=\s*["']([^"'?]*)#([A-Za-z][\w-]*)["']/gi)) {
    const [, p, frag] = mt;
    if (/^(https?:)?\/\//i.test(p)) continue;
    let target = h;
    if (p) {
      const clean = p.replace(/\/$/, "");
      const asDir = join(DIST, clean, "index.html");
      const asFile = join(DIST, clean + ".html");
      if (existsSync(asDir)) target = readFileSync(asDir, "utf8");
      else if (existsSync(asFile)) target = readFileSync(asFile, "utf8");
      else continue; // dead path is 4d's finding, not 4h's
    }
    if (!new RegExp(`id=["']${frag}["']`).test(target)) {
      problems.push(`${f}: anchor "${p}#${frag}" has no id="${frag}" target`);
    }
  }
}

// 5. Local-first SVGs: assets must be self-contained — no remote fonts/refs/scripts
// (breaks offline, privacy, and reproducibility). The xmlns is not a dependency.
function walkSvg(dir) {
  const out = [];
  for (const e of readdirSync(dir)) {
    const p = join(dir, e);
    if (statSync(p).isDirectory()) out.push(...walkSvg(p));
    else if (e.toLowerCase().endsWith(".svg")) out.push(p);
  }
  return out;
}
// Scan source assets too, not just dist — the build strips @import on optimize,
// so a non-self-contained source logo would otherwise slip the dist-only audit.
for (const root of [DIST, "assets", "public"]) {
  if (!existsSync(root)) continue;
  for (const f of walkSvg(root)) {
    const s = readFileSync(f, "utf8");
    if (/@import|<script|url\(\s*['"]?https?:|(?:href|src)\s*=\s*["']https?:/i.test(s)) {
      problems.push(`${f}: SVG has a remote dependency (@import / remote url / script) — must be self-contained`);
    }
  }
}
// 6. Every /img/ reference in the built HTML resolves to a real file in dist —
// catches a content image path with no materialised asset behind it (not in
// assets.yaml). The gradient/placeholder masks the 404 in the browser, so it's
// otherwise invisible.
const imgRefs = new Set();
for (const f of htmls) {
  for (const mt of readFileSync(f, "utf8").matchAll(/\/img\/[^\s"')]+?\.(?:webp|avif|jpe?g|png|svg|gif)/gi)) {
    imgRefs.add(mt[0]);
  }
}
for (const ref of imgRefs) {
  if (!existsSync(join(DIST, ref))) {
    problems.push(`referenced image ${ref} missing from dist/ — dead <img>: not in assets.yaml, so apply-assets-manifest never materialised it`);
  }
}

// 7. Every materialised image in dist/img is referenced by some page — catches
// the inverse of 6: the image is built but its slot was never wired, so the page
// renders an empty `.ph` placeholder next to an orphaned file. Keyed
// off the real dist files (not the manifest, whose basenames Pixel may rename),
// grouped by stem so a referenced `.webp` covers its `.avif` sibling. SVGs skip —
// a logo may be a text wordmark by design.
const imgDir = join(DIST, "img");
if (existsSync(imgDir)) {
  const refStems = new Set([...imgRefs].map((r) => r.split("/").pop().replace(/\.[^.]+$/, "")));
  const orphans = new Set();
  (function walkAll(dir) {
    for (const e of readdirSync(dir)) {
      const p = join(dir, e);
      if (statSync(p).isDirectory()) walkAll(p);
      else if (/\.(webp|avif|jpe?g|png|gif)$/i.test(e)) {
        const stem = e.replace(/\.[^.]+$/, "");
        if (!refStems.has(stem)) orphans.add(stem);
      }
    }
  })(imgDir);
  for (const stem of orphans) {
    problems.push(`dist/img/${stem}.* materialised but referenced by no page — apply-assets-manifest did not wire its slot (orphaned asset)`);
  }
}

// 8. Hard facts in site.json must come from the brief — an invented domain
// shipped once; these facts are grep-able, so gate them (no brief.md → skip).
if (existsSync("brief.md")) {
  const briefNorm = readFileSync("brief.md", "utf8").replace(/[\s()\-]/g, "").toLowerCase();
  const facts = [];
  if (site.url) { try { facts.push(["url host", new URL(site.url).host]); } catch { facts.push(["url", site.url]); } }
  if (site.contact?.phone) facts.push(["contact.phone", site.contact.phone]);
  if (site.contact?.email) facts.push(["contact.email", site.contact.email]);
  if (site.booking?.propertyId) facts.push(["booking.propertyId", site.booking.propertyId]);
  for (const [name, value] of facts) {
    const norm = String(value).replace(/[\s()\-]/g, "").toLowerCase();
    if (norm && !briefNorm.includes(norm)) {
      problems.push(`site.json ${name} "${value}" does not appear in brief.md — invented facts cannot ship`);
    }
  }
}

// 9. Fixed-layer drift vs the master template — INFORMATIVE (warns, never fails):
// stale-after-upgrade is expected, but an agent-edited component also surfaces here.
import { createHash } from "node:crypto";
const TPL = "../../templates/hotel-web";
const FIXED = ["src/components", "src/layouts", "src/lib", "src/styles", "scripts",
  "src/config/site-schema.ts", "src/config/site.ts", "src/content/config.ts"];
if (existsSync(TPL) && readFileSync("package.json", "utf8") !== "" ) {
  const md5 = (p) => createHash("md5").update(readFileSync(p)).digest("hex");
  const drift = [];
  const walkRel = (root, rel) => {
    const out = [];
    const abs = join(root, rel);
    if (!existsSync(abs)) return out;
    if (statSync(abs).isFile()) return [rel];
    for (const e of readdirSync(abs)) out.push(...walkRel(root, join(rel, e)));
    return out;
  };
  for (const f of FIXED) {
    for (const rel of walkRel(".", f)) {
      const tplFile = join(TPL, rel);
      if (!existsSync(tplFile)) drift.push(`${rel} (not in template)`);
      else if (md5(rel) !== md5(tplFile)) drift.push(rel);
    }
  }
  if (drift.length) {
    console.warn(`preflight WARN · fixed layer differs from the master template (${drift.length} file(s)) — stale upgrade or local edit:`);
    for (const d of drift.slice(0, 10)) console.warn("  ~ " + d);
  }
}

// 10. Supplied photos must not be silently dropped: images in assets/ with no
// assets.yaml means the restore phase was skipped (photos sit unwired).
if (existsSync("assets")) {
  const imgs = readdirSync("assets").filter((f) => /\.(jpe?g|png|webp|avif)$/i.test(f));
  if (imgs.length && !existsSync("assets/assets.yaml")) {
    problems.push(`assets/ has ${imgs.length} supplied photo(s) but no assets.yaml — the restore phase was skipped; muse must triage + wire them (or remove them)`);
  }
}

// 11. Copy minimums on the SOURCE locale — thin copy is a defect (a floor, not
// the target; quill aims higher). Translations vary in length, so source only.
const SRC = site.defaultLocale;
const FLOORS = { room: 50, intro: 40, about: 55, dining: 40 };
const words = (s) => (s || "").trim().split(/\s+/).filter(Boolean).length;
function readJson(p) { try { return JSON.parse(readFileSync(p, "utf8")); } catch { return null; } }
const C = "src/content";
if (existsSync(`${C}/rooms`)) {
  for (const f of readdirSync(`${C}/rooms`).filter((n) => n.endsWith(`.${SRC}.json`))) {
    const d = readJson(`${C}/rooms/${f}`); if (!d) continue;
    const w = words(d.description);
    if (w < FLOORS.room) problems.push(`content thin: rooms/${f} description ${w}w < ${FLOORS.room} (source ${SRC}) — quill must expand with facts`);
  }
}
const homeSrc = `${C}/pages/home.${SRC}.json`;
if (existsSync(homeSrc)) {
  const h = readJson(homeSrc) || {};
  const iw = words(h.intro?.body), aw = words(h.about?.body);
  if (h.intro && iw < FLOORS.intro) problems.push(`content thin: home intro ${iw}w < ${FLOORS.intro} (${SRC})`);
  if (h.about && aw < FLOORS.about) problems.push(`content thin: home about ${aw}w < ${FLOORS.about} (${SRC})`);
}
if (existsSync(`${C}/dining`)) {
  for (const f of readdirSync(`${C}/dining`).filter((n) => n.endsWith(`.${SRC}.json`))) {
    const d = readJson(`${C}/dining/${f}`); if (!d) continue;
    const w = words(d.description);
    if (d.description && w < FLOORS.dining) problems.push(`content thin: dining/${f} description ${w}w < ${FLOORS.dining} (${SRC})`);
  }
}

// 12. booking.propertyId is empty OR a numeric Mirai id — never a hotel name or
// placeholder string (those silently fall back to the demo and mislead).
const pid = (site.booking?.propertyId ?? "").trim();
if (pid && !/^\d{4,}$/.test(pid)) {
  problems.push(`booking.propertyId "${pid}" is not a numeric Mirai id — set the real id or leave it empty (never the hotel name / a placeholder)`);
}

// 13. Materialised images stay under the byte budget. Atlas owns the number in
// performance/budget.yaml; per-slot caps aren't filename-detectable, so the hero
// cap is the universal ceiling — it catches real bloat without false-failing.
let imgCapKb = 200;
if (existsSync("performance/budget.yaml")) {
  const mm = readFileSync("performance/budget.yaml", "utf8").match(/hero_max_kb:\s*(\d+)/);
  if (mm) imgCapKb = parseInt(mm[1], 10);
}
(function walkImgs(dir) {
  if (!existsSync(dir)) return;
  for (const e of readdirSync(dir)) {
    const fp = join(dir, e);
    if (statSync(fp).isDirectory()) { walkImgs(fp); continue; }
    if (!/\.(webp|avif|jpe?g|png)$/i.test(e)) continue;
    const kb = statSync(fp).size / 1024;
    if (kb > imgCapKb) problems.push(`image over budget: ${fp.slice(DIST.length)} ${Math.round(kb)}KB > ${imgCapKb}KB — source too large; muse re-exports smaller (or raise budget.yaml hero_max_kb)`);
  }
})(join(DIST, "img"));

// De-dup (the same dead link recurs across locales/pages).
const seen = new Set();
const unique = problems.filter((p) => (seen.has(p) ? false : seen.add(p)));
problems.length = 0;
problems.push(...unique);

if (problems.length) {
  console.error(`PREFLIGHT FAIL · ${problems.length} blocker(s):`);
  for (const p of problems) console.error("  - " + p);
  // Quarantine: a red preflight leaves NO dist/, so the hub's disk-is-truth check cannot close the build phase over a failed gate.
  const rejected = DIST.replace(/\/?$/, "") + ".rejected";
  rmSync(rejected, { recursive: true, force: true });
  renameSync(DIST, rejected);
  console.error(`dist/ quarantined → ${rejected} — fix the blockers and re-run npm run ship`);
  process.exit(1);
}
console.log(`preflight OK · ${htmls.length} pages · locales ${locales.join(",")} · no mechanical blockers`);

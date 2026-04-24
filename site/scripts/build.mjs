#!/usr/bin/env node
// Build script for the alpi site. Zero runtime dependencies.
// Reads docs at HEAD from the repo and bakes a static site into site/dist/.

import { readFileSync, writeFileSync, mkdirSync, rmSync, readdirSync, copyFileSync, existsSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { renderMarkdown } from './markdown.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SITE = resolve(__dirname, '..');
const REPO = resolve(SITE, '..');
const DIST = join(SITE, 'dist');
const TPL  = join(SITE, 'templates');

// ── deploy metadata (override with env vars on CI if needed) ────────────────
const SITE_URL    = (process.env.SITE_URL    || 'https://alpi.satoshi-ltd.com').replace(/\/+$/, '');
const SITE_NAME   = process.env.SITE_NAME   || 'alpi';
const SITE_TAGLINE = 'your private agent network';
const SITE_DESCRIPTION = "alpi starts as the agent in your terminal, then grows with you: profiles for work, cron, home servers, research, and rooms with other alpis. Each profile owns its memory, keys, model, skills, gateways, approvals, and trust boundary. ALP links them across machines without a registry, hub, account, or mandatory cloud.";
const OG_IMAGE = `${SITE_URL}/assets/alpi-brand.png`;
const OG_IMAGE_W = 1200;
const OG_IMAGE_H = 800;
const TWITTER     = '@soyjavi';

// ── version (single source of truth: pyproject.toml) ─────────────────────────
const pyproject = readFileSync(join(REPO, 'pyproject.toml'), 'utf8');
const VERSION = (pyproject.match(/^version\s*=\s*"([^"]+)"/m) || [null, '0.0.0'])[1];

// ── doc metadata ─────────────────────────────────────────────────────────────
// Order drives prev/next pager and the docs index.
const DOCS = [
  { slug: 'README',       src: 'README.md',             ix: '01', category: 'intro',     sub: "Start here. The public thesis: local-first, user-owned agent infrastructure." },
  { slug: 'QUICKSTART',   src: 'QUICKSTART.md',         ix: '02', category: 'guide',     sub: 'Install, pick a model, pin a workspace, send a first message, and check health.' },
  { slug: 'PROFILES',     src: 'docs/PROFILES.md',      ix: '03', category: 'guide',     sub: 'The isolation primitive: identity, keys, memory, skills, peers, gateways, and cost.' },
  { slug: 'SKILLS',       src: 'docs/SKILLS.md',        ix: '04', category: 'guide',     sub: 'Directory contract, frontmatter, scanner, validation, secrets, and bundled namespace.' },
  { slug: 'MODELS',       src: 'docs/MODELS.md',        ix: '05', category: 'guide',     sub: 'Model tiers for tool-heavy agent use: quality, cost/service, and local Ollama.' },
  { slug: 'ALP',          src: 'docs/ALP.md',           ix: '06', category: 'reference', sub: 'Alpi Link Protocol: pinned identity, signed envelopes, peer capabilities, rooms.' },
  { slug: 'ARCHITECTURE', src: 'docs/ARCHITECTURE.md',  ix: '07', category: 'reference', sub: 'Code structure, turn loop, memory, sessions, gateway, scheduler, MCP, logging.' },
  { slug: 'CONFIG',       src: 'docs/CONFIG.md',        ix: '08', category: 'reference', sub: 'Every YAML knob, its default, what it controls.' },
  { slug: 'SECURITY',     src: 'docs/SECURITY.md',      ix: '09', category: 'reference', sub: 'Two-layer security model. Approval system, SSRF, prompt-injection, sensitive paths. Sandbox.' },
  { slug: 'DEPLOYMENTS',  src: 'docs/DEPLOYMENTS.md',   ix: '10', category: 'ops',       sub: 'launchd on macOS, systemd on Linux. Gateway daemon, schedule daemon, keep-alive, logs.' },
  { slug: 'OPERATIONS',   src: 'docs/OPERATIONS.md',    ix: '11', category: 'ops',       sub: 'Day-2 runbook. Doctor, diagnostics, log rotation, backup, recovery, upgrade.' },
  { slug: 'LICENSE',      src: 'LICENSE',               ix: '12', category: 'legal',     sub: 'Legal terms for the source-available agent core and Apache-2.0 Alpi Link Protocol.', raw: true },
  { slug: 'ROADMAP',      src: 'docs/ROADMAP.md',       ix: '13', category: 'planning',  sub: 'Open release gates, ALP launch work, long-term bets, and discarded decisions.' },
  { slug: 'CHANGELOG',    src: 'CHANGELOG.md',          ix: '14', category: 'log',       sub: 'Version-by-version log of user-visible changes since v0.1.' },
];
const TOTAL = DOCS.length;

// ── SEO head block — identical shape across every page, just data differs ─
// kind: 'landing' | 'docs-index' | 'doc'
function renderHead({ kind, title, description, path, iconPath }) {
  const canonical = `${SITE_URL}${path}`;
  const ogType = kind === 'doc' ? 'article' : 'website';
  const structuredData = renderJsonLd({ kind, title, description, canonical });
  return `<meta charset="utf-8" />
<title>${escapeHtml(title)}</title>
<meta name="description" content="${escapeAttr(description)}" />
<meta name="author" content="Satoshi Ltd." />
<meta name="theme-color" content="#0a0a0a" />
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1" />
<meta name="generator" content="${SITE_NAME} static build" />
<link rel="canonical" href="${canonical}" />
<link rel="icon" href="${iconPath}" type="image/svg+xml" />
<link rel="mask-icon" href="${iconPath}" color="#0a0a0a" />

<!-- Open Graph -->
<meta property="og:type" content="${ogType}" />
<meta property="og:site_name" content="${SITE_NAME}" />
<meta property="og:title" content="${escapeAttr(title)}" />
<meta property="og:description" content="${escapeAttr(description)}" />
<meta property="og:url" content="${canonical}" />
<meta property="og:locale" content="en_US" />
<meta property="og:image" content="${OG_IMAGE}" />
<meta property="og:image:secure_url" content="${OG_IMAGE}" />
<meta property="og:image:type" content="image/png" />
<meta property="og:image:width" content="${OG_IMAGE_W}" />
<meta property="og:image:height" content="${OG_IMAGE_H}" />
<meta property="og:image:alt" content="alpi — your private agent network" />

<!-- Twitter -->
<meta name="twitter:card" content="summary_large_image" />
<meta name="twitter:title" content="${escapeAttr(title)}" />
<meta name="twitter:description" content="${escapeAttr(description)}" />
<meta name="twitter:image" content="${OG_IMAGE}" />
<meta name="twitter:image:alt" content="alpi — your private agent network" />
<meta name="twitter:creator" content="${TWITTER}" />
<meta name="twitter:site" content="${TWITTER}" />

${structuredData}`;
}

function escapeHtml(s) {
  return String(s).replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}
function escapeAttr(s) {
  return escapeHtml(s).replace(/"/g, '&quot;');
}

// ── JSON-LD structured data ─────────────────────────────────────────────────
function renderJsonLd({ kind, title, description, canonical }) {
  const organization = {
    '@type': 'Organization',
    name: 'Satoshi Ltd.',
    url: 'https://www.satoshi-ltd.com/',
  };

  if (kind === 'landing') {
    const blocks = [
      {
        '@context': 'https://schema.org',
        '@type': 'WebSite',
        name: SITE_NAME,
        alternateName: 'alpi agent',
        url: SITE_URL,
        description: SITE_DESCRIPTION,
        publisher: organization,
      },
      {
        '@context': 'https://schema.org',
        '@type': 'SoftwareApplication',
        name: 'alpi',
        applicationCategory: 'DeveloperApplication',
        operatingSystem: 'macOS, Linux',
        description: SITE_DESCRIPTION,
        url: SITE_URL,
        softwareVersion: VERSION,
        license: 'https://mariadb.com/bsl11/',
        author: organization,
        publisher: organization,
        offers: {
          '@type': 'Offer',
          price: '0',
          priceCurrency: 'USD',
        },
      },
    ];
    return blocks.map(b => `<script type="application/ld+json">${JSON.stringify(b)}</script>`).join('\n');
  }

  if (kind === 'docs-index') {
    const data = {
      '@context': 'https://schema.org',
      '@type': 'CollectionPage',
      name: title,
      description,
      url: canonical,
      isPartOf: { '@type': 'WebSite', name: SITE_NAME, url: SITE_URL },
      publisher: organization,
    };
    return `<script type="application/ld+json">${JSON.stringify(data)}</script>`;
  }

  // kind === 'doc'
  const data = {
    '@context': 'https://schema.org',
    '@type': 'TechArticle',
    headline: title,
    description,
    url: canonical,
    inLanguage: 'en',
    isPartOf: { '@type': 'WebSite', name: SITE_NAME, url: SITE_URL },
    author: organization,
    publisher: organization,
  };
  return `<script type="application/ld+json">${JSON.stringify(data)}</script>`;
}

// ── alpi logo (alpaca + wordmark, inlined into the nav) ───────────────────
const logoSvg = (() => {
  const src = readFileSync(join(SITE, 'assets', 'alpi-logo.svg'), 'utf8');
  return src
    .replace(/<\?xml[^?]*\?>\s*/i, '')
    .replace(/<svg\b[^>]*>/i, '<svg class="logo" role="img" aria-label="alpi" xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1319 587" fill="currentColor">')
    .trim();
})();

// ── shared nav component — identical markup on landing + docs + doc pages ──
// kind: 'landing' | 'docs-index' | 'doc'
// opts.current (doc pages): the slug shown as current crumb
// opts.brandHref: link for the brand chip (home-of-section)
function renderNav(kind, opts = {}) {
  const crumbs = [];
  let brandHref;
  let showMenu = false;

  if (kind === 'landing') {
    brandHref = 'index.html';
    showMenu = true;
  } else if (kind === 'docs-index') {
    brandHref = '../index.html';
    // On /docs/ the DOCS crumb is current AND keeps the bold+highlight
    // "docs-link" treatment so the section label always reads the same way.
    crumbs.push({ label: 'DOCS', current: true, docs: true });
  } else if (kind === 'doc') {
    brandHref = '../index.html';
    crumbs.push({ label: 'DOCS', href: 'index.html', docs: true });
    crumbs.push({ label: opts.current, current: true });
  }

  const crumbsHtml = crumbs.length
    ? `<span class="bp-tail">${crumbs.map(c => {
        const sep = '<span class="bp-sep">/</span>';
        const extra = c.docs ? ' bp-docs' : '';
        const seg = c.current
          ? `<span class="bp-seg bp-current${extra}">${c.label}</span>`
          : `<a href="${c.href}" class="bp-seg${extra}">${c.label}</a>`;
        return sep + seg;
      }).join('')}</span>`
    : '';

  const menuLinks = [
    ['#what', 'What'],
    ['#quickstart', 'Quickstart'],
    ['#alp', 'ALP'],
    ['#deployments', 'Deploy'],
    ['docs/index.html', 'Docs'],
  ];
  const menuHtml = showMenu
    ? `<ul class="nav-menu">${menuLinks.map(([h, l]) => `<li><a href="${h}">${l}</a></li>`).join('')}</ul>`
    : '';
  const burgerHtml = showMenu
    ? `<button class="burger" aria-label="Menu" aria-controls="nav-drawer" aria-expanded="false"><span></span><span></span><span></span></button>`
    : '';
  const drawerHtml = showMenu
    ? `<div class="nav-drawer" id="nav-drawer" hidden>
    <ul>${menuLinks.map(([h, l]) => `<li><a href="${h}">${l}</a></li>`).join('')}</ul>
    <a href="#install" class="nav-cta">$ uv tool install alpi →</a>
  </div>`
    : '';

  const ctaHref = kind === 'landing' ? '#install' : '../index.html#install';

  return `<nav class="top">
  <div class="shell row">
    <div class="brand-lockup">
      <a class="brand" href="${brandHref}" aria-label="alpi — home">
        ${logoSvg}
      </a>${crumbsHtml}
    </div>
    ${menuHtml}
    <a href="${ctaHref}" class="nav-cta">$ uv tool install alpi →</a>
    ${burgerHtml}
  </div>
  ${drawerHtml}
</nav>`;
}

// ── shared docs grid — used by the landing "docs" section and /docs/ ─────
// `hrefPrefix`: '' when emitted on /docs/index.html (already inside docs/),
//               'docs/' when emitted on the landing page.
// `withSection`: if true, wraps in the <section id="docs"> landing block
//               with eyebrow + heading. If false, just the grid (for /docs/).
function renderDocsGrid({ hrefPrefix = '', withSection = false, eyebrow, heading, sub } = {}) {
  const cards = DOCS.map(d =>
    `      <a class="doc" href="${hrefPrefix}${d.slug}.html">
        <span class="ix">${d.ix} · ${d.category}</span>
        <h4>${d.slug}.md</h4>
        <p>${d.sub}</p>
        <span class="go">read →</span>
      </a>`
  ).join('\n');

  const grid = `    <div class="docs" style="grid-template-columns:repeat(4,1fr)">
${cards}
    </div>`;

  if (!withSection) return grid;

  return `<section id="docs">
  <div class="shell">
    <div class="eyebrow">${eyebrow}</div>
    <h2>${heading}</h2>
    <p class="sub">${sub}</p>
${grid}
  </div>
</section>`;
}

// ── helpers ──────────────────────────────────────────────────────────────────
function ensureDir(p) { mkdirSync(p, { recursive: true }); }
function write(p, content) { ensureDir(dirname(p)); writeFileSync(p, content); }
function copyTree(srcDir, destDir) {
  ensureDir(destDir);
  for (const name of readdirSync(srcDir)) {
    const s = join(srcDir, name), d = join(destDir, name);
    if (statSync(s).isDirectory()) copyTree(s, d);
    else copyFileSync(s, d);
  }
}

// Rewrites intra-doc markdown links: .md → .html; keeps anchors; external untouched.
function linkRewrite(url) {
  if (/^(https?:|mailto:|#|\/)/.test(url)) return url;
  // Strip leading ../ segments; keep just the basename.
  const clean = url.replace(/^(\.\/|\.\.\/)+/, '').replace(/^docs\//, '');
  const [path, hash = ''] = clean.split('#');
  const base = path.replace(/\.md$/i, '');
  const known = DOCS.find(d => d.slug.toLowerCase() === base.toLowerCase());
  if (known) return known.slug + '.html' + (hash ? '#' + hash : '');
  return url;
}

// Strip YAML front-matter if present (some docs may grow it later).
function stripFrontmatter(src) {
  if (src.startsWith('---\n')) {
    const end = src.indexOf('\n---\n', 4);
    if (end !== -1) return src.slice(end + 5);
  }
  return src;
}

// Strip the first H1 — the page header already shows the title.
function stripFirstH1(src) {
  return src.replace(/^#\s+.+\n+/, '');
}

// ── doc page template ────────────────────────────────────────────────────────
function docPage(doc, bodyHtml, prev, next) {
  return `<!doctype html>
<html lang="en">
<head>
${renderHead({
  kind: 'doc',
  title: `${doc.slug} — alpi docs`,
  description: `${doc.sub} Part of the alpi documentation (${doc.ix}/${String(TOTAL).padStart(2,'0')}, ${doc.category}). v${VERSION}.`,
  path: `/docs/${doc.slug}.html`,
  iconPath: '../assets/alpi-alpaca.svg',
})}
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@300;400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../doc.css" />
</head>
<body>
<canvas id="ascii-bg" aria-hidden="true"></canvas>
<div class="veil"></div>

${renderNav('doc', { current: doc.slug })}

<main class="shell doc">
  <header class="dochead">
    <h1>${doc.slug}</h1>
    <p class="sub">${doc.sub}</p>
    <div class="meta mono">
      <span>${doc.ix} / ${String(TOTAL).padStart(2, '0')}</span><span class="d">·</span><span>${doc.category}</span><span class="d">·</span><span>v${VERSION}</span>
    </div>
  </header>

  <article id="md-target" class="md">
${bodyHtml}
  </article>

  <nav class="pager">
    ${prev
      ? `<a class="pg prev" href="${prev.slug}.html"><span class="lbl">← ${prev.ix}</span><span class="tt">${prev.slug}</span></a>`
      : `<a class="pg prev" href="index.html"><span class="lbl">← back</span><span class="tt">all docs</span></a>`}
    ${next
      ? `<a class="pg next" href="${next.slug}.html"><span class="lbl">${next.ix} →</span><span class="tt">${next.slug}</span></a>`
      : `<a class="pg next" href="index.html"><span class="lbl">index →</span><span class="tt">all docs</span></a>`}
  </nav>
</main>

<script src="../doc.js"></script>
</body>
</html>
`;
}

// ── docs index (same card grid as the landing "docs" section) ──────────────
function docsIndexPage() {
  return `<!doctype html>
<html lang="en">
<head>
${renderHead({
  kind: 'docs-index',
  title: 'alpi docs — documentation index',
  description: `Complete documentation for alpi v${VERSION}: ${TOTAL} references covering quickstart, skills, profiles, models, architecture, security, deployments, the Alpi Link Protocol, and more.`,
  path: '/docs/',
  iconPath: '../assets/alpi-alpaca.svg',
})}
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@300;400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../doc.css" />
</head>
<body>
<canvas id="ascii-bg" aria-hidden="true"></canvas>
<div class="veil"></div>

${renderNav('docs-index')}

<main class="shell shell-wide docs-index">
${renderDocsGrid({
  hrefPrefix: '',
  withSection: true,
  eyebrow: `v${VERSION} · ${TOTAL} documents · updated ${new Date().toISOString().slice(0, 7)}`,
  heading: 'DOCS',
  sub: "Every doc is a reference of something that already ships. Read in order for the full picture, or jump to what you need — historical decisions live in commits, planned work in the ROADMAP.",
})}
</main>

<script src="../doc.js"></script>
</body>
</html>
`;
}

// ── runtime JS (drops renderDoc — docs are pre-rendered at build) ──────────
const runtimeJs = (() => {
  const full = readFileSync(join(TPL, 'doc.js'), 'utf8');
  // Keep everything up to the async function renderDoc declaration.
  const idx = full.indexOf('async function renderDoc');
  return idx === -1 ? full : full.slice(0, idx).trimEnd() + '\n';
})();

// ── build ────────────────────────────────────────────────────────────────────
console.log(`alpi site build — v${VERSION}`);

// Clean dist
if (existsSync(DIST)) rmSync(DIST, { recursive: true });
ensureDir(DIST);

// Assets
copyTree(join(SITE, 'assets'), join(DIST, 'assets'));

// Shared doc.css + baked doc.js
copyFileSync(join(TPL, 'doc.css'), join(DIST, 'doc.css'));
writeFileSync(join(DIST, 'doc.js'), runtimeJs);

// Landing — inject head, shared nav + docs grid, rewrite version refs
const landingHead = renderHead({
  kind: 'landing',
  title: `alpi — ${SITE_TAGLINE}`,
  description: SITE_DESCRIPTION,
  path: '/',
  iconPath: 'assets/alpi-alpaca.svg',
});
const landing = readFileSync(join(TPL, 'landing.html'), 'utf8')
  .replace('<meta charset="utf-8" />\n<!-- SEO_HEAD (injected by build.mjs) -->', landingHead)
  .replace('<!-- NAV (injected by build.mjs) -->', renderNav('landing'))
  .replace('<!-- DOCS_GRID_PLACEHOLDER -->', renderDocsGrid({ hrefPrefix: 'docs/' }))
  // Match any v<semver> in the landing template so the hero, terminal
  // chrome, and footer all track pyproject.toml regardless of which
  // version the template was last saved with.
  .replace(/\bv\d+\.\d+\.\d+\b/g, `v${VERSION}`);
write(join(DIST, 'index.html'), landing);

// Docs index
write(join(DIST, 'docs', 'index.html'), docsIndexPage());

// Each doc
for (let k = 0; k < DOCS.length; k++) {
  const doc = DOCS[k];
  const srcPath = join(REPO, doc.src);
  if (!existsSync(srcPath)) {
    console.warn(`  skip ${doc.slug} — missing ${doc.src}`);
    continue;
  }
  const raw = readFileSync(srcPath, 'utf8');
  let body;
  if (doc.raw) {
    body = `<pre><code>${raw.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')}</code></pre>`;
  } else {
    body = renderMarkdown(stripFirstH1(stripFrontmatter(raw)), { linkRewrite });
  }
  const prev = DOCS[k - 1] || null;
  const next = DOCS[k + 1] || null;
  write(join(DIST, 'docs', `${doc.slug}.html`), docPage(doc, body, prev, next));
  console.log(`  ${doc.ix}  ${doc.slug.padEnd(14)} ← ${doc.src}`);
}

// sitemap.xml — discoverable URL list for crawlers
const today = new Date().toISOString().slice(0, 10);
const sitemapUrls = [
  { loc: `${SITE_URL}/`, priority: '1.0', changefreq: 'weekly' },
  { loc: `${SITE_URL}/docs/`, priority: '0.9', changefreq: 'weekly' },
  ...DOCS.map(d => ({
    loc: `${SITE_URL}/docs/${d.slug}.html`,
    priority: '0.8',
    changefreq: 'weekly',
  })),
];
const sitemapXml = `<?xml version="1.0" encoding="UTF-8"?>
<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
${sitemapUrls.map(u => `  <url>
    <loc>${u.loc}</loc>
    <lastmod>${today}</lastmod>
    <changefreq>${u.changefreq}</changefreq>
    <priority>${u.priority}</priority>
  </url>`).join('\n')}
</urlset>
`;
write(join(DIST, 'sitemap.xml'), sitemapXml);

// robots.txt — allow all, point at sitemap
const robotsTxt = `User-agent: *
Allow: /

Sitemap: ${SITE_URL}/sitemap.xml
`;
write(join(DIST, 'robots.txt'), robotsTxt);

console.log(`  sitemap.xml (${sitemapUrls.length} urls)`);
console.log(`  robots.txt`);
console.log(`done → ${DIST}`);

#!/usr/bin/env node
// Build script for the alpi site. Zero runtime dependencies.
// Reads docs at HEAD from the repo and bakes a static site into site/dist/.

import { readFileSync, writeFileSync, mkdirSync, rmSync, readdirSync, copyFileSync, existsSync, statSync } from 'node:fs';
import { dirname, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { renderMarkdown, parseFrontmatter } from './markdown.mjs';

const __dirname = dirname(fileURLToPath(import.meta.url));
const SITE = resolve(__dirname, '..');
const REPO = resolve(SITE, '..');
const DIST = join(SITE, 'dist');
const TPL  = join(SITE, 'templates');

// ── deploy metadata (override with env vars on CI if needed) ────────────────
const SITE_URL    = (process.env.SITE_URL    || 'https://alpi.satoshi-ltd.com').replace(/\/+$/, '');
const SITE_NAME   = process.env.SITE_NAME   || 'alpi';
const SITE_TAGLINE = 'your private agent network';
const SITE_DESCRIPTION = "alpi is a daemon you run, with terminal, desktop, and mobile clients on top. Profiles isolate memory, keys, models, skills, schedules, approvals, and trust. ALP links your alpis across machines without a registry, central account, or mandatory cloud.";
// 1200×630 — standard OG / Twitter card ratio. Crops cleanly on Twitter, Slack, LinkedIn and Discord previews.
const OG_IMAGE = `${SITE_URL}/assets/alpi-social.png`;
const OG_IMAGE_W = 1200;
const OG_IMAGE_H = 630;
const TWITTER     = '@soyjavi';

// ── version (single source of truth: pyproject.toml) ─────────────────────────
const pyproject = readFileSync(join(REPO, 'pyproject.toml'), 'utf8');
const VERSION = (pyproject.match(/^version\s*=\s*"([^"]+)"/m) || [null, '0.0.0'])[1];

// Desktop version travels separately (released on its own cadence as
// `desktop-vX.Y.Z`). Source of truth: tauri.conf.json — package.json
// and src-tauri/Cargo.toml track the same value but the workflow's
// gate verifies they're aligned.
const tauriConf = readFileSync(join(REPO, 'desktop/src-tauri/tauri.conf.json'), 'utf8');
const DESKTOP_VERSION = JSON.parse(tauriConf).version;
const DESKTOP_DOWNLOAD_URL = 'https://github.com/satoshi-ltd/alpi/releases/download/desktop-latest/alpi-latest.dmg';
const DESKTOP_RELEASES_URL = `https://github.com/satoshi-ltd/alpi/releases/tag/desktop-v${DESKTOP_VERSION}`;

// ── doc metadata ─────────────────────────────────────────────────────────────
// Order drives prev/next pager and the docs index.
const DOCS = [
  { slug: 'README',       src: 'README.md',             ix: '01', category: 'intro',     sub: "Start here. The public thesis: local-first, user-owned agent infrastructure." },
  { slug: 'INSTALL',      src: 'docs/INSTALL.md',       ix: '02', category: 'guide',     sub: 'Install methods (uv, pipx, dev), update path, uninstall, troubleshooting, supported platforms.' },
  { slug: 'QUICKSTART',   src: 'QUICKSTART.md',         ix: '03', category: 'guide',     sub: 'Install, pick a model, pin a workspace, send a first message, and check health.' },
  { slug: 'PROFILES',     src: 'docs/PROFILES.md',      ix: '04', category: 'guide',     sub: 'The isolation primitive: identity, keys, memory, skills, peers, gateways, and cost.' },
  { slug: 'SKILLS',       src: 'docs/SKILLS.md',        ix: '05', category: 'guide',     sub: 'Directory contract, frontmatter, scanner, validation, secrets, and bundled namespace.' },
  { slug: 'MODELS',       src: 'docs/MODELS.md',        ix: '06', category: 'guide',     sub: 'Model tiers for tool-heavy agent use: quality, cost/service, and local Ollama.' },
  { slug: 'ALP',          src: 'docs/ALP.md',           ix: '07', category: 'reference', sub: 'Alpi Link Protocol: pinned identity, signed envelopes, peer capabilities, workgroups.' },
  { slug: 'ARCHITECTURE', src: 'docs/ARCHITECTURE.md',  ix: '08', category: 'reference', sub: 'Code structure, turn loop, memory, sessions, gateway, scheduler, MCP, logging.' },
  { slug: 'CONFIG',       src: 'docs/CONFIG.md',        ix: '09', category: 'reference', sub: 'Every YAML knob, its default, what it controls.' },
  { slug: 'SECURITY',     src: 'docs/SECURITY.md',      ix: '10', category: 'reference', sub: 'Two-layer security model. Approval system, SSRF, prompt-injection, sensitive paths. Sandbox.' },
  { slug: 'DEPLOYMENTS',  src: 'docs/DEPLOYMENTS.md',   ix: '11', category: 'ops',       sub: 'launchd on macOS, systemd on Linux. Gateway daemon, schedule daemon, keep-alive, logs.' },
  { slug: 'OPERATIONS',   src: 'docs/OPERATIONS.md',    ix: '12', category: 'ops',       sub: 'Day-2 runbook. Doctor, diagnostics, log rotation, backup, recovery, upgrade.' },
  { slug: 'LICENSE',      src: 'LICENSE',               ix: '13', category: 'legal',     sub: 'Legal terms for the source-available agent core and Apache-2.0 Alpi Link Protocol.', raw: true },
  { slug: 'ORGANIZATION', src: 'docs/ORGANIZATION.md',  ix: '14', category: 'guide',     sub: '17-agent company scaffold built on ALP: roles, workgroups, 51 skills, and a one-command bootstrap.' },
  { slug: 'ROADMAP',      src: 'docs/ROADMAP.md',       ix: '15', category: 'planning',  sub: 'Open release gates, ALP launch work, long-term bets, and discarded decisions.' },
  { slug: 'CHANGELOG',    src: 'CHANGELOG.md',          ix: '16', category: 'log',       sub: 'Version-by-version log of user-visible changes since v0.1.' },
];
const TOTAL = DOCS.length;

// ── blog posts ───────────────────────────────────────────────────────────────
// Auto-discovered from site/posts/*.md — no manual registry. Drop a markdown
// file with front-matter (title, date, description, tags, draft?) and it
// publishes on the next build. `draft: true` is skipped.
const POSTS_DIR = join(SITE, 'posts');
function loadPosts() {
  if (!existsSync(POSTS_DIR)) return [];
  const out = [];
  for (const name of readdirSync(POSTS_DIR)) {
    if (!name.endsWith('.md')) continue;
    const raw = readFileSync(join(POSTS_DIR, name), 'utf8');
    const { meta, body } = parseFrontmatter(raw);
    if (meta.draft === true) continue;
    const slug = name.replace(/\.md$/, '');
    const h1 = body.match(/^#\s+(.+?)\s*$/m);
    const title = meta.title || (h1 && h1[1]) || slug;
    out.push({
      slug,
      title,
      date: meta.date || '',
      description: meta.description || '',
      tags: Array.isArray(meta.tags) ? meta.tags : [],
      body,
    });
  }
  // Newest first; ISO dates sort lexically, undated posts sink to the bottom.
  out.sort((a, b) => (b.date || '').localeCompare(a.date || ''));
  return out;
}
const POSTS = loadPosts();

// ── SEO head block — identical shape across every page, just data differs ─
// kind: 'landing' | 'docs-index' | 'doc'
function renderHead({ kind, title, description, path, iconPath, date }) {
  const canonical = `${SITE_URL}${path}`;
  const ogType = (kind === 'doc' || kind === 'post') ? 'article' : 'website';
  const structuredData = renderJsonLd({ kind, title, description, canonical, date });
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
function renderJsonLd({ kind, title, description, canonical, date }) {
  const opts = { date };
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
        operatingSystem: 'macOS, Linux, Windows',
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

  if (kind === 'docs-index' || kind === 'blog-index') {
    const data = {
      '@context': 'https://schema.org',
      '@type': kind === 'blog-index' ? 'Blog' : 'CollectionPage',
      name: title,
      description,
      url: canonical,
      isPartOf: { '@type': 'WebSite', name: SITE_NAME, url: SITE_URL },
      publisher: organization,
    };
    return `<script type="application/ld+json">${JSON.stringify(data)}</script>`;
  }

  if (kind === 'post') {
    const data = {
      '@context': 'https://schema.org',
      '@type': 'BlogPosting',
      headline: title,
      description,
      url: canonical,
      inLanguage: 'en',
      ...(opts.date ? { datePublished: opts.date } : {}),
      isPartOf: { '@type': 'Blog', name: `${SITE_NAME} blog`, url: `${SITE_URL}/blog/` },
      author: organization,
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

// ── alpi logo (llama + wordmark, inlined into the nav) ─────────────────────
function inlineLogoPart(fileName, className, attrs = '') {
  const src = readFileSync(join(SITE, 'assets', fileName), 'utf8');
  return src
    .replace(/<\?xml[^?]*\?>\s*/i, '')
    .replace(/<svg\b/i, `<svg class="${className}" ${attrs} aria-hidden="true" focusable="false"`)
    .trim();
}

const logoSvg = `<span class="logo">${inlineLogoPart('alpi-white.svg', 'logo-mark', 'width="35" height="40"')}<span class="logo-word">alpi</span></span>`;
const themeControlHtml = `<div class="bg-ctrl" role="group" aria-label="theme">
  <span>theme</span>
  <button data-theme="dark" class="on">dark</button>
  <button data-theme="light">light</button>
</div>`;
const GITHUB_URL = 'https://github.com/satoshi-ltd/alpi';
const githubIcon = `<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path fill="currentColor" d="M8 0C3.58 0 0 3.67 0 8.2c0 3.62 2.29 6.69 5.47 7.78.4.08.55-.18.55-.4l-.01-1.52c-2.23.5-2.7-1.1-2.7-1.1-.36-.95-.89-1.2-.89-1.2-.73-.51.06-.5.06-.5.8.06 1.23.85 1.23.85.72 1.26 1.88.9 2.34.68.07-.53.28-.9.51-1.1-1.78-.21-3.64-.91-3.64-4.04 0-.9.31-1.62.82-2.2-.08-.21-.36-1.04.08-2.17 0 0 .68-.22 2.2.84A7.42 7.42 0 0 1 8 3.84c.68 0 1.36.09 1.99.28 1.52-1.06 2.2-.84 2.2-.84.44 1.13.16 1.96.08 2.17.51.58.82 1.31.82 2.2 0 3.14-1.87 3.83-3.65 4.03.29.26.54.76.54 1.53l-.01 2.37c0 .22.14.48.55.4A8.12 8.12 0 0 0 16 8.2C16 3.67 12.42 0 8 0Z"/></svg>`;

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
  } else if (kind === 'apps') {
    // Subpage at the site root — brand goes to landing, crumb shows the section.
    brandHref = 'index.html';
    crumbs.push({ label: 'APPS', current: true, docs: true });
  } else if (kind === 'blog-index') {
    brandHref = '../index.html';
    crumbs.push({ label: 'BLOG', current: true, docs: true });
  } else if (kind === 'blog') {
    brandHref = '../index.html';
    crumbs.push({ label: 'BLOG', href: 'index.html', docs: true });
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

  // Menu is only rendered on the landing — paths are relative to the site root.
  const menuLinks = [
    ['#what', 'What'],
    ['#quickstart', 'Quickstart'],
    ['apps.html', 'Apps'],
    ['#alp', 'ALP'],
    ['docs/index.html', 'Docs'],
    ['blog/index.html', 'Blog'],
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
    <a href="#install" class="nav-cta">$ uv tool install alpi-agent →</a>
  </div>`
    : '';

  // CTA install anchor lives on the landing — point at it correctly from each surface.
  const ctaHref = kind === 'landing' ? '#install'
    : kind === 'apps' ? 'index.html#install'
    : '../index.html#install';

  return `<nav class="top">
  <div class="shell row">
    <div class="brand-lockup">
      <a class="brand" href="${brandHref}" aria-label="alpi — home">
        ${logoSvg}
      </a>${crumbsHtml}
    </div>
    ${menuHtml}
    <div class="nav-actions">
      <a href="${GITHUB_URL}" class="nav-github" aria-label="alpi on GitHub">${githubIcon}</a>
      <a href="${ctaHref}" class="nav-cta">$ uv tool install alpi-agent →</a>
    </div>
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
  iconPath: '../assets/alpi-favicon.svg',
})}
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@300;400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../doc.css?v=${VERSION}" />
<link rel="stylesheet" href="../demo.css" />
</head>
<body>
<div id="ascii-bg" aria-hidden="true"><pre id="ascii-pre"></pre></div>
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

${themeControlHtml}
<script src="../doc.js?v=${VERSION}"></script>
<script src="../demo.js?v=${VERSION}" defer></script>
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
  iconPath: '../assets/alpi-favicon.svg',
})}
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@300;400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../doc.css?v=${VERSION}" />
</head>
<body>
<div id="ascii-bg" aria-hidden="true"><pre id="ascii-pre"></pre></div>
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

${themeControlHtml}
<script src="../doc.js?v=${VERSION}"></script>
</body>
</html>
`;
}

// ── blog ─────────────────────────────────────────────────────────────────────
const MONTHS = ['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function formatPostDate(iso) {
  const m = (iso || '').match(/^(\d{4})-(\d{2})-(\d{2})/);
  if (!m) return iso || '';
  return `${MONTHS[Number(m[2]) - 1]} ${Number(m[3])}, ${m[1]}`;
}

// Post-aware link rewrite: a `<slug>.md` matching another post resolves within
// /blog/; everything else falls back to the docs/external rewrite.
function postLinkRewrite(url) {
  if (/^(https?:|mailto:|#|\/)/.test(url)) return url;
  const clean = url.replace(/^(\.\/|\.\.\/)+/, '');
  const [path, hash = ''] = clean.split('#');
  const base = path.replace(/\.md$/i, '');
  if (POSTS.some(p => p.slug === base)) return base + '.html' + (hash ? '#' + hash : '');
  return linkRewrite(url);
}

function postMetaLine(post) {
  const parts = [];
  if (post.date) parts.push(formatPostDate(post.date));
  if (post.tags.length) parts.push(post.tags.join(' · '));
  return parts.join('  ·  ');
}

function renderPostsGrid() {
  if (!POSTS.length) {
    return `    <p class="sub">No posts yet.</p>`;
  }
  const cards = POSTS.map(p =>
    `      <a class="doc" href="${p.slug}.html">
        <span class="ix">${escapeHtml(postMetaLine(p))}</span>
        <h4>${escapeHtml(p.title)}</h4>
        <p>${escapeHtml(p.description)}</p>
        <span class="go">read →</span>
      </a>`
  ).join('\n');
  return `    <div class="docs" style="grid-template-columns:repeat(3,1fr)">
${cards}
    </div>`;
}

function blogIndexPage() {
  return `<!doctype html>
<html lang="en">
<head>
${renderHead({
  kind: 'blog-index',
  title: 'alpi blog — posts',
  description: `Writing from the alpi project: positioning, architecture, and how local-first agent infrastructure plays out in practice. ${POSTS.length} post${POSTS.length === 1 ? '' : 's'}.`,
  path: '/blog/',
  iconPath: '../assets/alpi-favicon.svg',
})}
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@300;400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../doc.css?v=${VERSION}" />
</head>
<body>
<div id="ascii-bg" aria-hidden="true"><pre id="ascii-pre"></pre></div>
<div class="veil"></div>

${renderNav('blog-index')}

<main class="shell shell-wide docs-index">
<section id="docs">
  <div class="shell">
    <div class="eyebrow">${POSTS.length} post${POSTS.length === 1 ? '' : 's'}</div>
    <h2>BLOG</h2>
    <p class="sub">Positioning, architecture, and field notes from the alpi project.</p>
${renderPostsGrid()}
  </div>
</section>
</main>

${themeControlHtml}
<script src="../doc.js?v=${VERSION}"></script>
</body>
</html>
`;
}

function postPage(post, bodyHtml, prev, next) {
  const metaLine = postMetaLine(post);
  return `<!doctype html>
<html lang="en">
<head>
${renderHead({
  kind: 'post',
  title: `${post.title} — alpi blog`,
  description: post.description || `A post from the alpi blog.`,
  path: `/blog/${post.slug}.html`,
  iconPath: '../assets/alpi-favicon.svg',
  date: post.date || undefined,
})}
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=JetBrains+Mono:wght@300;400;500;600&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../doc.css?v=${VERSION}" />
</head>
<body>
<div id="ascii-bg" aria-hidden="true"><pre id="ascii-pre"></pre></div>
<div class="veil"></div>

${renderNav('blog')}

<main class="shell doc">
  <header class="dochead">
    <h1>${escapeHtml(post.title)}</h1>
    ${post.description ? `<p class="sub">${escapeHtml(post.description)}</p>` : ''}
    ${metaLine ? `<div class="meta mono"><span>${escapeHtml(metaLine)}</span></div>` : ''}
  </header>

  <article id="md-target" class="md">
${bodyHtml}
  </article>

  <aside class="post-cta">
    <div class="eyebrow">Get started</div>
    <h2 class="post-cta-h">Run your own private agent network.</h2>
    <p class="post-cta-sub">One command. Local-first, source-available, no telemetry — your agents run on the machines you already own.</p>
    <div class="cta-row">
      <a class="btn btn-primary" href="../index.html#install">$ uv tool install alpi-agent <span class="arr">→</span></a>
      <a class="btn btn-ghost" href="https://github.com/satoshi-ltd/alpi">View source <span class="arr">→</span></a>
    </div>
    <p class="post-cta-meta">BUSL-1.1 → Apache-2.0 (rolling) · the ALP protocol is Apache-2.0 from day one</p>
  </aside>

  <nav class="pager">
    ${prev
      ? `<a class="pg prev" href="${prev.slug}.html"><span class="lbl">← newer</span><span class="tt">${escapeHtml(prev.title)}</span></a>`
      : `<a class="pg prev" href="index.html"><span class="lbl">← back</span><span class="tt">all posts</span></a>`}
    ${next
      ? `<a class="pg next" href="${next.slug}.html"><span class="lbl">older →</span><span class="tt">${escapeHtml(next.title)}</span></a>`
      : `<a class="pg next" href="index.html"><span class="lbl">index →</span><span class="tt">all posts</span></a>`}
  </nav>
</main>

${themeControlHtml}
<script src="../doc.js?v=${VERSION}"></script>
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

// Quickstart demo widget (mounts in landing hero and on QUICKSTART doc).
// CSS travels as-is; demo.js gets the same version sweep landing.html
// gets so the simulated terminal advertises the version this build
// is shipping (header `alpi v…`, install line, doctor row, etc.).
copyFileSync(join(TPL, 'demo.css'), join(DIST, 'demo.css'));
{
  const src = readFileSync(join(TPL, 'demo.js'), 'utf8');
  // ``\bv?\d+\.\d+\.\d+\b`` catches both ``v0.3.0`` and bare ``0.3.0``
  // (the doctor row prints the bare form). Preserve the ``v`` prefix
  // when the literal had one so we don't drop it on the way out.
  const out = src.replace(/\bv?\d+\.\d+\.\d+\b/g,
    m => (m.startsWith('v') ? 'v' : '') + VERSION);
  writeFileSync(join(DIST, 'demo.js'), out);
}

// Landing — inject head, shared nav + docs grid, rewrite version refs
const landingHead = renderHead({
  kind: 'landing',
  title: `alpi — ${SITE_TAGLINE}`,
  description: SITE_DESCRIPTION,
  path: '/',
  iconPath: 'assets/alpi-favicon.svg',
});
const landing = readFileSync(join(TPL, 'landing.html'), 'utf8')
  .replace('<meta charset="utf-8" />\n<!-- SEO_HEAD (injected by build.mjs) -->', landingHead)
  .replace('<!-- NAV (injected by build.mjs) -->', renderNav('landing'))
  .replace('<!-- DOCS_GRID_PLACEHOLDER -->', renderDocsGrid({ hrefPrefix: 'docs/' }))
  // Match any v<semver> in the landing template so the hero, terminal
  // chrome, and footer all track pyproject.toml regardless of which
  // version the template was last saved with.
  .replace(/\bv\d+\.\d+\.\d+\b/g, `v${VERSION}`)
  // cache-bust the demo widget script — same defense as doc.js/apps.css.
  .replace('src="demo.js"', `src="demo.js?v=${VERSION}"`)
  // Desktop version goes AFTER the alpi-version sweep so the regex
  // above doesn't clobber it (desktop ships on its own track).
  .replaceAll('<!-- DESKTOP_DOWNLOAD_URL -->', DESKTOP_DOWNLOAD_URL)
  .replaceAll('<!-- DESKTOP_RELEASES_URL -->', DESKTOP_RELEASES_URL)
  .replaceAll('<!-- DESKTOP_VERSION -->', `v${DESKTOP_VERSION}`);
write(join(DIST, 'index.html'), landing);

// Apps page — same head/nav infra as landing, but its own template + CSS
const appsHead = renderHead({
  kind: 'landing',
  title: 'alpi apps — desktop + mobile',
  description: 'Desktop and mobile clients for alpi. The agent stays in the daemon you run; the apps connect to it over Tailscale with QR-pair tokens, biometric unlock, and native approval modals for caution commands.',
  path: '/apps.html',
  iconPath: 'assets/alpi-favicon.svg',
});
copyFileSync(join(TPL, 'apps.css'), join(DIST, 'apps.css'));
const apps = readFileSync(join(TPL, 'apps.html'), 'utf8')
  .replace('<meta charset="utf-8" />\n<!-- SEO_HEAD (injected by build.mjs) -->', appsHead)
  .replace('<!-- NAV (injected by build.mjs) -->', renderNav('apps'))
  .replace('<!-- THEME_CONTROL (injected by build.mjs — same component used by docs) -->', themeControlHtml)
  .replace(/\bv\d+\.\d+\.\d+\b/g, `v${VERSION}`)
  .replaceAll('<!-- DESKTOP_DOWNLOAD_URL -->', DESKTOP_DOWNLOAD_URL)
  .replaceAll('<!-- DESKTOP_RELEASES_URL -->', DESKTOP_RELEASES_URL)
  .replaceAll('<!-- DESKTOP_VERSION -->', `v${DESKTOP_VERSION}`)
  // cache-bust shared assets so a Cloudflare edge copy of an older bundle can't crash against new HTML markup.
  .replace('href="doc.css"', `href="doc.css?v=${VERSION}"`)
  .replace('href="apps.css"', `href="apps.css?v=${VERSION}"`)
  .replace('src="doc.js"', `src="doc.js?v=${VERSION}"`);
write(join(DIST, 'apps.html'), apps);

// Live preview — copies the desktop prototype (the React+Babel one) into /preview/.
// The /apps "see it live" CTA opens this in an iframe inside an overlay.
// Heavy (~600KB of React+Babel from unpkg + 13 jsx files); lazy-loaded only when the overlay opens.
const previewSrc = join(TPL, 'preview');
if (existsSync(previewSrc)) copyTree(previewSrc, join(DIST, 'preview'));

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
    // The ``<!-- alpi-demo -->`` marker survives Markdown rendering as
    // an escaped paragraph; swap it for the mount node the demo widget
    // hydrates on load.
    body = body.replace(
      /<p>(?:&lt;|<)!--\s*alpi-demo\s*--(?:&gt;|>)<\/p>/g,
      '<div data-alpi-demo class="demo-console"></div>',
    );
  }
  const prev = DOCS[k - 1] || null;
  const next = DOCS[k + 1] || null;
  write(join(DIST, 'docs', `${doc.slug}.html`), docPage(doc, body, prev, next));
  console.log(`  ${doc.ix}  ${doc.slug.padEnd(14)} ← ${doc.src}`);
}

// Blog — auto-discovered posts. Index + one page per post; newest-first pager.
write(join(DIST, 'blog', 'index.html'), blogIndexPage());
for (let k = 0; k < POSTS.length; k++) {
  const post = POSTS[k];
  const body = renderMarkdown(stripFirstH1(post.body), { linkRewrite: postLinkRewrite });
  const prev = POSTS[k - 1] || null;   // newer
  const next = POSTS[k + 1] || null;   // older
  write(join(DIST, 'blog', `${post.slug}.html`), postPage(post, body, prev, next));
  console.log(`  blog  ${post.slug.padEnd(14)} ← posts/${post.slug}.md`);
}

// sitemap.xml — discoverable URL list for crawlers
const today = new Date().toISOString().slice(0, 10);
const sitemapUrls = [
  { loc: `${SITE_URL}/`, priority: '1.0', changefreq: 'weekly' },
  { loc: `${SITE_URL}/apps.html`, priority: '0.95', changefreq: 'weekly' },
  { loc: `${SITE_URL}/docs/`, priority: '0.9', changefreq: 'weekly' },
  ...DOCS.map(d => ({
    loc: `${SITE_URL}/docs/${d.slug}.html`,
    priority: '0.8',
    changefreq: 'weekly',
  })),
  ...(POSTS.length ? [{ loc: `${SITE_URL}/blog/`, priority: '0.7', changefreq: 'weekly' }] : []),
  ...POSTS.map(p => ({
    loc: `${SITE_URL}/blog/${p.slug}.html`,
    priority: '0.6',
    changefreq: 'monthly',
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

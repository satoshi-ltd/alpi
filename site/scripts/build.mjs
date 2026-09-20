#!/usr/bin/env node
// Build script for the alpi site. Zero runtime dependencies.
// Reads docs at HEAD from the repo and bakes a static site into site/dist/.

import { ALPI_PATHS } from '../../common/alpiMark.mjs';
import { ICONS } from '../../common/iconPaths.mjs';
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
const SITE_TAGLINE = 'agent infrastructure you run yourself';
const SITE_DESCRIPTION = "alpi runs long-lived agents on machines you own. Every agent gets an Ed25519 identity, its own memory, a deny-by-default permission list and a daily spend ceiling the daemon enforces below the model. ALP links agents across machines with no registry, no central account and no mandatory cloud.";
// 1200×630 — standard OG / Twitter card ratio. Crops cleanly on Twitter, Slack, LinkedIn and Discord previews.
const OG_IMAGE = `${SITE_URL}/assets/alpi-social.png`;
const OG_IMAGE_W = 1200;
const OG_IMAGE_H = 630;

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
  { slug: 'INSTALL',      src: 'docs/INSTALL.md',       ix: '02', category: 'guide',     sub: "Install with uv or pipx, the update path, uninstall, supported platforms." },
  { slug: 'QUICKSTART',   src: 'QUICKSTART.md',         ix: '03', category: 'guide',     sub: 'Install, pick a model, pin a workspace, send a first message, and check health.' },
  { slug: 'PROFILES',     src: 'docs/PROFILES.md',      ix: '04', category: 'guide',     sub: 'The isolation primitive: identity, keys, memory, skills, peers, schedules, and cost.' },
  { slug: 'SKILLS',       src: 'docs/SKILLS.md',        ix: '05', category: 'guide',     sub: "Directory contract, frontmatter, the scanner, eligibility gates, secrets." },
  { slug: 'MODELS',       src: 'docs/MODELS.md',        ix: '06', category: 'guide',     sub: 'Model tiers for tool-heavy agent use: quality, cost/service, and local Ollama.' },
  { slug: 'ALP',          src: 'docs/ALP.md',           ix: '07', category: 'reference', sub: 'Alpi Link Protocol: pinned identity, signed envelopes, peer capabilities, workgroups.' },
  { slug: 'WORKGROUPS',   src: 'docs/WORKGROUPS.md',    ix: '08', category: 'reference', sub: "Briefings, task markers, recipes, pipelines with gates, and how a human steers." },
  { slug: 'ARCHITECTURE', src: 'docs/ARCHITECTURE.md',  ix: '09', category: 'reference', sub: 'Code structure, turn loop, memory, sessions, email tool, scheduler, MCP, logging.' },
  { slug: 'CONFIG',       src: 'docs/CONFIG.md',        ix: '10', category: 'reference', sub: "Every YAML key, what it controls, its default, and when a change takes effect." },
  { slug: 'SECURITY',     src: 'docs/SECURITY.md',      ix: '11', category: 'reference', sub: 'Two-layer security model. Approval system, SSRF, prompt-injection, sensitive paths. Sandbox.' },
  { slug: 'DEPLOYMENTS',  src: 'docs/DEPLOYMENTS.md',   ix: '12', category: 'ops',       sub: "Reference topologies from one laptop to an enterprise mesh, Docker and WSS included." },
  { slug: 'OPERATIONS',   src: 'docs/OPERATIONS.md',    ix: '13', category: 'ops',       sub: 'Day-2 runbook. Doctor, diagnostics, log rotation, backup, recovery, upgrade.' },
  { slug: 'INTEGRATIONS', src: 'docs/INTEGRATIONS.md',  ix: '14', category: 'reference', sub: "Drive a profile or a workgroup from your own code, over the host-plane WebSocket." },
  { slug: 'LICENSE',      src: 'LICENSE',               ix: '15', category: 'legal',     sub: "Source-available terms: what individuals get free, when a company needs a licence.", raw: true },
  { slug: 'ROADMAP',      src: 'docs/ROADMAP.md',       ix: '16', category: 'planning',  sub: "Open release gates, demand-gated candidates, and decisions already discarded." },
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
<meta name="theme-color" content="#0c0b09" />
<script src="${kind === 'landing' ? '' : '../'}theme.js?v=${VERSION}"></script>
<meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1" />
<meta name="generator" content="${SITE_NAME} static build" />
<link rel="canonical" href="${canonical}" />
<link rel="icon" href="${iconPath}" type="image/svg+xml" />
<link rel="mask-icon" href="${iconPath.replace('alpi-icon.svg', 'alpi-black.svg')}" color="#f0b447" />

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
// The alpaca geometry has ONE source: common/alpiMark.mjs, the same module both apps
// render. Written into dist so the favicon link resolves to a real file.
const ALPI_ICON = 'alpi-icon.svg';
function alpiIconSvg() {
  const paths = ALPI_PATHS.map((d) => `<path d="${d}"/>`).join('');
  return `<svg xmlns="http://www.w3.org/2000/svg" width="512" height="512" viewBox="0 0 512 512" role="img" aria-label="alpi">`
    + `<rect x="8" y="8" width="496" height="496" rx="116" fill="#f0b447"/>`
    + `<g fill="#141006" transform="translate(97.70 40.61) scale(0.37072)">${paths}</g></svg>`;
}

// Same lucide source the desktop app renders, so the toggle can never drift from it.
function lucide(name, className) {
  const body = ICONS[name]
    .map(([tag, attrs]) => `<${tag} ${Object.entries(attrs).map(([k, v]) => `${k}="${v}"`).join(' ')}/>`)
    .join('');
  return `<svg class="${className}" viewBox="0 0 24 24" fill="none" stroke="currentColor" `
    + `stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">${body}</svg>`;
}

function inlineLogoPart(fileName, className, attrs = '') {
  const src = fileName === ALPI_ICON
    ? alpiIconSvg()
    : readFileSync(join(SITE, 'assets', fileName), 'utf8');
  return src
    .replace(/<\?xml[^?]*\?>\s*/i, '')
    .replace(/<svg\b/i, `<svg class="${className}" ${attrs} aria-hidden="true" focusable="false"`)
    .trim();
}

// App-icon tile + wordmark, the lockup the sibling product uses. The tile is the one
// place the mark sits on a ground; everywhere else the alpaca stays a bare silhouette.
const logoSvg = `<span class="logo">${inlineLogoPart('alpi-icon.svg', 'logo-mark', 'width="36" height="36"')}<span class="logo-word">alpi</span></span>`;
const GITHUB_URL = 'https://github.com/satoshi-ltd/alpi';
const githubIcon = `<svg viewBox="0 0 16 16" aria-hidden="true" focusable="false"><path fill="currentColor" d="M8 0C3.58 0 0 3.67 0 8.2c0 3.62 2.29 6.69 5.47 7.78.4.08.55-.18.55-.4l-.01-1.52c-2.23.5-2.7-1.1-2.7-1.1-.36-.95-.89-1.2-.89-1.2-.73-.51.06-.5.06-.5.8.06 1.23.85 1.23.85.72 1.26 1.88.9 2.34.68.07-.53.28-.9.51-1.1-1.78-.21-3.64-.91-3.64-4.04 0-.9.31-1.62.82-2.2-.08-.21-.36-1.04.08-2.17 0 0 .68-.22 2.2.84A7.42 7.42 0 0 1 8 3.84c.68 0 1.36.09 1.99.28 1.52-1.06 2.2-.84 2.2-.84.44 1.13.16 1.96.08 2.17.51.58.82 1.31.82 2.2 0 3.14-1.87 3.83-3.65 4.03.29.26.54.76.54 1.53l-.01 2.37c0 .22.14.48.55.4A8.12 8.12 0 0 0 16 8.2C16 3.67 12.42 0 8 0Z"/></svg>`;

// ── shared nav component — identical markup on landing + docs + doc pages ──
// kind: 'landing' | 'docs-index' | 'doc'
// opts.current (doc pages): the slug shown as current crumb
// opts.brandHref: link for the brand chip (home-of-section)
// A plain-text licence is hard-wrapped for a 72-column terminal. On the page that
// reads as ragged prose, so rebuild it as a document: the words are untouched,
// only the wrapping is handed back to the browser.
// A reference table is wider than a phone; give it its own scroller instead of
// letting it widen the whole page.
function wrapTables(html) {
  return html.replace(/<table>[\s\S]*?<\/table>/g, m => `<div class="md-table">${m}</div>`);
}

function renderPlainDocument(raw) {
  const e = s => s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
  const blocks = raw.replace(/\r\n/g, '\n').split(/\n{2,}/).map(b => b.replace(/\s+$/, '')).filter(Boolean);
  const out = [];
  blocks.forEach((block, idx) => {
    const lines = block.split('\n');
    if (/^-{3,}$/.test(lines[0].trim()) && lines.length === 1) { out.push('<hr />'); return; }
    // "Key:   value" rows whose continuations are indented under the value column.
    if (/^[A-Z][A-Za-z ]+:\s+\S/.test(lines[0])) {
      const rows = [];
      for (const line of lines) {
        const m = /^\s/.test(line) ? null : line.match(/^([A-Z][A-Za-z ]+:)\s+(.*)$/);
        if (m) rows.push([m[1].replace(/:$/, ''), [m[2]]]);
        else if (rows.length) rows[rows.length - 1][1].push(line.trim());
      }
      out.push('<dl class="doc-terms">' + rows.map(([k, v]) =>
        `<dt>${e(k)}</dt><dd>${e(v.join(' '))}</dd>`).join('') + '</dl>');
      return;
    }
    // "1. …" clauses with a hanging indent.
    if (/^\d+\.\s/.test(lines[0])) {
      const text = lines.map(l => l.trim()).join(' ').replace(/^\d+\.\s*/, '');
      const n = lines[0].match(/^(\d+)\./)[1];
      out.push(`<p class="doc-clause"><span>${e(n)}.</span> ${e(text)}</p>`);
      return;
    }
    const text = lines.map(l => l.trim()).join(' ');
    // The first line, and any short standalone line, is a section title.
    if (lines.length === 1 && text.length < 60 && !/[.:]$/.test(text)) {
      out.push(`<h2>${e(text)}</h2>`);
      return;
    }
    out.push(`<p>${e(text)}</p>`);
  });
  return out.join('\n');
}

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
    ['#what', 'Profiles'],
    ['#alp', 'Protocol'],
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
    <a href="#apps" class="nav-cta">$ uv tool install alpi-agent →</a>
  </div>`
    : '';

  // CTA install anchor lives on the landing — point at it correctly from each surface.
  const ctaHref = kind === 'landing' ? '#apps' : '../index.html#apps';

  return `<nav class="top">
  <div class="shell row">
    <div class="brand-lockup">
      <a class="brand" href="${brandHref}" aria-label="alpi — home">
        ${logoSvg}
      </a>${crumbsHtml}
    </div>
    ${menuHtml}
    <div class="nav-actions">
      <a href="${ctaHref}" class="nav-cta">$ uv tool install alpi-agent →</a>
    </div>
    ${burgerHtml}
  </div>
  ${drawerHtml}
</nav>
<script>
document.addEventListener('click', function (e) {
  var a = e.target.closest && e.target.closest('a.brand');
  if (!a) return;
  // Same page: the wordmark means "back to the top", not a reload.
  if (new URL(a.href, location.href).pathname !== location.pathname) return;
  e.preventDefault();
  window.scrollTo({ top: 0, behavior: 'smooth' });
});
</script>`;
}

// The footer is a shared component, so it carries its own styles — the landing
// keeps them inline and doc.css never had them, which left 37 pages unstyled.
const FOOTER_CSS = `<style>
footer{border-top:1px solid var(--line);padding:64px 0 48px;margin-top:80px;position:relative;z-index:5}
footer .row{display:grid;grid-template-columns:1fr 1fr 1fr 1fr;gap:40px}
@media(max-width:760px){footer .row{grid-template-columns:1fr 1fr}}
footer h5{font-family:"Geist Mono",ui-monospace,monospace;font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.12em;margin-bottom:16px}
footer ul{list-style:none}
footer li{margin-bottom:10px}
footer a{color:var(--fg);text-decoration:none;font-size:14px}
footer a:hover{color:var(--muted)}
footer .sig{
    margin-top:48px;padding-top:30px;border-top:1px solid var(--line);
    display:flex;align-items:baseline;justify-content:space-between;gap:20px;flex-wrap:wrap;
  }
/* inline-block, not flex: a flex lockup takes its baseline from the icon, which
   drops the version ~6px below the wordmark it is meant to sit next to. */
footer .sig .brand{
    display:inline-block;
    font-family:"Instrument Sans",system-ui,sans-serif;font-size:23px;font-weight:700;
    letter-spacing:-1px;color:var(--fg);line-height:1;
  }
footer .sig .brand .logo-mark{width:28px;height:28px;border-radius:8px;display:inline-block;vertical-align:middle;margin-right:12px}
footer .sig .who{display:flex;align-items:baseline;gap:13px}
footer .sig .ver{font-family:"Geist Mono",ui-monospace,monospace;font-size:11px;color:var(--muted);letter-spacing:.02em}
footer .sig .attr{font-size:11px;color:var(--muted);font-family:"Geist Mono",ui-monospace,monospace}
footer .sig .attr a{font-size:inherit}
/* Last: a media query adds no specificity, so the base rules above would win. */
@media(max-width:720px){footer h5,footer .sig .attr,footer .sig .attr a,footer .sig .ver{font-size:12.5px}}
</style>`;

// ── table of contents — built from the rendered h2s, shown only when a document
// is long enough that scrolling blind is a real cost.
function buildToc(bodyHtml) {
  const heads = [...bodyHtml.matchAll(/<h2 id="([^"]+)">([\s\S]*?)<\/h2>/g)]
    .map(m => ({ id: m[1], text: m[2].replace(/<[^>]+>/g, '').trim() }))
    .filter(h => h.text);
  if (heads.length < 4) return '';
  return `<aside class="toc" aria-label="On this page">
    <p class="toc-h">On this page</p>
    <ol>${heads.map(h => `<li><a href="#${h.id}">${h.text}</a></li>`).join('')}</ol>
  </aside>`;
}

// ── shared footer — one component for every surface. `base` is the path back
// to the site root ('' on the landing, '../' from docs/ and blog/).
function renderFooter(base = '') {
  const abs = h => {
    if (/^(https?:|mailto:)/.test(h)) return h;
    // Landing-section anchors have to travel back to the landing from a sub-page.
    if (h.startsWith('#')) return base ? base + 'index.html' + h : h;
    return base + h;
  };
  const cols = [
    ['Product', [['#what','What alpi is'], ['#how','How it works'], ['#alp','ALP protocol'], ['#apps','Get it'], ['blog/index.html','Writing']]],
    ['Guides', [['docs/INSTALL.html','Install'], ['docs/QUICKSTART.html','Quickstart'], ['docs/PROFILES.html','Profiles'], ['docs/SKILLS.html','Skills'], ['docs/MODELS.html','Models'], ['docs/INTEGRATIONS.html','Integrations']]],
    ['Reference', [['docs/ARCHITECTURE.html','Architecture'], ['docs/ALP.html','ALP protocol'], ['docs/CONFIG.html','Configuration'], ['docs/SECURITY.html','Security'], ['docs/OPERATIONS.html','Operations'], ['docs/DEPLOYMENTS.html','Deployments']]],
    ['Meta', [['https://github.com/satoshi-ltd/alpi/blob/main/CHANGELOG.md','Changelog'], ['docs/ROADMAP.html','Roadmap'], ['https://github.com/satoshi-ltd/alpi/blob/main/LICENSE','Licence'], ['mailto:info@satoshi-ltd.com','Commercial use'], ['https://github.com/satoshi-ltd/alpi','GitHub']]],
  ];
  const colHtml = cols.map(([head, links]) => `<div>
        <h5>${head}</h5>
        <ul>${links.map(([h, l]) => `<li><a href="${abs(h)}">${l}</a></li>`).join('')}</ul>
      </div>`).join('\n      ');
  return `${FOOTER_CSS}<button class="theme-btn" type="button" aria-label="Switch theme">${lucide('sun', 'sun')}${lucide('moon', 'moon')}</button><footer>
  <div class="shell">
    <div class="row">
      ${colHtml}
    </div>
    <div class="sig">
      <div class="who">
        <a class="brand" href="${base || ''}index.html">${inlineLogoPart('alpi-icon.svg', 'logo-mark', 'width="28" height="28"')}alpi</a>
        <span class="ver">v${VERSION}</span>
      </div>
      <span class="attr">By <a href="https://www.satoshi-ltd.com/">Satoshi Ltd.</a> &middot; no telemetry</span>
    </div>
  </div>
</footer>`;
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
        <h2>${d.slug}</h2>
        <p>${d.sub}</p>
        <span class="go">read →</span>
      </a>`
  ).join('\n');

  const grid = `    <div class="docs docs-catalog">
${cards}
    </div>`;

  if (!withSection) return grid;

  return `<section id="docs">
  <div class="shell">
    <div class="eyebrow">${eyebrow}</div>
    <h1 class="index-title">${heading}</h1>
    <p class="sub">${sub}</p>
    <nav class="docs-start" aria-label="Start using alpi">
      <a href="${hrefPrefix}INSTALL.html"><span>01 / Install</span><strong>Put alpi on your machine <span aria-hidden="true">→</span></strong></a>
      <a href="${hrefPrefix}QUICKSTART.html"><span>02 / First run</span><strong>Talk to your first agent <span aria-hidden="true">→</span></strong></a>
      <a href="${hrefPrefix}PROFILES.html"><span>03 / Make it yours</span><strong>Give each agent a role <span aria-hidden="true">→</span></strong></a>
    </nav>
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
// Files that live in the repo but are deliberately not built as pages.
const REPO_FILES = {
  'changelog': 'https://github.com/satoshi-ltd/alpi/blob/main/CHANGELOG.md',
  'docker/readme': 'https://github.com/satoshi-ltd/alpi/blob/main/docker/README.md',
  'release': 'https://github.com/satoshi-ltd/alpi/blob/main/docs/RELEASE.md',
};

function linkRewrite(url) {
  if (/^(https?:|mailto:|#|\/)/.test(url)) return url;
  // Strip leading ../ segments; keep just the basename.
  const clean = url.replace(/^(\.\/|\.\.\/)+/, '').replace(/^docs\//, '');
  const [path, hash = ''] = clean.split('#');
  const base = path.replace(/\.md$/i, '');
  const known = DOCS.find(d => d.slug.toLowerCase() === base.toLowerCase());
  if (known) return known.slug + '.html' + (hash ? '#' + hash : '');
  const repoFile = REPO_FILES[base.toLowerCase()];
  if (repoFile) return repoFile + (hash ? '#' + hash : '');
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
  iconPath: '../assets/alpi-icon.svg',
})}
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400..700;1,400..700&family=Geist+Mono:wght@400..700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../doc.css?v=${VERSION}" />
<link rel="stylesheet" href="../demo.css" />
</head>
<body>
<div class="aurora" aria-hidden="true"></div>
<div id="ascii-bg" aria-hidden="true"><pre id="ascii-pre"></pre></div>
<div class="veil"></div>
<div class="grain" aria-hidden="true"></div>

${renderNav('doc', { current: doc.slug })}

<main class="shell doc">
${buildToc(bodyHtml)}
  <header class="dochead">
    <h1>${doc.slug}</h1>
    <p class="sub">${doc.sub}</p>
    <div class="meta mono">
      <span class="ct">${doc.ix} / ${String(TOTAL).padStart(2, '0')}</span><span class="d">·</span><span>${doc.category}</span><span class="d">·</span><span>v${VERSION}</span>
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

${renderFooter('../')}

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
  iconPath: '../assets/alpi-icon.svg',
})}
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400..700;1,400..700&family=Geist+Mono:wght@400..700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../doc.css?v=${VERSION}" />
</head>
<body>
<div class="aurora" aria-hidden="true"></div>
<div id="ascii-bg" aria-hidden="true"><pre id="ascii-pre"></pre></div>
<div class="veil"></div>
<div class="grain" aria-hidden="true"></div>

${renderNav('docs-index')}

<main class="shell shell-wide docs-index">
${renderDocsGrid({
  hrefPrefix: '',
  withSection: true,
  eyebrow: `v${VERSION} · ${TOTAL} documents · updated ${new Date().toISOString().slice(0, 7)}`,
  heading: 'Documentation.',
  sub: "Start with installation and your first conversation. Come back for the guides and reference as your setup grows.",
})}
</main>

${renderFooter('../')}

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
        <h2>${escapeHtml(p.title)}</h2>
        <p>${escapeHtml(p.description)}</p>
        <span class="go">read →</span>
      </a>`
  ).join('\n');
  return `    <div class="docs blog-grid">
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
  iconPath: '../assets/alpi-icon.svg',
})}
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400..700;1,400..700&family=Geist+Mono:wght@400..700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../doc.css?v=${VERSION}" />
</head>
<body>
<div class="aurora" aria-hidden="true"></div>
<div id="ascii-bg" aria-hidden="true"><pre id="ascii-pre"></pre></div>
<div class="veil"></div>
<div class="grain" aria-hidden="true"></div>

${renderNav('blog-index')}

<main class="shell shell-wide docs-index">
<section id="docs">
  <div class="shell">
    <div class="eyebrow">${POSTS.length} post${POSTS.length === 1 ? '' : 's'}</div>
    <h1 class="index-title">Notes from the project.</h1>
    <p class="sub">On building, running and keeping control of your own agents.</p>
${renderPostsGrid()}
  </div>
</section>
</main>

${renderFooter('../')}

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
  iconPath: '../assets/alpi-icon.svg',
  date: post.date || undefined,
})}
<meta name="viewport" content="width=device-width, initial-scale=1" />
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Instrument+Sans:ital,wght@0,400..700;1,400..700&family=Geist+Mono:wght@400..700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="../doc.css?v=${VERSION}" />
</head>
<body>
<div class="aurora" aria-hidden="true"></div>
<div id="ascii-bg" aria-hidden="true"><pre id="ascii-pre"></pre></div>
<div class="veil"></div>
<div class="grain" aria-hidden="true"></div>

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
      <a class="btn btn-primary" href="../index.html#apps">$ uv tool install alpi-agent <span class="arr">→</span></a>
      <a class="btn btn-ghost" href="https://github.com/satoshi-ltd/alpi">View source <span class="arr">→</span></a>
    </div>
    <p class="post-cta-meta">BUSL-1.1 → Apache-2.0 (rolling)</p>
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

${renderFooter('../')}

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
writeFileSync(join(DIST, 'assets', ALPI_ICON), alpiIconSvg());

copyFileSync(join(TPL, 'theme.js'), join(DIST, 'theme.js'));

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
  iconPath: 'assets/alpi-icon.svg',
});
const landing = readFileSync(join(TPL, 'landing.html'), 'utf8')
  .replace('<meta charset="utf-8" />\n<!-- SEO_HEAD (injected by build.mjs) -->', landingHead)
  .replace('<!-- NAV (injected by build.mjs) -->', renderNav('landing'))
  // Match any v<semver> in the landing template so the hero, terminal
  // chrome, and footer all track pyproject.toml regardless of which
  // version the template was last saved with.
  .replace(/\bv\d+\.\d+\.\d+\b/g, `v${VERSION}`)
  // cache-bust the demo widget script — same defense as doc.js/apps.css.
  .replace('src="demo.js"', `src="demo.js?v=${VERSION}"`)
  // Desktop version goes AFTER the alpi-version sweep so the regex
  // above doesn't clobber it (desktop ships on its own track).
  .replace('<!-- FOOTER (injected by build.mjs) -->', renderFooter(''))
  .replaceAll('<!-- DESKTOP_DOWNLOAD_URL -->', DESKTOP_DOWNLOAD_URL)
  .replaceAll('<!-- DESKTOP_RELEASES_URL -->', DESKTOP_RELEASES_URL)
  .replaceAll('<!-- DESKTOP_RELEASES_URL -->', DESKTOP_RELEASES_URL)
  .replaceAll('<!-- DESKTOP_VERSION -->', `v${DESKTOP_VERSION}`);
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
    body = renderPlainDocument(raw);
  } else {
    body = renderMarkdown(stripFirstH1(stripFrontmatter(raw)), { linkRewrite });
    body = wrapTables(body);
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
  const body = wrapTables(renderMarkdown(stripFirstH1(post.body), { linkRewrite: postLinkRewrite }));
  const prev = POSTS[k - 1] || null;   // newer
  const next = POSTS[k + 1] || null;   // older
  write(join(DIST, 'blog', `${post.slug}.html`), postPage(post, body, prev, next));
  console.log(`  blog  ${post.slug.padEnd(14)} ← posts/${post.slug}.md`);
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

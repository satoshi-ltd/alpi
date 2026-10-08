import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { creaseLadders } from './brand.mjs';
import { fileURLToPath } from 'node:url';

const site = fileURLToPath(new URL('../', import.meta.url));
execFileSync(process.execPath, [join(site, 'scripts/build.mjs')]);
const dist = join(site, 'dist');
const read = path => readFileSync(join(dist, path), 'utf8');
const isRedirect = html => html.includes('http-equiv="refresh"');

test('generated pages link to existing local pages and assets', () => {
  const missing = [];
  for (const folder of ['', 'docs', 'blog']) {
    for (const name of readdirSync(join(dist, folder)).filter(name => name.endsWith('.html'))) {
      const page = join(folder, name);
      for (const [, href] of read(page).matchAll(/(?:href|src)="([^"]+)"/g)) {
        const url = new URL(href.replaceAll('&amp;', '&'), `https://site.test/${page}`);
        if (url.origin !== 'https://site.test') continue;
        if (!existsSync(join(dist, decodeURIComponent(url.pathname)))) missing.push(`${page}: ${href}`);
      }
    }
  }
  assert.deepEqual(missing, []);
});

test('unpublished reference links keep their repository path and section', () => {
  assert.ok(read('docs/INSTALL.html').includes('https://github.com/satoshi-ltd/alpi/blob/main/docker/README.md'));
  assert.ok(read('docs/CONFIG.html').includes('https://github.com/satoshi-ltd/alpi/blob/main/docker/README.md#secure-internet-access-wss'));
  assert.ok(read('docs/OPERATIONS.html').includes('https://github.com/satoshi-ltd/alpi/blob/main/docs/RELEASE.md'));
});

test('the roadmap stays in the repository: its old page redirects there and no doc lists it', () => {
  const url = 'https://github.com/satoshi-ltd/alpi/blob/main/docs/ROADMAP.md';
  const redirect = read('docs/ROADMAP.html');
  assert.ok(isRedirect(redirect) && redirect.includes(`url=${url}`) && redirect.includes('noindex'));
  assert.ok(!read('docs/index.html').includes('ROADMAP.html'));
  assert.ok(!read('sitemap.xml').includes('ROADMAP'));
  assert.ok(read('docs/ALP.html').includes(url));
  assert.ok(read('index.html').includes(`href="${url}"`));
});

test('index pages have one primary heading and an installation path', () => {
  for (const page of ['docs/index.html', 'blog/index.html']) {
    assert.equal([...read(page).matchAll(/<h1\b/g)].length, 1);
  }
  const intro = read('docs/index.html').match(/<nav class="docs-start"[\s\S]*?<\/nav>/)[0];
  for (const page of ['INSTALL', 'QUICKSTART', 'PROFILES']) assert.ok(intro.includes(`href="${page}.html"`));
});

test('every page initializes its shared theme before loading styles', () => {
  for (const folder of ['', 'docs', 'blog']) {
    for (const name of readdirSync(join(dist, folder)).filter(name => name.endsWith('.html'))) {
      const html = read(join(folder, name));
      if (isRedirect(html)) continue;
      const script = html.indexOf('theme.js?v=');
      assert.ok(script > 0 && script < html.indexOf('rel="stylesheet"'), `${folder}/${name}`);
      assert.equal([...html.matchAll(/theme\.js\?v=/g)].length, 1);
    }
  }
});

const pages = () => ['', 'docs', 'blog'].flatMap(folder => readdirSync(join(dist, folder)).filter(name => name.endsWith('.html')).map(name => join(folder, name))).filter(page => !isRedirect(read(page)));
const rules = css => [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map(m => ({ selector: m[1].trim(), body: m[2] }));

test('Bricolage ships as one font file and its licence', () => {
  assert.ok(existsSync(join(dist, 'assets/fonts/bricolage-800-latin.woff2')));
  assert.ok(existsSync(join(dist, 'assets/fonts/BricolageGrotesque-OFL.txt')));
  const css = read('brand.css');
  assert.equal([...css.matchAll(/@font-face/g)].length, 1);
  assert.ok(css.includes('url("assets/fonts/bricolage-800-latin.woff2")'));
  assert.ok(css.includes('font-display:swap'));
});

test('only the lockup, the hero, the page headings and profile names use Bricolage; body, docs and posts stay Instrument Sans', () => {
  const using = rules(read('brand.css')).filter(r => r.body.includes('Bricolage') && !r.selector.startsWith('@font-face'));
  assert.deepEqual(using.map(r => r.selector), ['.logo .logo-word.crease,.hero h1 .crease,h1.crease-heading,h2.crease-heading,.crease-name']);
  for (const file of ['doc.css', 'demo.css']) assert.ok(!/bricolage/i.test(read(file)), file);
  assert.ok(!/bricolage/i.test(readFileSync(join(site, 'templates/landing.html'), 'utf8')));
  assert.equal([...read('index.html').matchAll(/<h2 class="crease crease-heading"|<h2 id="story-title" class="crease crease-heading"/g)].length, 6);
  assert.match(read('doc.css'), /html,body\{[^}]*Instrument Sans/);
});

test('every page links the brand stylesheet and only the landing preloads the font', () => {
  for (const page of pages()) {
    const html = read(page);
    assert.equal([...html.matchAll(/brand\.css\?v=/g)].length, 1, page);
    assert.equal(html.includes('rel="preload"'), page === 'index.html', page);
  }
  assert.match(read('index.html'), /<link rel="preload" href="assets\/fonts\/bricolage-800-latin\.woff2" as="font" type="font\/woff2" crossorigin \/>/);
});

test('the brand stylesheet carries the computed crease ladders for both themes', () => {
  const css = read('brand.css');
  const { night, light } = creaseLadders();
  const [dark, paper] = css.split(':root[data-theme="light"]');
  for (const tone of [...night.lockup, ...night.first, ...night.second]) assert.ok(dark.includes(tone), tone);
  for (const tone of [...light.lockup, ...light.first, ...light.second]) assert.ok(paper.includes(tone), tone);
  assert.match(css, /@media \(forced-colors:active\)\{\.crease,:root \.logo \.logo-word\.crease,h1\.crease-heading,h2\.crease-heading\{background:none;color:CanvasText\}\}/);
});

test('every navigation lockup is the tonal alpaca beside real crease text', () => {
  for (const page of pages()) {
    const nav = read(page).match(/<nav class="top">[\s\S]*?<\/nav>/)[0];
    assert.equal([...nav.matchAll(/<polygon /g)].length, 12, page);
    assert.ok(nav.includes('<span class="logo-word crease">alpi</span>'), page);
  }
});

test('the landing hero is the crease headline, with no strip of identities', () => {
  const html = read('index.html');
  const hero = html.match(/<h1>[\s\S]*?<\/h1>/)[0];
  assert.ok(hero.includes('<span class="hero-line"><span class="crease crease-first">Your</span> <span class="crease crease-agents">agents.</span></span>'));
  assert.ok(read('brand.css').includes('.hero h1 .hero-line{display:flex;column-gap:.24em}'));
  assert.ok(hero.includes('<span class="crease crease-second">Your machines.</span>'));
  assert.ok(!html.includes('class="identities"') && !html.includes('IDENTITIES'));
});

test('the hero pass pauses while the hero is off screen', () => {
  const html = read('index.html');
  assert.match(html, /IntersectionObserver\(\(\[entry\]\) => hero\.classList\.toggle\('is-away', !entry\.isIntersecting\)\)\.observe\(hero\)/);
  assert.ok(read('brand.css').includes('.hero.is-away h1 .crease-agents{animation-play-state:paused}'));
});

test('favicon, brand art and social card are generated from the shared sources', () => {
  assert.ok(read('index.html').includes('rel="icon" href="assets/alpi-favicon.svg"'));
  for (const name of ['alpi-favicon.svg', 'alpi-brand.svg', 'alpi-social.svg']) {
    assert.equal(readFileSync(join(site, 'assets', name), 'utf8'), read(`assets/${name}`), name);
  }
  assert.equal([...read('assets/alpi-favicon.svg').matchAll(/<polygon /g)].length, 9);
  assert.ok(read('assets/alpi-brand.svg').includes('data:font/woff2;base64,'));
  assert.ok(!existsSync(join(site, 'assets/alpi-brand.png')));
});

test('scrapers keep a raster social image', () => {
  const html = read('index.html');
  assert.ok(html.includes('og:image" content="https://alpi.satoshi-ltd.com/assets/alpi-social.png"'));
  assert.ok(existsSync(join(dist, 'assets/alpi-social.png')));
});

test('the README card points at a generated file and stays out of the rendered doc', () => {
  const readme = readFileSync(join(site, '../README.md'), 'utf8');
  const src = readme.match(/<img src="([^"]+)"/)[1];
  assert.equal(src, 'https://raw.githubusercontent.com/satoshi-ltd/alpi/main/site/assets/alpi-brand.svg');
  assert.ok(existsSync(join(site, '..', 'site/assets/alpi-brand.svg')));
  assert.ok(!read('docs/README.html').includes('alpi-brand.svg'));
});

test('the lockup crease wins the cascade over the page brand rules', () => {
  const css = read('brand.css');
  const rule = css.match(/:root \.logo \.logo-word\.crease\{([^}]*)\}/)[1];
  for (const part of ['color:transparent', 'font-weight:800', 'letter-spacing:-.04em', 'background-image:var(--crease-lockup)']) assert.ok(rule.includes(part), part);
  const page = read('index.html');
  const brandRule = page.match(/\.brand \.logo-word\{[^}]*\}/);
  assert.ok(!brandRule || !/(^|[^-])!important/.test(brandRule[0]));
});

test('the hero console draws each profile as its origami object in its own colour', async () => {
  const { ACCENTS, ACCENT_FOLDS } = await import('../../common/accents.mjs');
  const hex = (fold) => ACCENTS.find(([colour]) => ACCENT_FOLDS[colour] === fold)[1];
  const demo = read('demo.js');
  assert.ok(!demo.includes('__PROFILES__'));
  assert.ok(!/[⬟⌃▴]/.test(demo));
  const profiles = JSON.parse(demo.match(/const PROFILES = (\{.*?\});\n/)[1]);
  assert.deepEqual(Object.keys(profiles).sort(), ['builder', 'librarian', 'reviewer']);
  assert.equal(profiles.reviewer.color, hex('shield'));
  assert.equal(profiles.librarian.color, hex('tree'));
  assert.equal(profiles.builder.color, hex('rocket'));
  for (const { mark } of Object.values(profiles)) assert.match(mark, /^<svg [^>]*viewBox="0 0 100 100"/);
});

test('profile names wear their fold and a crease in their colour on both themes, and every section heading takes the crease type', async () => {
  const { ACCENTS, ACCENT_FOLDS } = await import('../../common/accents.mjs');
  const { creaseGradient, creaseTones } = await import('../../common/crease.mjs');
  const { NIGHT, PAPER } = await import('./brand.mjs');
  const hex = (fold) => ACCENTS.find(([colour]) => ACCENT_FOLDS[colour] === fold)[1];
  const landing = read('index.html');
  assert.ok(!landing.includes('<!-- PROFILE'));
  assert.ok(!landing.includes('profile-ink'));
  const names = [...landing.matchAll(/<span class="profile-name"><svg [^>]*aria-label="(\w+) (\w+)"[\s\S]*?<\/svg><span class="crease crease-name" style="--crease-night:([^;]+);--crease-paper:([^"]+)">(\w+)<\/span><\/span>/g)];
  assert.deepEqual(names.map((m) => [m[5], m[2]]), [
    ['reviewer', 'shield'], ['librarian', 'tree'],
    ['reviewer', 'shield'], ['librarian', 'tree'], ['researcher', 'star'],
    ['reviewer', 'shield'], ['librarian', 'tree'],
  ]);
  for (const [, , fold, night, paper] of names) {
    assert.equal(night, creaseGradient(creaseTones(hex(fold), NIGHT)));
    assert.equal(paper, creaseGradient(creaseTones(hex(fold), PAPER)));
  }
  assert.match(read('brand.css'), /:root\[data-theme="light"\] \.crease-name\{background-image:var\(--crease-paper\)\}/);
  assert.equal([...landing.matchAll(/<h2(?![^>]*crease-heading)[^>]*>/g)].length, 0);
});

test('the hero console stays night on both themes', async () => {
  const { palettes } = await import('../../common/tokens.mjs');
  const scoped = read('tokens.css').match(/\.hero \[data-alpi-demo\]\{([^}]*)\}/);
  assert.ok(scoped);
  assert.match(scoped[1], new RegExp(`--term-bg:${palettes.dark.bgPane}`));
  assert.match(scoped[1], new RegExp(`--fg:${palettes.dark.ink}`));
  assert.match(read('index.html'), /<section class="hero">[\s\S]*?<div data-alpi-demo data-scene-set="hero"/);
});

test('the ascii field only frames the landing hero; reading pages carry none', () => {
  const landing = read('index.html');
  const field = landing.match(/#ascii-bg\{([^}]*)\}/)[1];
  assert.match(field, /position:absolute/);
  assert.match(field, /mask-image:linear-gradient/);
  for (const page of [...pages().filter((p) => p !== 'index.html'), 'doc.js', 'doc.css']) {
    assert.ok(!read(page).includes('ascii'), page);
  }
});

test('everything the console writes goes through the one helper that keeps the newest line in view', () => {
  const demo = read('demo.js');
  assert.equal([...demo.matchAll(/insertAdjacentHTML/g)].length, 1);
  assert.match(demo, /function appendHtml\(html\)\{\s*body\.insertAdjacentHTML\("beforeend", html\);\s*body\.scrollTop = body\.scrollHeight;/);
  assert.match(demo, /appendHtml\(`<span class="thinking">/);
});

test('the demo assets are versioned by their content, so an edit within a release is never served stale', async () => {
  const { createHash } = await import('node:crypto');
  const v = (file) => createHash('sha256').update(read(file)).digest('hex').slice(0, 10);
  const landing = read('index.html');
  assert.ok(landing.includes(`src="demo.js?v=${v('demo.js')}"`));
  assert.ok(landing.includes(`href="demo.css?v=${v('demo.css')}"`));
  assert.ok(read('docs/QUICKSTART.html').includes(`src="../demo.js?v=${v('demo.js')}"`));
  assert.ok(read('docs/QUICKSTART.html').includes(`href="../demo.css?v=${v('demo.css')}"`));
});

const styleSources = () => {
  const landing = readFileSync(join(site, 'templates/landing.html'), 'utf8').match(/<style>([\s\S]*?)<\/style>/)[1];
  const footer = read('index.html').match(/<style>\nfooter\{[\s\S]*?<\/style>/)[0];
  return { 'landing.html': landing, 'doc.css': read('doc.css'), 'demo.css': read('demo.css'), footer };
};

test('the site wears the apps paper: small corners, no shadows, blur, washes, lifts or umber', () => {
  for (const [name, css] of Object.entries(styleSources())) {
    for (const [, value] of css.matchAll(/border-radius:([^;}]+)/g)) {
      assert.ok(/^(var\(--(r-xs|r-tag|radius|radius-in|radius-btn|radius-sm)\)|50%|0)$/.test(value.trim()), `${name}: border-radius:${value}`);
    }
    for (const [, value] of css.matchAll(/box-shadow:([^;}]+)/g)) assert.ok(value.trim().startsWith('inset'), `${name}: box-shadow:${value}`);
    assert.ok(!/backdrop-filter/.test(css), `${name}: backdrop-filter`);
    assert.ok(!/umber|#4a3006/i.test(css), `${name}: umber`);
    assert.ok(!/(?<!mask-image:)(linear|radial)-gradient/.test(css.replace(/(-webkit-)?mask-image:[^;]+;/g, '')), `${name}: gradient`);
    assert.ok(!/:hover[^{]*\{[^}]*transform/.test(css), `${name}: hover transform`);
    assert.ok(!/#[0-9a-f]{3,8}\b|rgba?\(/i.test(css.replace(/(-webkit-)?mask-image:[^;]+;/g, '')), `${name}: colour literal`);
  }
  assert.ok(!/class="(aurora|grain|veil)"/.test(read('index.html') + read('docs/QUICKSTART.html') + read('blog/index.html')));
});

test('every colour, corner and seam comes from the shared tokens, light and dark', async () => {
  const { palettes, radii } = await import('../../common/tokens.mjs');
  const [dark, light] = read('tokens.css').split(':root[data-theme="light"]');
  for (const key of ['bg', 'bgPane', 'ink', 'ink2', 'ink3', 'line', 'line2', 'hover', 'selected']) {
    assert.ok(dark.includes(palettes.dark[key]), `dark ${key}`);
    assert.ok(light.includes(palettes.light[key]), `light ${key}`);
  }
  assert.ok(dark.includes(`--r-xs:${radii.xs}px`) && dark.includes(`--r-tag:${radii.tag}px`));
  for (const page of pages()) assert.equal([...read(page).matchAll(/tokens\.css\?v=/g)].length, 1, page);
});

test('the docs index groups the docs by intent, titled in words with a reading time', () => {
  const index = read('docs/index.html');
  const groups = [...index.matchAll(/<h2 class="group-h">([^<]+)<\/h2>/g)].map(m => m[1]);
  assert.deepEqual(groups, ['Start', 'Use alpi', 'Connect', 'Run it', 'Project']);
  for (const title of ['Overview', 'Quickstart', 'Configuration', 'Architecture']) assert.ok(index.includes(`<span class="row-t">${title}</span>`), title);
  assert.equal([...index.matchAll(/<span class="row-m">\d+ min<\/span>/g)].length, 15);
  assert.ok(!/<span class="row-t">[A-Z]{4,}<\/span>/.test(index));
});

test('a doc page names itself in words, rails the doc set and links other docs by title', () => {
  const page = read('docs/QUICKSTART.html');
  assert.ok(page.includes('<h1 class="crease crease-heading">Quickstart</h1>'));
  assert.ok(page.includes('<a href="QUICKSTART.html" aria-current="page">Quickstart</a>'));
  assert.ok(page.includes('<details class="docnav-m">'));
  assert.ok(page.includes('<a href="ARCHITECTURE.html">Architecture</a>'));
  for (const name of readdirSync(join(dist, 'docs')).filter(n => n.endsWith('.html'))) {
    assert.ok(!/<a href="[A-Z_]+\.html(#[^"]*)?">(<code>)?[A-Z_]+\.md(<\/code>)?<\/a>/.test(read(join('docs', name))), name);
  }
});

test('the blog leads with the newest post, lists the rest by year and files every tag on its own page', () => {
  const index = read('blog/index.html');
  const posts = readdirSync(join(dist, 'blog')).filter(n => n.endsWith('.html') && n !== 'index.html' && !n.startsWith('tag-'));
  const lead = index.match(/<a class="post-lead" href="([^"]+)"/)[1];
  const years = [...index.matchAll(/<section class="post-year">[\s\S]*?<\/section>/g)].map(m => m[0]).join('');
  const listed = [...years.matchAll(/<li><a href="([^"]+)\.html">/g)].map(m => m[1]);
  assert.equal(listed.length + 1, posts.length);
  assert.ok(!listed.includes(lead.replace('.html', '')));
  assert.ok(/<h2 class="group-h">\d{4}<\/h2>/.test(index));
  const tags = new Set([...read('sitemap.xml').matchAll(/\/blog\/(tag-[a-z0-9-]+)\.html/g)].map(m => m[1]));
  assert.ok(tags.size > 0);
  for (const tag of tags) {
    const page = read(`blog/${tag}.html`);
    assert.ok(page.includes('<span class="chip on" aria-current="page">'), tag);
    assert.equal([...page.matchAll(/<h1\b/g)].length, 1, tag);
  }
  const post = read(`blog/${lead}`);
  assert.match(post, /<span>\d+ min read<\/span>/);
  for (const [, href] of post.matchAll(/<a class="chip" href="(tag-[^"]+)"/g)) assert.ok(existsSync(join(dist, 'blog', href)), href);
});

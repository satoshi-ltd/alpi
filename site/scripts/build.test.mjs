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

test('repository files outside the published docs link to GitHub', () => {
  const roadmap = read('docs/ROADMAP.html');
  assert.ok(roadmap.includes('https://github.com/satoshi-ltd/alpi/blob/main/desktop/CHANGELOG.md'));
  assert.ok(roadmap.includes('https://github.com/satoshi-ltd/alpi/tree/main/design/'));
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
      const script = html.indexOf('theme.js?v=');
      assert.ok(script > 0 && script < html.indexOf('rel="stylesheet"'), `${folder}/${name}`);
      assert.equal([...html.matchAll(/theme\.js\?v=/g)].length, 1);
    }
  }
});

const pages = () => ['', 'docs', 'blog'].flatMap(folder => readdirSync(join(dist, folder)).filter(name => name.endsWith('.html')).map(name => join(folder, name)));
const rules = css => [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map(m => ({ selector: m[1].trim(), body: m[2] }));

test('Bricolage ships as one font file and its licence', () => {
  assert.ok(existsSync(join(dist, 'assets/fonts/bricolage-800-latin.woff2')));
  assert.ok(existsSync(join(dist, 'assets/fonts/BricolageGrotesque-OFL.txt')));
  const css = read('brand.css');
  assert.equal([...css.matchAll(/@font-face/g)].length, 1);
  assert.ok(css.includes('url("assets/fonts/bricolage-800-latin.woff2")'));
  assert.ok(css.includes('font-display:swap'));
});

test('only the lockup, the hero and the page headings use Bricolage; body, docs and posts stay Instrument Sans', () => {
  const using = rules(read('brand.css')).filter(r => r.body.includes('Bricolage') && !r.selector.startsWith('@font-face'));
  assert.deepEqual(using.map(r => r.selector), ['.logo .logo-word.crease,.hero h1 .crease,h1.crease-heading,h2.crease-heading']);
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
  assert.ok(hero.includes('<span class="crease crease-first">Your agents.</span>'));
  assert.ok(hero.includes('<span class="crease crease-second">Your machines.</span>'));
  assert.ok(!html.includes('class="identities"') && !html.includes('IDENTITIES'));
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

test('profile names take their colour, readable on both themes, and every section heading takes the crease type', async () => {
  const { ACCENTS, ACCENT_FOLDS } = await import('../../common/accents.mjs');
  const { contrastRatio } = await import('../../common/crease.mjs');
  const { NIGHT, PAPER, TEXT_MIN_CONTRAST } = await import('./brand.mjs');
  const hex = (fold) => ACCENTS.find(([colour]) => ACCENT_FOLDS[colour] === fold)[1];
  const landing = read('index.html');
  assert.ok(!landing.includes('data-ink='));
  const inks = [...landing.matchAll(/<span class="profile-ink" style="--ink-night:(#[0-9a-f]{6});--ink-paper:(#[0-9a-f]{6})">(\w+)<\/span>/g)];
  assert.deepEqual(inks.map((m) => [m[3], m[1]]), [['reviewer', hex('shield')], ['librarian', hex('tree')]]);
  for (const [, night, paper] of inks) {
    assert.ok(contrastRatio(night, NIGHT) >= TEXT_MIN_CONTRAST, night);
    assert.ok(contrastRatio(paper, PAPER) >= TEXT_MIN_CONTRAST, paper);
  }
  assert.equal([...landing.matchAll(/<h2(?![^>]*crease-heading)[^>]*>/g)].length, 0);
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

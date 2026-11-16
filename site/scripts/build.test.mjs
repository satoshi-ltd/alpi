import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { CREAM, INK, twinMark } from './brand.mjs';
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

const section = (id) => read('index.html').match(new RegExp(`<section id="${id}"[\\s\\S]*?</section>`))[0];
const visible = (html) => html.replace(/<style>[\s\S]*?<\/style>/g, '').replace(/<script[\s\S]*?<\/script>/g, '');
const words = (html) => html.replace(/<[^>]+>/g, ' ').replace(/&[a-z]+;/g, ' ').split(/\s+/).filter(Boolean);
const pages = () => ['', 'docs', 'blog'].flatMap(folder => readdirSync(join(dist, folder)).filter(name => name.endsWith('.html')).map(name => join(folder, name))).filter(page => !isRedirect(read(page)));
const landingCss = () => readFileSync(join(site, 'templates/landing.html'), 'utf8').match(/<style>([\s\S]*?)<\/style>/)[1];
const rules = css => [...css.matchAll(/([^{}]+)\{([^{}]*)\}/g)].map(m => ({ selector: m[1].trim(), body: m[2] }));

test('Bricolage ships as one font file and its licence', () => {
  assert.ok(existsSync(join(dist, 'assets/fonts/bricolage-800-latin.woff2')));
  assert.ok(existsSync(join(dist, 'assets/fonts/BricolageGrotesque-OFL.txt')));
  const css = read('brand.css');
  assert.equal([...css.matchAll(/@font-face/g)].length, 1);
  assert.ok(css.includes('url("assets/fonts/bricolage-800-latin.woff2")'));
  assert.ok(css.includes('font-display:swap'));
});

test('only the lockup, the hero, the page and section headings and profile names use Bricolage; everything else sets Geist', () => {
  const using = rules(read('brand.css')).filter(r => r.body.includes('Bricolage') && !r.selector.startsWith('@font-face'));
  assert.deepEqual(using.map(r => r.selector), ['.logo .logo-word.display,.hero h1 .display,h1.display-heading,h2.display-heading,.display-name']);
  for (const file of ['doc.css', 'demo.css']) assert.ok(!/bricolage/i.test(read(file)), file);
  assert.ok(!/bricolage/i.test(readFileSync(join(site, 'templates/landing.html'), 'utf8')));
  assert.equal([...read('index.html').matchAll(/<h2 (?:id="[\w-]+" )?class="display display-heading"/g)].length, 7);
  assert.match(read('doc.css'), /html,body\{[^}]*var\(--font-sans\)/);
  assert.match(styleSources()['landing.html'], /html,body\{[^}]*var\(--font-sans\)/);
  assert.ok(read('tokens.css').includes('--font-sans:"Geist"'));
  for (const page of pages()) assert.ok(!/Instrument/.test(read(page)), page);
  for (const file of ['doc.css', 'demo.css', 'brand.css']) assert.ok(!/Instrument/.test(read(file)), file);
});

test('every page links the brand stylesheet and only the landing preloads the font', () => {
  for (const page of pages()) {
    const html = read(page);
    assert.equal([...html.matchAll(/brand\.css\?v=/g)].length, 1, page);
    assert.equal(html.includes('rel="preload"'), page === 'index.html', page);
  }
  assert.match(read('index.html'), /<link rel="preload" href="assets\/fonts\/bricolage-800-latin\.woff2" as="font" type="font\/woff2" crossorigin \/>/);
});

test('the brand stylesheet sets one solid brand ink per theme, draws no crease and paints a gradient only on the agents word', () => {
  const css = read('brand.css');
  assert.ok(css.includes(`:root{--brand-ink:${CREAM}}`));
  assert.ok(css.includes(`:root[data-theme="light"]{--brand-ink:${INK}}`));
  assert.ok(!/crease/i.test(css));
  const painted = css.split('\n').filter((line) => /gradient|background-clip/i.test(line));
  assert.ok(painted.length > 0 && painted.every((line) => line.includes('.hero h1 .display-agents')));
  for (const page of pages()) assert.ok(!/class="[^"]*crease/.test(read(page)), page);
});

test('every navigation lockup is Twin at half turn beside the solid wordmark', () => {
  const mark = twinMark({ height: 34, className: 'logo-mark' });
  for (const page of pages()) {
    const nav = read(page).match(/<nav class="top[^"]*">[\s\S]*?<\/nav>/)[0];
    assert.ok(!nav.includes('<polygon'), page);
    assert.ok(nav.includes(mark), page);
    assert.ok(nav.includes('<span class="logo-word display">alpi</span>'), page);
  }
});

test('the landing hero is the centred solid headline over the cast line-up', () => {
  const html = read('index.html');
  const hero = html.match(/<h1>[\s\S]*?<\/h1>/)[0];
  assert.ok(hero.includes('<span class="hero-line"><span class="display display-first">Your</span> <span class="display display-agents">agents.</span></span>'));
  assert.ok(read('brand.css').includes('.hero h1 .hero-line{display:flex;column-gap:.24em}'));
  assert.ok(hero.includes('<span class="display display-second">Your machines.</span>'));
  const css = landingCss();
  assert.ok(css.includes('.hero .shell{display:flex;flex-direction:column;align-items:center;text-align:center}'));
  assert.ok(css.includes('.hero h1 .hero-line{justify-content:center}'));
  const section = html.match(/<section class="hero">[\s\S]*?<\/section>/)[0];
  const order = ['<h1>', 'class="hero-cta"', 'class="cast"', 'data-alpi-demo'].map((part) => section.indexOf(part));
  assert.ok(order.every((at, i) => at > 0 && (i === 0 || at > order[i - 1])), String(order));
  assert.ok(!html.includes('class="identities"') && !html.includes('IDENTITIES'));
});

test('the cast lines up twelve shapes and Twin in the hero, with the motion styles in the page', async () => {
  const { castCss, castHtml } = await import('./brand.mjs');
  const html = read('index.html');
  const section = html.match(/<section class="hero">[\s\S]*?<\/section>/)[0];
  assert.ok(section.includes(castHtml()));
  assert.ok(!html.includes('<!-- HERO_CAST -->'));
  const shapes = [...section.matchAll(/<svg [^>]*data-shape="([\w-]+)"/g)].map((m) => m[1]);
  assert.equal(shapes.length, 13);
  assert.equal(shapes.filter((s) => s === 'alpi-twin').length, 1);
  assert.equal(new Set(shapes).size, 13);
  const head = html.slice(0, html.indexOf('</head>'));
  assert.ok(head.includes(`<style>\n${castCss()}\n</style>`));
});

const CAST_PX = { desktop: 68, twin: 110, phone: 52, middle: 44, phoneTwin: 76 };

test('the cast shrinks at desktop widths so the console shows above the fold, and wraps around Twin on a phone', () => {
  const css = landingCss();
  const base = css.match(/\n {2}\.cast\{--m:min\((\d+)px, calc\(\(100vw - var\(--space\) \* 2\) \/ ([\d.]+)\)\);--twin:calc\(var\(--m\) \* ([\d.]+)\)/);
  assert.ok(base);
  assert.equal(Number(base[1]), CAST_PX.desktop);
  assert.equal(Math.round(CAST_PX.desktop * Number(base[3])), CAST_PX.twin);
  const row = 12 * CAST_PX.desktop + CAST_PX.twin;
  assert.ok(row + 13 * CAST_PX.desktop * 0.2 < 1280, 'one row fits the 1280 shell');
  const phone = css.match(/@media\(max-width:720px\)\{[\s\S]*?\.cast\{--m:min\((\d+)px, calc\(\(100vw - var\(--space\) \* 2\) \/ ([\d.]+)\)\);--mid:calc\(var\(--m\) \* ([\d.]+)\);--twin:calc\(var\(--m\) \* ([\d.]+)\);flex-wrap:wrap/);
  assert.ok(phone);
  assert.equal(Number(phone[1]), CAST_PX.phone);
  assert.equal(Math.round(CAST_PX.phone * Number(phone[3])), CAST_PX.middle);
  assert.equal(Math.round(CAST_PX.phone * Number(phone[4])), CAST_PX.phoneTwin);
  assert.ok(/@media\(max-width:720px\)\{[\s\S]*?\.cast-break\{display:block;flex-basis:100%;height:0\}/.test(css));
  const cast = read('index.html').match(/<div class="cast"[\s\S]*?<\/span><\/span><\/div>/)[0];
  const seq = [...cast.matchAll(/class="cast-(item|break)/g)].map((m) => m[1]);
  assert.deepEqual(seq.join(' ').split('break').map((part) => part.trim().split(' ').filter(Boolean).length), [4, 5, 4]);
  const phoneWidth = 390 - 2 * 24;
  assert.ok(4 * CAST_PX.middle + CAST_PX.phoneTwin + 4 * CAST_PX.phone * 0.36 <= phoneWidth, 'the middle row fits 390 px');
});

test('the cast and every block of live marks pause while off screen', () => {
  const html = read('index.html');
  assert.ok(html.includes("entries.forEach((entry) => entry.target.classList.toggle('is-away', !entry.isIntersecting))"));
  assert.ok(html.includes("document.querySelectorAll('.cast, .marks-live').forEach((el) => away.observe(el))"));
  assert.ok(html.includes('.is-away .am-a,.is-away .vt-a{animation-play-state:paused}'));
  const sections = visible(html).match(/<section[\s\S]*?<\/section>/g);
  const moving = sections.filter((part) => /class="vt-a vt-turn-/.test(part));
  assert.equal(moving.length, 5);
  for (const part of moving) assert.match(part, /class="(cast|[^"]*\bmarks-live\b[^"]*)"/, part.slice(0, 80));
  assert.ok(!/requestAnimationFrame/.test(html));
});

test('the cast holds every still pose under reduced motion', () => {
  const html = read('index.html');
  assert.ok(html.includes('@media (prefers-reduced-motion:reduce){.am-a,.vt-a{animation:none}}'));
  const cast = html.match(/<div class="cast"[\s\S]*?<\/span><\/span><\/div>/)[0];
  assert.ok(!/<animate/.test(cast));
  for (const svg of cast.match(/<svg [^>]*>/g)) assert.match(svg, /style="--d:-?[\d.]+s;transform:rotateY\(/);
});

test('the cast tooltips show on hover and keyboard focus, never move the mark, and keep the edges on screen', () => {
  const css = landingCss();
  assert.ok(css.includes('.cast-item:hover .cast-tip,.cast-item:focus-visible .cast-tip{opacity:1}'));
  assert.ok(/\.cast-tip\{[^}]*opacity:0[^}]*font-size:var\(--t-small\)/.test(css));
  assert.ok(css.includes('.cast-first .cast-tip{left:0;translate:none}'));
  assert.ok(css.includes('.cast-start .cast-tip{left:0;right:auto;translate:none}'));
  assert.ok(css.includes('.cast-end .cast-tip{left:auto;right:0;translate:none}'));
  assert.ok(css.includes('.cast-twin .mark-body{fill:var(--brand-ink)}'));
});

test('the hero CTA pair is the macOS download pill and the copyable mono install pill', async () => {
  const { copyButton } = await import('./copy.mjs');
  const html = read('index.html');
  const cta = html.match(/<div class="hero-cta">[\s\S]*?<\/button>\s*<\/div>/)[0];
  assert.match(cta, /<a class="btn btn-primary" href="https:\/\/github\.com\/satoshi-ltd\/alpi\/releases\/download\/desktop-latest\/alpi-latest\.dmg"><svg [^>]*aria-hidden="true">[\s\S]*?<\/svg>Download for macOS<\/a>/);
  assert.ok(cta.includes(copyButton({ text: 'uv tool install alpi-agent', shown: 'uv tool install alpi-agent', label: 'Copy the install command: uv tool install alpi-agent', className: 'btn btn-ghost hero-copy' })));
  assert.ok(!/Copied<\/span>\s*<\/div>|class="hero-copied"/.test(cta));
  assert.ok(landingCss().includes('.btn.hero-copy{cursor:pointer;font-family:var(--font-mono);font-size:var(--t-mono)}'));
});

test('every copy affordance on the site swaps in place and announces through one live region', async () => {
  const { copyButton, copyScript } = await import('./copy.mjs');
  const html = read('index.html');
  const buttons = html.match(/<button class="copy[^"]*"[\s\S]*?<\/button>/g);
  assert.equal(buttons.length, 3);
  assert.ok(html.includes(copyButton({ text: 'uv tool install alpi-agent', shown: 'uv tool install alpi-agent', label: 'Copy the install command: uv tool install alpi-agent', className: 'pullcmd' })));
  assert.ok(/data-copy="docker pull satoshiltd\/alpi:latest"/.test(html));
  assert.ok(!/class="pullcmd"(?![^>]*type="button")/.test(html.replace(/<style>[\s\S]*?<\/style>/g, '')));
  assert.ok(html.includes(copyScript()));
  assert.ok(!/aria-live/.test(html.replace(copyScript(), '')));
  const doc = read('doc.js');
  assert.ok(!doc.includes('__COPY_BUTTON__'));
  assert.ok(doc.includes(JSON.stringify(copyButton({ shown: 'Copy', label: 'Copy code' }))));
  assert.ok(doc.includes(copyScript()));
  assert.ok(!/textContent = 'copied'/.test(doc));
});

test('focus rings show for the keyboard only, in the design system ring', async () => {
  const { palettes } = await import('../../common/tokens.mjs');
  const [dark, light] = read('tokens.css').split(':root[data-theme="light"]');
  assert.ok(dark.includes(`--focus:${palettes.dark.focus}`) && light.includes(`--focus:${palettes.light.focus}`));
  for (const css of [landingCss(), read('doc.css')]) {
    assert.match(css, /button:focus-visible[^{]*\{outline:2px solid var\(--focus\);outline-offset:2px\}/);
    assert.ok(css.includes(':focus:not(:focus-visible){outline:none}'));
    assert.ok(!/button:focus(?!-visible|:not)/.test(css));
  }
});

test('the console sits below the cast on a soft 20 px card in the page theme', () => {
  const css = landingCss();
  assert.ok(css.includes('.hero-scene{width:min(960px, 100%);min-width:0;position:relative}'));
  assert.match(read('demo.css'), /\.alpi-term\{[^}]*background:var\(--t-bg\);[^}]*border-radius:var\(--r-surface\)/);
  const section = read('index.html').match(/<section class="hero">[\s\S]*?<\/section>/)[0];
  assert.ok(section.indexOf('class="cast"') < section.indexOf('<div class="hero-scene">'));
  assert.ok(section.includes('<p class="scene-caption"><b>One daemon.</b> Your terminal, desktop and phone.</p>'));
});

test('the hero pass pauses while the hero is off screen', () => {
  const html = read('index.html');
  assert.match(html, /IntersectionObserver\(\(\[entry\]\) => hero\.classList\.toggle\('is-away', !entry\.isIntersecting\)\)\.observe\(hero\)/);
  assert.ok(read('brand.css').includes('.hero.is-away h1 .display-agents{animation-play-state:paused}'));
});

test('favicon, brand art and social card are generated from the shared sources', () => {
  assert.ok(read('index.html').includes('rel="icon" href="assets/alpi-favicon.svg"'));
  for (const name of ['alpi-favicon.svg', 'alpi-brand.svg', 'alpi-social.svg']) {
    assert.equal(readFileSync(join(site, 'assets', name), 'utf8'), read(`assets/${name}`), name);
  }
  const favicon = read('assets/alpi-favicon.svg');
  assert.ok(!favicon.includes('<polygon'));
  assert.equal([...favicon.matchAll(/<path d="[^"]+" fill="#14110c" fill-rule="evenodd"\/>/g)].length, 1);
  assert.equal(favicon.match(/ d="([^"]+)"/)[1].match(/M/g).length, 3);
  for (const name of ['alpi-brand.svg', 'alpi-social.svg']) assert.ok(!/polygon|Gradient|crease/.test(read(`assets/${name}`)), name);
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

test('the solid lockup wins the cascade over the page brand rules', () => {
  const css = read('brand.css');
  const rule = css.match(/:root \.logo \.logo-word\.display\{([^}]*)\}/)[1];
  for (const part of ['color:var(--brand-ink)', 'font-weight:800', 'letter-spacing:-.04em']) assert.ok(rule.includes(part), part);
  const page = read('index.html');
  const brandRule = page.match(/\.brand \.logo-word\{[^}]*\}/);
  assert.ok(!brandRule || !/(^|[^-])!important/.test(brandRule[0]));
});

test('the hero console draws each profile as its shape mark in its own colour', async () => {
  const { IDENTITIES } = await import('./brand.mjs');
  const hex = (shape) => IDENTITIES.find((i) => i.shape === shape).hex;
  const demo = read('demo.js');
  assert.ok(!demo.includes('__PROFILES__'));
  assert.ok(!/[⬟⌃▴]/.test(demo));
  const profiles = JSON.parse(demo.match(/const PROFILES = (\{.*?\});\n/)[1]);
  assert.deepEqual(Object.keys(profiles).sort(), ['builder', 'librarian', 'reviewer']);
  assert.equal(profiles.reviewer.color, hex('bell'));
  assert.equal(profiles.librarian.color, hex('pebble'));
  assert.equal(profiles.builder.color, hex('pill'));
  for (const { mark } of Object.values(profiles)) {
    assert.match(mark, /^<svg [^>]*viewBox="0 0 100 100"/);
    assert.ok(!mark.includes('<polygon') && mark.includes('class="mark-eye"') && !mark.includes('evenodd'));
  }
  assert.ok(!read('demo.css').includes('polygon'));
});

test('profile names wear their shape and solid type in their name tone on both themes, and every section heading takes the display type', async () => {
  const { nameTone } = await import('../../common/name.mjs');
  const { IDENTITIES, NIGHT, PAPER } = await import('./brand.mjs');
  const hex = (shape) => IDENTITIES.find((i) => i.shape === shape).hex;
  const landing = read('index.html');
  assert.ok(!landing.includes('<!-- PROFILE'));
  const names = [...landing.matchAll(/<span class="profile-name">(?:<span class="live-mark"[^>]*>)?<svg [^>]*aria-hidden="true"[^>]*data-shape="(\w+)"[\s\S]*?<\/svg>(?:<\/span>)?<span class="display display-name" style="--name-night:([^;]+);--name-paper:([^"]+)">(\w+)<\/span><\/span>/g)].map((m) => [m[0], m[1], m[1], m[2], m[3], m[4]]);
  assert.deepEqual(names.map((m) => [m[5], m[2]]), [
    ['reviewer', 'bell'], ['librarian', 'pebble'],
    ['reviewer', 'bell'], ['librarian', 'pebble'], ['researcher', 'clover'],
    ['reviewer', 'bell'], ['librarian', 'pebble'],
  ]);
  for (const [, , shape, night, paper] of names) {
    assert.equal(night, nameTone(hex(shape), NIGHT));
    assert.equal(paper, nameTone(hex(shape), PAPER));
  }
  assert.equal([...landing.matchAll(/<h2(?![^>]*display-heading)[^>]*>/g)].length, 0);
});

test('the console follows the page theme on a 20 px card, with pill controls', () => {
  assert.ok(!/data-alpi-demo/.test(read('tokens.css')));
  const css = read('demo.css');
  assert.match(css, /\.alpi-term\{[^}]*background:var\(--t-bg\);[^}]*border-radius:var\(--r-surface\)/);
  assert.match(css, /\.alpi-term-foot button\{[^}]*border-radius:var\(--r-pill\)/);
  assert.match(css, /\.alpi-term-input\{[^}]*border-radius:var\(--r-surface\)/);
  const demo = read('demo.js');
  for (const label of ['Restart', 'Back', 'Next']) assert.ok(demo.includes(`type="button">${label}</button>`), label);
  assert.ok(demo.includes('`Step ${idx+1} · '));
  assert.match(read('index.html'), /<section class="hero">[\s\S]*?<div data-alpi-demo data-scene-set="hero"/);
});

test('the bundler thumbnail is Twin and the wordmark on the light page ground', async () => {
  const { palettes } = await import('../../common/tokens.mjs');
  const thumb = read('index.html').match(/<template id="__bundler_thumbnail" data-bg-color="([^"]+)">([\s\S]*?)<\/template>/);
  assert.ok(thumb);
  assert.equal(thumb[1], palettes.light.bg);
  assert.ok(thumb[2].includes(`fill="${INK}" fill-rule="evenodd"`));
  assert.ok(thumb[2].includes('>alpi</text>'));
  assert.ok(!/monospace|\/\/\/|#0c0b09|#3d3830|#7a746a|PRIVATE AGENT/.test(thumb[2]));
});

test('no page carries the animated ascii background', () => {
  for (const page of [...pages(), 'doc.js', 'doc.css']) {
    const html = read(page);
    assert.ok(!/ascii-bg|ascii-pre|ASCII BACKGROUND/.test(html), page);
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
const declarations = css => rules(css).flatMap(({ selector, body }) => body.split(';').map(d => d.trim()).filter(Boolean).map(d => {
  const at = d.indexOf(':');
  return { selector, prop: d.slice(0, at).trim(), value: d.slice(at + 1).trim() };
}));
const ROLE = /^var\(--r-(xs|control|surface|sheet|pill)\)$/;
const radiusOf = (css, selector) => {
  const rule = rules(css).find(r => r.selector === selector && /border-radius:/.test(r.body));
  return rule && rule.body.match(/border-radius:([^;}]+)/)[1].trim();
};

test('radii by role: pills for what you press, 12 for tags and chips, 20 for cards and the console, 28 for panels that hold cards', () => {
  for (const [name, css] of Object.entries(styleSources())) {
    for (const { value } of declarations(css).filter(d => d.prop === 'border-radius')) {
      assert.ok(value === '50%' || value.split(/\s+/).every(part => part === '0' || ROLE.test(part)), `${name}: border-radius:${value}`);
    }
    assert.ok(!/backdrop-filter/.test(css), `${name}: backdrop-filter`);
    assert.ok(!/umber|#4a3006/i.test(css), `${name}: umber`);
    assert.ok(!/(?<!mask-image:)(linear|radial)-gradient/.test(css.replace(/(-webkit-)?mask-image:[^;]+;/g, '')), `${name}: gradient`);
    assert.ok(!/:hover[^{]*\{[^}]*transform/.test(css), `${name}: hover transform`);
    assert.ok(!/#[0-9a-f]{3,8}\b|rgba?\(/i.test(css.replace(/(-webkit-)?mask-image:[^;]+;/g, '')), `${name}: colour literal`);
  }
  const { 'landing.html': landing, 'doc.css': doc, 'demo.css': demo, footer } = styleSources();
  const expect = {
    pill: [[landing, '.btn'], [landing, '.hero .kicker'], [landing, '.burger'], [landing, '.grant'], [landing, '.network-trigger'], [doc, '.chip'], [doc, '.post-cta .btn'], [doc, '.md pre .copy'], [doc, '.docnav-m,.toc-m'], [demo, '.alpi-term-foot button'], [footer, '.theme-btn']],
    control: [[landing, '.network-alp'], [landing, '.pullcmd'], [landing, '.cast-tip'], [landing, '.cast-item'], [doc, '.dochead .meta .ver'], [doc, '.docrail a,.docnav-m nav a'], [footer, 'footer .sig .ver']],
    surface: [[landing, '.surface'], [landing, '.prof'], [landing, '.network-machine'], [landing, '.network-report'], [landing, '.state-row'], [landing, '.stage-desk'], [landing, '.rung'], [landing, '.verbs'], [landing, '.counter'], [landing, '.qa details'], [doc, '.md pre'], [doc, '.pg'], [doc, '.post-lead'], [doc, '.docs-start a'], [doc, '.post-cta'], [demo, '.alpi-term']],
    sheet: [[landing, '.feature'], [landing, '.network-figure'], [landing, '.states-list']],
    xs: [[landing, 'p .mono,li .mono,.cell .mono'], [doc, '.md code']],
  };
  for (const [role, items] of Object.entries(expect)) {
    for (const [css, selector] of items) assert.equal(radiusOf(css, selector), `var(--r-${role})`, selector);
  }
});

test('no grey rules: no seam, no hairline borders and no shadows between sections, cells, steps, questions, the nav or cards', () => {
  assert.ok(!read('tokens.css').includes('--seam'));
  for (const [name, css] of Object.entries(styleSources())) {
    for (const { selector, prop, value } of declarations(css)) {
      if (prop === 'box-shadow') assert.equal(value, 'none', `${name}: ${selector} box-shadow:${value}`);
      if (!/^border(-(top|right|bottom|left|block|inline))?(-(color|width|style))?$/.test(prop)) continue;
      if (selector === '.alpi-term-body .said') continue;
      assert.ok(/^(0|none|transparent)$/.test(value), `${name}: ${selector} ${prop}:${value}`);
    }
    assert.ok(!/var\(--(seam|accent-line|term-line)\)/.test(css), name);
  }
  const landing = styleSources()['landing.html'];
  for (const selector of ['nav.top', '.strip', '.cell', '.steps li', '.qa details', '.questions-grid', '.feature', '.surface']) {
    const found = rules(landing).filter(r => r.selector === selector);
    assert.ok(found.length, selector);
    for (const rule of found) assert.ok(!/border|box-shadow/.test(rule.body.replace(/border-radius:[^;]+;?/g, '')), selector);
  }
});

test('type follows the apps ladder with its 12 px floor; mono only for machine text at 0.92 em', async () => {
  const { typeLadder, typeFloor, monoScale } = await import('../../common/tokens.mjs');
  const tokens = read('tokens.css');
  for (const [step, size] of Object.entries(typeLadder)) assert.ok(tokens.includes(`--t-${step}:${size}px`), step);
  assert.ok(tokens.includes(`--t-mono:${monoScale}em`));
  const STEP = /^var\(--t-(meta|small|ui|read|title|display|hero|headline|mono)\)$/;
  for (const [name, css] of Object.entries(styleSources())) {
    for (const { selector, prop, value } of declarations(css)) {
      if (prop === 'font-size' && !STEP.test(value) && value !== 'inherit') {
        const sizes = [...value.matchAll(/(\d+(?:\.\d+)?)px/g)].map(m => Number(m[1]));
        assert.ok(/^(min|clamp)\(/.test(value) && sizes.length && sizes.every(n => n >= typeFloor), `${name}: ${selector} font-size:${value}`);
      }
      if (prop === 'font' && value !== 'inherit') assert.match(value, /^var\(--t-[a-z]+\)\/[\d.]+ var\(--font-(sans|mono)\)$/, `${name}: ${selector} font:${value}`);
      if (prop === 'font-family' && value === 'var(--font-mono)') {
        const body = rules(css).find(r => r.selector === selector && r.body.includes('var(--font-mono)')).body;
        assert.ok(!/font-size/.test(body) || /font-size:(var\(--t-mono\)|inherit)/.test(body), `${name}: ${selector} sets mono off the 0.92 em step`);
      }
    }
    assert.ok(!/"Geist Mono"|ui-monospace/.test(css), `${name}: mono stack outside the token`);
  }
  for (const page of ['index.html', 'docs/QUICKSTART.html', 'blog/index.html']) {
    for (const [, style] of read(page).matchAll(/style="([^"]*)"/g)) assert.ok(!/font-size/.test(style), `${page}: ${style}`);
  }
});

test('labels speak in sentence case: no uppercase transform, no tracked caps, no all-caps eyebrow, label or crumb', () => {
  for (const [name, css] of Object.entries({ ...styleSources(), 'brand.css': read('brand.css') })) {
    assert.ok(!/text-transform:\s*(uppercase|lowercase)/.test(css), `${name}: text-transform`);
    for (const { selector, value } of declarations(css).filter(d => d.prop === 'letter-spacing')) {
      assert.ok(Number.parseFloat(value) <= 0, `${name}: ${selector} letter-spacing:${value}`);
    }
  }
  const caps = /^[^a-z]*[A-Z]{3,}[^a-z]*$/;
  const landing = read('index.html');
  const doc = read('docs/QUICKSTART.html');
  const texts = [
    ...[...landing.matchAll(/<div class="eyebrow">(?:<b>\d+<\/b>)?([^<]+)<\/div>/g)].map(m => m[1]),
    ...[...landing.matchAll(/<span class="(?:n|lbl|pill|tag|state-label|machine-location)">([^<]+)<\/span>/g)].map(m => m[1]),
    ...[...landing.matchAll(/<h5>([^<]+)<\/h5>/g)].map(m => m[1]),
    ...[...doc.matchAll(/class="bp-seg[^"]*"[^>]*>([^<]+)</g)].map(m => m[1]),
    ...[...doc.matchAll(/<p class="rail-h">([^<]+)<\/p>/g)].map(m => m[1]),
  ];
  assert.ok(texts.length > 30, String(texts.length));
  for (const text of texts.filter(t => !/^ALP\.\d$/.test(t))) assert.ok(!caps.test(text.trim()), text);
  assert.ok(landing.includes('<div class="eyebrow"><b>01</b>The unit you own is the profile</div>'));
});

test('every colour, corner and type step comes from the shared tokens, light and dark', async () => {
  const { palettes, radii, fontStacks } = await import('../../common/tokens.mjs');
  const [dark, light] = read('tokens.css').split(':root[data-theme="light"]');
  for (const key of ['bg', 'bgPane', 'ink', 'ink2', 'ink3', 'line', 'line2', 'hover', 'selected']) {
    assert.ok(dark.includes(palettes.dark[key]), `dark ${key}`);
    assert.ok(light.includes(palettes.light[key]), `light ${key}`);
  }
  for (const role of ['xs', 'control', 'surface', 'sheet', 'pill']) assert.ok(dark.includes(`--r-${role}:${radii[role]}px`), role);
  assert.ok(dark.includes(`--font-sans:${fontStacks.sans}`) && dark.includes(`--font-mono:${fontStacks.mono}`));
  for (const page of pages()) assert.equal([...read(page).matchAll(/tokens\.css\?v=/g)].length, 1, page);
});

test('cards, terminal, counters and panels sit on the fill surface, apart from the page ground, with the theme eye ink', async () => {
  const { palettes } = await import('../../common/tokens.mjs');
  const [dark, light] = read('tokens.css').split(':root[data-theme="light"]');
  const vars = (css) => Object.fromEntries([...css.matchAll(/(--[a-z0-9-]+):([^;}]+)/g)].map((m) => [m[1], m[2]]));
  for (const [css, mode] of [[dark, 'dark'], [light, 'light']]) {
    const v = vars(css);
    for (const name of ['--pane', '--soft', '--panel-bg', '--panel-soft', '--term-bg']) {
      assert.equal(v[name], palettes[mode].fill, `${mode} ${name}`);
      assert.notEqual(v[name], v['--bg'], `${mode} ${name} vs --bg`);
    }
    assert.equal(v['--mark-eye'], palettes[mode].markEye, `${mode} --mark-eye`);
  }
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
  assert.ok(page.includes('<h1 class="display display-heading">Quickstart</h1>'));
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

test('the landing links the Android app on Google Play, and the App Store is no link while iOS is in testing', () => {
  const apps = section('apps');
  assert.match(apps, /<a class="btn btn-ground" href="https:\/\/play\.google\.com\/store\/apps\/details\?id=com\.satoshilimited\.alpi"><svg [^>]*aria-hidden="true">[\s\S]*?<\/svg>Google Play<\/a>/);
  assert.match(apps, /<p class="meta">iOS in internal testing<\/p>/);
  assert.doesNotMatch(read('index.html'), /apps\.apple\.com|App Store/);
});

test('the docs rail is the app sidebar: side ground, 40 px rows of radius 12 and the current page on the selected fill', () => {
  const doc = read('doc.css');
  const body = selector => rules(doc).find(r => r.selector === selector).body;
  assert.match(body('.docrail'), /background:var\(--band\)/);
  assert.match(body('.docrail'), /border-radius:var\(--r-surface\)/);
  const row = body('.docrail a,.docnav-m nav a');
  assert.match(row, /min-height:40px/);
  assert.match(row, /border-radius:var\(--r-control\)/);
  assert.match(row, /font-size:var\(--t-ui\)/);
  assert.match(body('.docrail a[aria-current="page"],.docnav-m a[aria-current="page"]'), /background:var\(--selected\)/);
  assert.match(body('.docrail .rail-h,.docnav-m .rail-h'), /font-size:var\(--t-small\)/);
  for (const page of readdirSync(join(dist, 'docs')).filter(n => n.endsWith('.html') && n !== 'index.html' && n !== 'ROADMAP.html')) {
    const rail = read(join('docs', page)).match(/<nav class="docrail" aria-label="Documentation">([\s\S]*?)<\/nav>/)[1];
    assert.equal([...rail.matchAll(/aria-current="page"/g)].length, 1, page);
    assert.ok(rail.includes(`<a href="${page}" aria-current="page">`), page);
  }
});

test('a doc reads like the app: Bricolage title, Geist meta with the version as a chip, Geist 28 headings and code on soft cards with no rule', () => {
  const page = read('docs/QUICKSTART.html');
  const doc = read('doc.css');
  const body = selector => rules(doc).find(r => r.selector === selector).body;
  const version = readFileSync(join(site, '../pyproject.toml'), 'utf8').match(/^version\s*=\s*"([^"]+)"/m)[1];
  assert.ok(page.includes('<h1 class="display display-heading">Quickstart</h1>'));
  assert.ok(page.includes(`<span class="d">·</span><code class="ver">v${version}</code>`));
  assert.match(page, /<div class="meta">\s*<span>Start<\/span><span class="d">·<\/span><span>\d+ min read<\/span>/);
  assert.match(body('.md h2'), /font-size:var\(--t-display\)/);
  assert.ok(!/border|box-shadow|padding-top/.test(body('.md h2')));
  assert.ok(!/border|box-shadow/.test(body('.dochead')));
  assert.match(body('.md pre'), /background:var\(--soft\)/);
  assert.match(body('.md pre'), /border-radius:var\(--r-surface\)/);
  assert.match(body('.md pre'), /font-size:var\(--t-mono\)/);
  assert.match(body('.md code'), /border-radius:var\(--r-xs\)/);
  assert.ok(!/border/.test(body('.toc ol')));
  assert.match(body('.toc a.on'), /color:var\(--fg\)/);
  assert.match(page, /<details class="docnav-m">[\s\S]*?<details class="toc-m"><summary>On this page<\/summary>/);
  assert.match(rules(doc).find(r => r.selector === '.docnav-m,.toc-m' && /border-radius/.test(r.body)).body, /border-radius:var\(--r-pill\);background:var\(--soft\)/);
  assert.ok(page.includes('<div data-alpi-demo class="demo-console"></div>'));
});

const navOf = (page) => read(page).match(/<nav class="top[^"]*">[\s\S]*?<\/nav>/)[0];

test('the nav carries no install pill and no GitHub; Get alpi joins once the hero has scrolled away and always on docs and blog', () => {
  for (const page of pages()) {
    const nav = navOf(page);
    assert.ok(!/nav-cta|<code>|uv tool install/.test(nav), page);
    assert.ok(!/github/i.test(nav), page);
    const href = page === 'index.html' ? '#apps' : '../index.html#apps';
    assert.ok(nav.includes(`<a href="${href}" class="nav-get">Get alpi</a>`), page);
  }
  const drawer = navOf('index.html').match(/<div class="nav-drawer"[\s\S]*?<\/div>/)[0];
  assert.match(drawer, /<a href="#apps" class="drawer-get">Get alpi<\/a>\s*<\/div>$/);
  const css = landingCss();
  assert.ok(css.includes('nav.top .nav-get{visibility:hidden;opacity:0;'));
  assert.ok(css.includes('body:has(.hero.is-away) nav.top .nav-get{visibility:visible;opacity:1}'));
  assert.ok(!/nav-get/.test(read('doc.css')));
  const brand = read('brand.css');
  assert.match(brand, /\.nav-get,\.drawer-get\{[^}]*min-height:40px[^}]*border-radius:var\(--r-pill\);background:var\(--fg\);color:var\(--bg\)/);
  assert.ok(brand.includes('@media (max-width:760px){nav.has-menu .nav-get{display:none}}'));
  assert.ok(navOf('index.html') && !/has-menu/.test(read(pages().find((p) => p !== 'index.html')).match(/<nav class="top[^"]*">/)[0]));
  assert.ok(!/nav-cta/.test(css + read('doc.css')));
});

test('the footer has three columns with no label twice, GitHub once as a quiet source link, and signs off with the twelve still shapes', async () => {
  const { familyRow } = await import('./brand.mjs');
  for (const page of pages()) {
    const footer = read(page).match(/<footer>[\s\S]*?<\/footer>/)[0];
    assert.deepEqual([...footer.matchAll(/<h5>([^<]+)<\/h5>/g)].map((m) => m[1]), ['Guides', 'Reference', 'Project'], page);
    const labels = [...footer.matchAll(/<li><a href="[^"]+">([^<]+)<\/a><\/li>/g)].map((m) => m[1]);
    assert.equal(new Set(labels).size, labels.length, page);
    assert.ok(labels.includes('ALP specification') && !labels.includes('ALP protocol'), page);
    assert.equal(labels.indexOf('Blog'), labels.indexOf('Deployments') + 1, page);
    assert.ok(!labels.includes('Writing') && !labels.includes('What alpi is'), page);
    assert.equal([...footer.matchAll(/href="https:\/\/github\.com\/satoshi-ltd\/alpi"/g)].length, 1, page);
    assert.match(footer, /<a class="source" href="https:\/\/github\.com\/satoshi-ltd\/alpi">source on GitHub<\/a><\/p>/);
    assert.ok(!/>GitHub</.test(footer), page);
    assert.ok(footer.includes(familyRow(20)), page);
    assert.equal([...familyRow(20).matchAll(/<svg /g)].length, 12);
  }
  assert.match(styleSources().footer, /footer \.attr a\.source\{color:var\(--muted\)/);
});

test('the claims are four checked lines, one centred row on a desktop and one per line on a phone', () => {
  const strip = read('index.html').match(/<div class="strip">[\s\S]*?<\/div>\s*<\/div>/)[0];
  assert.equal([...strip.matchAll(/<svg class="check"/g)].length, 4);
  assert.ok(!/&#10033;|class="mk"/.test(strip));
  const css = landingCss();
  assert.match(css, /\n {2}\.strip\{[^}]*justify-content:center/);
  assert.match(css, /\.strip div\{[^}]*white-space:nowrap/);
  assert.match(css, /@media\(max-width:720px\)\{[\s\S]*?\.strip\{flex-direction:column;align-items:flex-start/);
});

test('the story figure draws no rules and plays the states: both machines working, the report done', () => {
  const story = visible(read('index.html')).match(/<section class="story" id="in-practice"[\s\S]*?<\/section>/)[0];
  assert.ok(!/network-route|network-link|agent-memory|network-permission|<line|<hr/.test(story));
  for (const [, box] of story.matchAll(/<svg [^>]*viewBox="([^"]+)"/g)) assert.ok(['0 0 24 24', '0 0 100 100'].includes(box), box);
  const marks = [...story.matchAll(/data-shape="(\w+)" data-state="(\w+)"/g)].map((m) => `${m[1]} ${m[2]}`);
  assert.deepEqual(marks, ['bell working', 'pebble working', 'bell done']);
  assert.match(story, /<div class="report-label"><span class="live-mark" style="--size:20px" aria-hidden="true">/);
  assert.match(story, /<span class="network-alp">ALP<\/span>/);
  const sub = story.match(/<p class="sub">([^<]+)<\/p>/)[1];
  assert.ok(sub.split(/\.\s/).length <= 2, sub);
  assert.match(landingCss(), /\.network-machines\{display:grid;grid-template-columns:minmax\(0,1fr\) auto minmax\(0,1fr\)/);
});

test('“You can tell at a glance” names the five states between the story and 01, drawn like the apps', async () => {
  const { statesHtml } = await import('./brand.mjs');
  const html = read('index.html');
  const at = (id) => html.indexOf(`id="${id}"`);
  assert.ok(at('in-practice') < at('states') && at('states') < at('what'));
  const states = section('states');
  assert.ok(states.includes(statesHtml()));
  assert.match(states, /<h2 id="states-title" class="display display-heading">You can tell at a glance\.<\/h2>/);
  assert.equal([...states.matchAll(/<li class="state-row"><span class="live-mark"[^>]*aria-hidden="true">/g)].length, 5);
  assert.ok(!/aria-label/.test(states.replace(/aria-labelledby/g, '')));
  assert.match(landingCss(), /@media\(max-width:1000px\)\{[\s\S]*?\.states-layout\{grid-template-columns:1fr/);
});

test('profiles and setup say each fact once, and the profile cards show their state at 40 px', () => {
  const what = visible(section('what'));
  const how = visible(read('index.html').match(/<section id="how">[\s\S]*?<\/section>/)[0]);
  const cards = [...what.matchAll(/<span class="nm"><span class="profile-name"><span class="live-mark" style="--size:40px" aria-hidden="true"><svg[^>]*data-shape="(\w+)" data-state="(\w+)"/g)].map((m) => `${m[1]} ${m[2]}`);
  assert.deepEqual(cards, ['bell working', 'pebble idle', 'clover failed']);
  assert.ok(!/class="tag"|>memory</.test(what));
  for (const [, p] of what.matchAll(/<div class="cell">[\s\S]*?<p>([\s\S]*?)<\/p>/g)) assert.ok(words(p).length <= 25, p);
  assert.equal([...what.matchAll(/<div class="cell">/g)].length, 6);
  assert.equal([...visible(read('index.html')).matchAll(/One daemon/g)].length, 1);
  assert.equal([...(what + how).matchAll(/before every model call/g)].length, 1);
  assert.ok(how.includes('Five decisions. Then it runs.'));
  assert.equal([...how.matchAll(/<li><span class="num">/g)].length, 5);
});

test('ALP is one panel: three rungs drawn with the marks, the rules in one line linking the protocol, no error codes', async () => {
  const { honeycomb } = await import('./brand.mjs');
  const html = read('index.html');
  assert.ok(!/-320\d\d/.test(visible(html)));
  const alp = section('alp');
  const rungs = alp.match(/<div class="rung">[\s\S]*?<\/p>\s*<\/div>/g);
  assert.equal(rungs.length, 3);
  assert.ok(rungs[2].includes(honeycomb('bell', 44)));
  assert.equal([...rungs[0].matchAll(/data-shape=/g)].length, 2);
  assert.equal([...rungs[1].matchAll(/data-shape=/g)].length, 2);
  for (const rung of rungs) assert.ok(!/aria-label/.test(rung) && /aria-hidden="true"/.test(rung));
  assert.match(alp, /<p class="rules">[^<]+<a class="link-inline" href="docs\/ALP\.html">Read the protocol/);
  assert.ok(!/<div class="grid c3"/.test(alp));
  const verbs = rules(landingCss()).find((r) => r.selector === '.verbs').body;
  assert.ok(!/overflow-x|white-space:pre/.test(verbs));
  assert.match(landingCss(), /@media\(max-width:620px\)\{[\s\S]*?\.verbs \.v,\.verbs \.c\{display:block;min-width:0\}/);
});

test('“Put alpi to work” shows the two apps on a stage in both themes, then three short cards with the install command once', () => {
  const apps = section('apps');
  for (const name of ['desktop', 'phone']) {
    for (const mode of ['light', 'dark']) {
      const file = `assets/stage-${name}-${mode}.png`;
      assert.ok(existsSync(join(dist, file)) && existsSync(join(site, file)), file);
      assert.match(apps, new RegExp(`<img class="stage-[a-z]+ shot-${mode}" src="${file}" width="\\d+" height="\\d+" alt="[^"]{20,}" loading="lazy"`));
    }
  }
  const css = landingCss();
  assert.ok(css.includes(':root[data-theme="light"] .shot-dark,:root:not([data-theme="light"]) .shot-light{display:none}'));
  assert.match(css, /@media\(max-width:720px\)\{[\s\S]*?\.stage \.stage-desk\{display:none\}/);
  assert.deepEqual([...apps.matchAll(/<div class="surface">\s*<h3>([^<]+)<\/h3>/g)].map((m) => m[1]), ['Desktop', 'Phone', 'Terminal and server']);
  assert.equal([...apps.matchAll(/data-copy="uv tool install alpi-agent"/g)].length, 1);
  assert.ok(!/<pre|ascii-diagram/.test(apps));
  assert.match(apps, /<p class="licence">[^<]+<a class="link-inline" href="docs\/LICENSE\.html">Read the licence/);
});

test('the desktop window is its own frame on a wide screen, and a phone shows only the phone app', () => {
  const css = landingCss();
  const rule = (selector) => rules(css).find((r) => r.selector === selector).body;
  assert.equal(rule('.stage'), 'margin-top:16px');
  assert.match(rule('.stage-desk'), /^width:100%;border-radius:var\(--r-surface\);outline:1px solid var\(--line\);outline-offset:-1px;filter:drop-shadow\(0 24px 64px var\(--lift\)\)$/);
  assert.ok(css.includes('@media not (max-width:720px){.stage .stage-phone{display:none}}'));
  const small = css.match(/@media\(max-width:720px\)\{[\s\S]*?\.stage \.stage-desk\{display:none\}[\s\S]*?\n  \}/)[0];
  assert.ok(small.includes('.stage-phone{width:min(280px,76%);margin:0 auto;filter:drop-shadow(0 24px 48px var(--lift))}'));
  const size = (name) => { const png = readFileSync(join(site, `assets/stage-${name}-light.png`)); return [png.readUInt32BE(16), png.readUInt32BE(20)]; };
  const apps = section('apps');
  for (const name of ['desktop', 'phone']) {
    const [w, h] = size(name);
    for (const mode of ['light', 'dark']) {
      const png = readFileSync(join(site, `assets/stage-${name}-${mode}.png`));
      assert.deepEqual([png.readUInt32BE(16), png.readUInt32BE(20)], [w, h], `${name} ${mode}`);
    }
    assert.ok(apps.includes(`src="assets/stage-${name}-light.png" width="${w / 2}" height="${h / 2}"`), name);
  }
  assert.ok(!/drop-shadow\(0 2px 6px|stage-phone\{right/.test(css));
  const tokens = read('tokens.css');
  assert.match(tokens, /^:root\{[^}]*--lift:rgba\(0,0,0,[.\d]+\)/);
  assert.match(tokens, /:root\[data-theme="light"\]\{[^}]*--lift:rgba\(20,20,20,[.\d]+\)/);
});

test('the stage shots are exported by the design kit from its drawings', () => {
  const exporter = readFileSync(join(site, '../design/stage.py'), 'utf8');
  assert.ok(exporter.includes('from site_stage import SHOTS'));
  assert.ok(exporter.includes('for mode in ("light", "dark")'));
  assert.ok(exporter.includes('OUT / f"stage-{name}-{mode}.png"'));
  const drawings = readFileSync(join(site, '../design/src/site_stage.py'), 'utf8');
  assert.match(drawings, /SHOTS = \{"desktop": .*"phone": /);
});

test('the cast is one tab stop with arrow-key roving, and no mark beside a visible name is announced as a colour and shape', async () => {
  const { castScript, IDENTITIES } = await import('./brand.mjs');
  const html = read('index.html');
  const cast = html.match(/<div class="cast"[\s\S]*?<\/span><\/span><\/div>/)[0];
  assert.equal([...cast.matchAll(/tabindex="0"/g)].length, 1);
  assert.equal([...cast.matchAll(/tabindex="-1"/g)].length, 12);
  assert.ok(html.includes(castScript()));
  for (const page of pages()) {
    for (const { name } of IDENTITIES) assert.ok(!read(page).includes(`aria-label="${name}"`), `${page}: ${name}`);
  }
});

test('the blog sits in the reading column, its tags scroll in one row on a phone, and every post ends on Twin, the download and the copy pill', async () => {
  const { copyButton } = await import('./copy.mjs');
  const { twinBadge } = await import('./brand.mjs');
  const doc = read('doc.css');
  assert.match(doc, /\.blog-index\{width:min\(760px, 100% - var\(--space\) \* 2\)\}/);
  assert.match(doc, /@media\(max-width:720px\)\{\s*\.blog-index > \.chips\{flex-wrap:nowrap;overflow-x:auto;/);
  assert.ok(read('blog/index.html').includes('<main class="shell docs-index blog-index">'));
  const pill = copyButton({ text: 'uv tool install alpi-agent', shown: 'uv tool install alpi-agent', label: 'Copy the install command: uv tool install alpi-agent', className: 'btn btn-ghost post-copy' });
  const posts = readdirSync(join(dist, 'blog')).filter((n) => n.endsWith('.html') && n !== 'index.html' && !n.startsWith('tag-'));
  assert.ok(posts.length > 20);
  for (const name of posts) {
    const cta = read(`blog/${name}`).match(/<aside class="post-cta">[\s\S]*?<\/aside>/)[0];
    assert.ok(cta.includes(twinBadge(40)), name);
    assert.ok(cta.includes(pill), name);
    assert.match(cta, /<a class="btn btn-primary" href="https:\/\/github\.com\/satoshi-ltd\/alpi\/releases\/download\/desktop-latest\/alpi-latest\.dmg"><svg[\s\S]*?<\/svg>Download for macOS<\/a>/);
    assert.ok(!/<a [^>]*>(?:(?!<\/a>)[\s\S])*<code>/.test(cta), name);
    assert.ok(!/BUSL|#apps/.test(cta), name);
    assert.match(cta, /Free for individuals &middot; <a class="link-inline" href="\.\.\/docs\/LICENSE\.html">Read the licence/);
  }
});

test('heading ids keep GitHub double hyphens, so docs links copied from GitHub land on their section', async () => {
  const { renderMarkdown } = await import('./markdown.mjs');
  const out = renderMarkdown('## Persistent state — SQLite via the db tool\n');
  const html = typeof out === 'string' ? out : out.html;
  assert.match(html, /id="persistent-state--sqlite-via-the-db-tool"/);
  assert.match(read('docs/SKILLS.html'), /id="persistent-state--sqlite-via-the-db-tool"/);
});

test('the cast hover label sits on the page ground its name tones are computed for', () => {
  assert.match(landingCss(), /\.cast-tip\{[^}]*background:var\(--bg\)/);
});

test('the cast stacks above the console, so a hover label below a mark is never covered', () => {
  const cast = rules(landingCss()).find((r) => r.selector === '.cast').body;
  assert.match(cast, /;position:relative;z-index:7$/);
});

test('alpi in the hero follows the pointer like the desktop hero mark, only with a fine pointer, motion allowed and the hero on screen', () => {
  const html = read('index.html');
  assert.equal(read('gaze.js'), readFileSync(join(site, '../common/gaze.mjs'), 'utf8'));
  const twin = html.match(/<span class="cast-item cast-twin"[\s\S]*?<span class="cast-tip"/)[0];
  assert.match(twin, /<span class="cast-gaze"><svg[\s\S]*<g class="cast-look">/);
  assert.equal((html.match(/class="cast-gaze"/g) || []).length, 1);
  assert.equal((html.match(/class="cast-look"/g) || []).length, 1);
  const css = landingCss();
  assert.ok(css.includes('.cast-gaze{display:block;width:100%;height:100%;transform-style:preserve-3d;transform-origin:50% 55%;transform:rotateY(calc(var(--gx, 0) * 21.6deg)) rotateX(calc(var(--gy, 0) * -14.4deg))}'));
  assert.ok(css.includes('.cast-look{transform:translate(calc(var(--gx, 0) * 6px), calc(var(--gy, 0) * 4px))}'));
  assert.ok(css.includes('.cast-gaze.is-following .vt-a{animation:none;transform:none!important}'));
  assert.match(twin, /vt-turn-idle/);
  const script = html.match(/<script type="module">([\s\S]*?)<\/script>/)[1];
  assert.match(script, /import \{ followPointer \} from '\.\/gaze\.js\?v=\d+\.\d+\.\d+'/);
  assert.match(script, /matchMedia\('\(pointer: fine\)'\)/);
  assert.match(script, /prefers-reduced-motion: reduce/);
  assert.match(script, /is-away/);
  assert.match(script, /stop = followPointer\(twin\); twin\.classList\.add\('is-following'\);/);
  assert.match(script, /stop\(\); stop = null; twin\.classList\.remove\('is-following'\);/);
});

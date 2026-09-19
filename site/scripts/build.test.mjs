import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync } from 'node:child_process';
import { existsSync, readFileSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
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

import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseFrontmatter } from './markdown.mjs';

test('parses keys, arrays, and booleans; body excludes the block', () => {
  const { meta, body } = parseFrontmatter(
    '---\ntitle: Hello World\ndate: 2026-06-11\ndraft: false\ntags: [a, b, c]\n---\n\n# Hello\nBody text.\n',
  );
  assert.equal(meta.title, 'Hello World');
  assert.equal(meta.date, '2026-06-11');
  assert.equal(meta.draft, false);
  assert.deepEqual(meta.tags, ['a', 'b', 'c']);
  assert.ok(body.startsWith('# Hello'));
  assert.ok(!body.includes('title:'));
});

test('draft: true is a boolean true', () => {
  const { meta } = parseFrontmatter('---\ndraft: true\n---\nx');
  assert.equal(meta.draft, true);
});

test('strips surrounding quotes from string values', () => {
  const { meta } = parseFrontmatter('---\ntitle: "Quoted: with colon"\n---\nx');
  assert.equal(meta.title, 'Quoted: with colon');
});

test('no front-matter returns empty meta and untouched body', () => {
  const { meta, body } = parseFrontmatter('# Just markdown\ntext');
  assert.deepEqual(meta, {});
  assert.equal(body, '# Just markdown\ntext');
});

test('unterminated front-matter is left as body, not swallowed', () => {
  const src = '---\ntitle: oops\nno closing fence\n# heading';
  const { meta, body } = parseFrontmatter(src);
  assert.deepEqual(meta, {});
  assert.equal(body, src);
});

test('every post title is in sentence case, never Title Case', async () => {
  const { readdirSync, readFileSync } = await import('node:fs');
  const dir = new URL('../posts/', import.meta.url);
  const titleCase = (title) => {
    const long = title.split(/\s+/).slice(1).filter((w) => /^[A-Za-z][a-z'’]{3,}/.test(w));
    return long.length >= 3 && long.filter((w) => /^[A-Z]/.test(w)).length / long.length > 0.6;
  };
  assert.ok(titleCase("Agents Don't Know Who They're Talking To"));
  assert.ok(!titleCase('Agents don’t know who they’re talking to'));
  for (const name of readdirSync(dir).filter((n) => n.endsWith('.md'))) {
    const { meta, body } = parseFrontmatter(readFileSync(new URL(name, dir), 'utf8'));
    assert.ok(!titleCase(meta.title || ''), name);
    const h1 = body.match(/^#\s+(.+)$/m);
    if (h1) assert.ok(!titleCase(h1[1]), name);
  }
});

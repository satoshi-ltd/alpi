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

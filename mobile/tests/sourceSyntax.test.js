import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { createRequire } from 'node:module';
import { describe, expect, it } from 'vitest';

const require = createRequire(import.meta.url);
const babel = require('@babel/core');
const ROOT = join(import.meta.dirname, '..');

const sources = (dir) =>
  readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === 'node_modules' ? [] : sources(path);
    return /\.(jsx?|mjs)$/.test(name) ? [path] : [];
  });

describe('source syntax', () => {
  it('parses every file the bundler ships, including ones the tests mock away', () => {
    const files = [...sources(join(ROOT, 'src')), ...sources(join(ROOT, 'app')), ...sources(join(ROOT, '..', 'common'))];
    const broken = files.flatMap((file) => {
      try {
        babel.parseSync(readFileSync(file, 'utf8'), { filename: file, babelrc: false, configFile: false, parserOpts: { plugins: ['jsx'], sourceType: 'module' } });
        return [];
      } catch (error) {
        return [`${file}: ${String(error.message).split('\n')[0]}`];
      }
    });
    expect(files.length).toBeGreaterThan(100);
    expect(broken).toEqual([]);
  });
});

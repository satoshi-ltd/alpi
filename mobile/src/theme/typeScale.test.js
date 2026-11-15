import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { fontSizes } from './tokens';

const ROOT = join(import.meta.dirname, '../..');
const THEME = 'src/theme';

function sourceFiles(dir) {
  return readdirSync(join(ROOT, dir), { withFileTypes: true }).flatMap((entry) => {
    const rel = `${dir}/${entry.name}`;
    if (entry.isDirectory()) return sourceFiles(rel);
    return /\.jsx?$/.test(entry.name) && !entry.name.includes('.test.') ? [rel] : [];
  });
}

const FILES = [...sourceFiles('src'), ...sourceFiles('app')].filter((path) => !path.startsWith(THEME));

function hits(pattern) {
  return FILES.flatMap((path) => {
    const lines = readFileSync(join(ROOT, path), 'utf8').split('\n');
    return lines.flatMap((line, i) => (pattern.test(line) ? [`${path}:${i + 1} ${line.trim()}`] : []));
  });
}

describe('type scale reach', () => {
  it('has no raw pixel font size anywhere outside the tokens', () => {
    expect(hits(/[a-zA-Z]*[Ff]ontSize:\s*[0-9]/)).toEqual([]);
  });

  it('reads every size through useTheme, so the user text-size setting reaches it', () => {
    expect(hits(/import\s*\{[^}]*\bfontSizes\b[^}]*\}\s*from\s*'[^']*theme\/tokens'/)).toEqual([]);
  });

  it('reaches only the ladder: every alias sits on one of the six rungs, none under 12', () => {
    for (const [name, size] of Object.entries(fontSizes)) {
      expect([12, 14, 15, 16, 20, 28], name).toContain(size);
    }
  });

  it('names every step of the scale in ascending order', () => {
    const sizes = Object.values(fontSizes);
    expect(sizes).toEqual([...sizes].sort((a, b) => a - b));
  });
});

describe('one ladder on both clients', () => {
  it('maps the old names onto the six rungs: meta, small, ui, read, title, display', () => {
    expect([fontSizes.xs, fontSizes.sm, fontSizes.md, fontSizes.lg, fontSizes.xl, fontSizes.display]).toEqual([12, 14, 15, 16, 20, 28]);
    expect(fontSizes.base).toBe(fontSizes.md);
    expect(fontSizes.chat).toBe(fontSizes.lg);
  });

  it('gives base no call site: mobile body text is md', () => {
    expect(hits(/fontSizes(\.base\b|\['base'\]|\["base"\])/)).toEqual([]);
  });
});

const LITERAL_TRACKING_LEFT = [];

describe('eyebrows', () => {
  it('uppercases nothing: section labels are sentence case', () => {
    expect(hits(/textTransform:\s*'uppercase'|\.toUpperCase\(\)\s*\}/)).toEqual([]);
  });

  it('sets Geist Mono only through the code helper, at 0.92 of its role', () => {
    expect(hits(/fonts\.mono/).filter((hit) => !hit.startsWith('src/theme/'))).toEqual([]);
  });

  it('derives every tracking value from a token instead of a literal em guess', () => {
    const literals = hits(/letterSpacing:\s*-?[0-9]+(\.[0-9]+)?\s*\*/)
      .filter((hit) => !LITERAL_TRACKING_LEFT.some((path) => hit.startsWith(path)));
    expect(literals).toEqual([]);
  });
});

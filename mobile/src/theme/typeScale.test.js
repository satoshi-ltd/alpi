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

  it('names every step of the scale in ascending order', () => {
    const sizes = Object.values(fontSizes);
    expect(sizes).toEqual([...sizes].sort((a, b) => a - b));
  });
});

describe('the touch shift off desktop body size', () => {
  it('keeps base in the scale so a desktop --fs-base still ports by name', () => {
    expect(fontSizes.base).toBe(13);
  });

  it('gives base no call site: mobile body text is md, its row titles lg', () => {
    expect(hits(/fontSizes(\.base\b|\['base'\]|\["base"\])/)).toEqual([]);
  });

  it('lands the shifted body tier one or two steps over desktop 13', () => {
    expect(fontSizes.md).toBe(14);
    expect(fontSizes.lg).toBe(15);
  });
});

// Owned by the modal pass — drop this list once TypedConfirm reads tracking
const LITERAL_TRACKING_LEFT = ['src/components/TypedConfirm.jsx'];

describe('eyebrows', () => {
  it('leaves no hand-rolled eyebrow — every uppercase label goes through the primitive', () => {
    const outsideThePrimitive = hits(/textTransform:\s*'uppercase'/)
      .filter((hit) => !hit.startsWith('src/components/Eyebrow.jsx'));
    expect(outsideThePrimitive).toEqual([]);
  });

  it('derives every tracking value from a token instead of a literal em guess', () => {
    const literals = hits(/letterSpacing:\s*-?[0-9]+(\.[0-9]+)?\s*\*/)
      .filter((hit) => !LITERAL_TRACKING_LEFT.some((path) => hit.startsWith(path)));
    expect(literals).toEqual([]);
  });
});

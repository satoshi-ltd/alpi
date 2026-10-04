import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = join(import.meta.dirname, '..');

function sources(dir) {
  return readdirSync(dir).flatMap((name) => {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) return name === 'node_modules' ? [] : sources(path);
    return /\.jsx$/.test(name) && !/\.test\.jsx$/.test(name) ? [path] : [];
  });
}

export function componentsOutOfScope(source) {
  const code = source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/^\s*\/\/.*$/gm, '');
  const used = new Set([...code.matchAll(/<([A-Z][A-Za-z0-9_]*)[\s/>.]/g)].map((m) => m[1]));
  const declared = new Set([
    ...[...code.matchAll(/import\s+([\s\S]*?)\s+from\s/g)].flatMap((m) => m[1].match(/[A-Za-z_$][\w$]*/g) ?? []),
    ...[...code.matchAll(/(?:function|class|const|let|var)\s+([A-Z][\w$]*)/g)].map((m) => m[1]),
    ...[...code.matchAll(/[{,(]\s*([A-Z][\w$]*)\s*[,}=:)]/g)].map((m) => m[1]),
    ...[...code.matchAll(/:\s*([A-Z][\w$]*)\s*[=,}]/g)].map((m) => m[1]),
  ]);
  return [...used].filter((name) => !declared.has(name)).sort();
}

describe('every component a screen renders is in scope', () => {
  it('catches a component rendered without its import', () => {
    expect(componentsOutOfScope("import { Text } from 'react-native';\nconst A = () => <><Text /><Fold fold=\"x\" /></>;")).toEqual(['Fold']);
  });

  it.each(['src'])('holds for %s', (dir) => {
    const missing = sources(join(ROOT, dir)).flatMap((path) =>
      componentsOutOfScope(readFileSync(path, 'utf8')).map((name) => `${relative(ROOT, path)}: ${name}`),
    );
    expect(missing).toEqual([]);
  });
});

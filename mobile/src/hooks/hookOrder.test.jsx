import { useCallback, useEffect, useMemo, useState } from 'react';
import { readdirSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

afterEach(cleanup);

let consoleError;
beforeEach(() => {
  consoleError = vi.spyOn(console, 'error').mockImplementation(() => {});
});
afterEach(() => {
  consoleError.mockRestore();
});

function useScreenState(loading, found) {
  const [seed] = useState(1);
  useEffect(() => {}, []);
  const doubled = useMemo(() => seed * 2, [seed]);
  return { doubled, ready: !loading && found };
}

function Broken({ loading, found }) {
  const { doubled, ready } = useScreenState(loading, found);
  if (loading) return <span>loading</span>;
  if (!found) return <span>missing</span>;
  const accentFor = useCallback(() => doubled, [doubled]);
  return <span>{ready ? accentFor() : ''}</span>;
}

function Fixed({ loading, found }) {
  const { doubled, ready } = useScreenState(loading, found);
  const accentFor = useCallback(() => doubled, [doubled]);
  if (loading) return <span>loading</span>;
  if (!found) return <span>missing</span>;
  return <span>{ready ? accentFor() : ''}</span>;
}

const LOADING_TO_LOADED = ['resolves after loading', { loading: true, found: false }, { loading: false, found: true }];
const MISSING_TO_FOUND = ['resolves after a cache miss', { loading: false, found: false }, { loading: false, found: true }];

describe('hook order across an early return', () => {
  for (const [label, first, second] of [LOADING_TO_LOADED, MISSING_TO_FOUND]) {
    it(`throws when a hook sits below the early return and the screen ${label}`, () => {
      const { rerender } = render(<Broken {...first} />);
      expect(() => rerender(<Broken {...second} />)).toThrow(/more hooks than during the previous render/);
    });

    it(`survives when every hook sits above the early return and the screen ${label}`, () => {
      const { rerender } = render(<Fixed {...first} />);
      expect(() => rerender(<Fixed {...second} />)).not.toThrow();
      expect(consoleError).not.toHaveBeenCalled();
    });
  }
});

const APP_DIR = join(import.meta.dirname, '../../app');

function screenFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((e) => {
    const path = join(dir, e.name);
    if (e.isDirectory()) return screenFiles(path);
    return e.name.endsWith('.jsx') ? [path] : [];
  });
}

function bodyLines(source, signature) {
  const lines = source.slice(source.indexOf(signature)).split('\n');
  const end = lines.findIndex((line, i) => i > 0 && line === '}');
  return end < 0 ? lines : lines.slice(0, end);
}

function firstEarlyReturn(lines) {
  for (let i = 0; i < lines.length; i++) {
    if (!/^ {2}if \(/.test(lines[i])) continue;
    for (let j = i + 1; j < lines.length && !/^ {2}\}/.test(lines[j]); j++) {
      if (/^ {4}return\b/.test(lines[j])) return i;
    }
  }
  return -1;
}

function lastBodyHook(lines) {
  let at = -1;
  for (let i = 0; i < lines.length; i++) {
    if (/^ {2}(?:const |let |var )?[^/]*?\buse[A-Z]\w*\(/.test(lines[i])) at = i;
  }
  return at;
}

describe('every screen calls its hooks above its first early return', () => {
  const suspects = screenFiles(APP_DIR).flatMap((path) => {
    const source = readFileSync(path, 'utf8');
    return [...source.matchAll(/^(?:export default )?function (\w+)\([^)]*\) \{$/gm)].flatMap(([signature, name]) => {
      const lines = bodyLines(source, signature);
      const earlyReturn = firstEarlyReturn(lines);
      const lastHook = lastBodyHook(lines);
      if (earlyReturn < 0 || lastHook < 0) return [];
      return [{ label: `${path.slice(APP_DIR.length + 1)} :: ${name}`, earlyReturn, lastHook }];
    });
  });

  it('finds the screens that mix hooks with early returns', () => {
    expect(suspects.length).toBeGreaterThan(5);
  });

  for (const { label, earlyReturn, lastHook } of suspects) {
    it(label, () => {
      expect(lastHook).toBeLessThan(earlyReturn);
    });
  }
});

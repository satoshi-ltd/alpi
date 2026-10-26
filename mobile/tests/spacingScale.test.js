import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';
import { spaceScale } from '../src/theme/tokens';

const ROOT = join(import.meta.dirname, '..');
const ALLOWED = new Set([0, 1, 2, 3, ...Object.values(spaceScale)]);
const AVATAR_INDENTS = new Set(['src/features/inbox/InboxSkeleton.jsx:64', 'app/wg/[id]/member.jsx:52']);

function walk(dir, out = []) {
  for (const name of readdirSync(dir)) {
    const path = join(dir, name);
    if (statSync(path).isDirectory()) walk(path, out);
    else if (/\.jsx?$/.test(name) && !/\.test\./.test(name)) out.push(path);
  }
  return out;
}

describe('spacing literals', () => {
  it('keeps every padding, margin and gap literal on the scale', () => {
    const offenders = [];
    for (const dir of ['src', 'app']) {
      for (const file of walk(join(ROOT, dir))) {
        const rel = file.slice(ROOT.length + 1);
        for (const m of readFileSync(file, 'utf8').matchAll(/\b(?:padding|margin|gap)[A-Za-z]*:\s*(\d+(?:\.\d+)?)\b(?!\s*[+*-])/g)) {
          const value = Number(m[1]);
          if (!ALLOWED.has(value) && !AVATAR_INDENTS.has(`${rel}:${value}`)) offenders.push(`${rel}:${value}`);
        }
      }
    }
    expect(offenders).toEqual([]);
  });
});

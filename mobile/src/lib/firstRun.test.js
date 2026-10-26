import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { FIRST_RUN_MAX_W, firstRun, firstRunColumn } from './firstRun';

const ROOT = join(import.meta.dirname, '..', '..');
const source = (path) => readFileSync(join(ROOT, path), 'utf8');

describe('first run grid', () => {
  it('uses 24 for heroes, 16 for body screens, one 14 pt card padding and 24 pt gaps', () => {
    expect(firstRun).toEqual({ hero: 24, body: 16, card: 14, gap: 24 });
  });

  it('centres the welcome column at 480 pt at most', () => {
    expect(FIRST_RUN_MAX_W).toBe(480);
    expect(firstRunColumn).toMatchObject({ maxWidth: 480, width: '100%', alignSelf: 'center' });
  });

  it.each(['app/onboarding.jsx', 'app/paired.jsx'])('%s pads its hero by the grid and caps its column', (path) => {
    const text = source(path);
    expect(text).toMatch(/padding: firstRun\.hero/);
    expect(text).toMatch(/style=\{firstRunColumn\}/);
    expect(text).not.toMatch(/padding: space\.s9/);
  });

  it('keeps the help card and the pair status card on one padding and the pair body on the 16 gutter', () => {
    expect(source('app/onboarding.jsx')).toMatch(/padding: firstRun\.card/);
    const pair = source('app/pair.jsx');
    expect(pair).toMatch(/padding: firstRun\.card/);
    expect(pair).toMatch(/padding: firstRun\.body, gap: firstRun\.gap/);
  });
});

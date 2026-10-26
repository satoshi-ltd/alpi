import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { space } from '../theme/tokens';

const ROOT = join(import.meta.dirname, '..', '..');
const source = (path) => readFileSync(join(ROOT, path), 'utf8');

describe('biometric unlock row', () => {
  const text = source('app/biometric.jsx');
  const KNOB = Number(/width: (\d+), height: \1, borderRadius: radii\.pill, backgroundColor: colors\.bgPane/.exec(text)[1]);

  it('insets its text like every other settings row', () => {
    expect(space.s7).toBe(16);
    expect(text).toMatch(/paddingHorizontal: space\.s7,\s+paddingVertical: space\.s6,\s+flexDirection: 'row'/);
  });

  it('sizes the track to the knob plus an even inset on all four sides', () => {
    const track = /width: 44,\s+height: (\d+),/.exec(text);
    const inset = /padding: space\.s1,/.test(text) ? space.s1 : NaN;
    expect(Number(track[1])).toBe(KNOB + 2 * inset);
  });
});

import { describe, expect, it } from 'vitest';
import { palettes } from '../theme/tokens';
import { wellStyle } from './well';

describe('a field is a well', () => {
  it.each(['light', 'dark'])('rests on the %s elevated surface with a hairline edge and the 4 pt sheet corner', (mode) => {
    const colors = palettes[mode];
    expect(wellStyle(colors)).toEqual({ backgroundColor: colors.bgElev, borderRadius: 4, borderWidth: 1, borderColor: colors.line2 });
  });

  it.each(['light', 'dark'])('keeps its fill and only sharpens the edge when focused in %s, never an underline', (mode) => {
    const colors = palettes[mode];
    const focused = wellStyle(colors, { focused: true });
    expect(focused.backgroundColor).toBe(colors.bgElev);
    expect(focused.borderColor).toBe(colors.edge);
    expect(focused.borderWidth).toBe(1);
    expect(Object.keys(focused).some((key) => key.startsWith('borderBottom'))).toBe(false);
  });

  it.each(['light', 'dark'])('turns grey with no edge only when disabled in %s', (mode) => {
    const colors = palettes[mode];
    expect(wellStyle(colors, { disabled: true, focused: true })).toMatchObject({ backgroundColor: colors.field, borderColor: 'transparent', borderWidth: 1 });
  });

  it('rings an invalid field in the danger text colour', () => {
    expect(wellStyle(palettes.light, { error: true }).borderColor).toBe(palettes.light.dangerText);
  });
});

describe('chips on a well', () => {
  it('keeps the composer model chip off the well tone so it still reads as a chip', async () => {
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    const source = readFileSync(join(import.meta.dirname, '../features/chat/Composer.jsx'), 'utf8');
    expect(source).toMatch(/backgroundColor: pressed \? colors\.line2 : colors\.selected/);
  });
});

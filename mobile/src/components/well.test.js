import { describe, expect, it } from 'vitest';
import { mixHex } from '../../../common/color.mjs';
import { palettes } from '../theme/tokens';
import { wellStyle } from './well';

describe('a field is a well', () => {
  it.each(['light', 'dark'])('sits borderless in the %s input tone with the 4 pt sheet corner', (mode) => {
    const colors = palettes[mode];
    expect(wellStyle(colors)).toEqual({ backgroundColor: colors.bgInput, borderRadius: 4, borderWidth: 1, borderColor: 'transparent' });
  });

  it.each(['light', 'dark'])('deepens one tone and rings at ink 30 %% when focused in %s, never an underline', (mode) => {
    const colors = palettes[mode];
    const focused = wellStyle(colors, { focused: true });
    expect(focused.backgroundColor).toBe(mixHex(colors.bgInput, 0.9, colors.ink));
    expect(focused.borderColor).toBe(`${colors.ink}4d`);
    expect(Object.keys(focused).some((key) => key.startsWith('borderBottom'))).toBe(false);
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

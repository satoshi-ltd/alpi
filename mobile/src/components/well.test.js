import { describe, expect, it } from 'vitest';
import { alpha, palettes } from '../theme/tokens';
import { wellStates } from '../../../common/well.mjs';
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

  it.each(['light', 'dark'])('turns grey with no edge and fades by the shared alpha when disabled in %s, as desktop does', (mode) => {
    const colors = palettes[mode];
    expect(wellStyle(colors, { disabled: true, focused: true, error: true })).toEqual({ backgroundColor: colors.field, borderRadius: 4, borderWidth: 1, borderColor: 'transparent', opacity: alpha.disabled });
  });

  it.each(['light', 'dark'])('rings an invalid field in the danger fill in %s, as desktop does', (mode) => {
    expect(wellStyle(palettes[mode], { error: true }).borderColor).toBe(palettes[mode][wellStates.error.ring]);
    expect(wellStates.error.ring).toBe('danger');
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

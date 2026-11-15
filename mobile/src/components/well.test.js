import { describe, expect, it } from 'vitest';
import { alpha, fieldFocus, focusRing, palettes, radii } from '../theme/tokens';
import { wellStates } from '../../../common/well.mjs';
import { recess, ringColor, wellStyle } from './well';

const blend = (hex8, ground) => {
  const a = parseInt(hex8.slice(7, 9), 16) / 255;
  return `#${[1, 3, 5].map((i) => Math.round(parseInt(hex8.slice(i, i + 2), 16) * a + parseInt(ground.slice(i, i + 2), 16) * (1 - a)).toString(16).padStart(2, '0')).join('')}`;
};
const lum = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4)).reduce((s, c, i) => s + c * [0.2126, 0.7152, 0.0722][i], 0);
const ratio = (a, b) => { const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x); return (hi + 0.05) / (lo + 0.05); };

describe('a field is a well', () => {
  it.each(['light', 'dark'])('rests on the %s fill with no edge at the 12 pt control corner', (mode) => {
    const colors = palettes[mode];
    expect(wellStyle(colors)).toEqual({ backgroundColor: colors.fill, borderRadius: 12, borderWidth: fieldFocus.width, borderColor: 'transparent' });
    expect(radii.control).toBe(12);
  });

  it.each(['light', 'dark'])('shows focus in %s as a 1.5 pt inset ink3 line, never the ring or an underline', (mode) => {
    const colors = palettes[mode];
    const focused = wellStyle(colors, { focused: true });
    expect(focused.backgroundColor).toBe(colors.fill);
    expect(focused.borderColor).toBe(colors.ink3);
    expect(focused.borderWidth).toBe(1.5);
    expect(Object.keys(focused).some((key) => key.startsWith('borderBottom') || key.startsWith('outline'))).toBe(false);
    expect(ratio(colors.ink3, colors.fill)).toBeGreaterThanOrEqual(3);
  });

  it.each(['light', 'dark'])('draws the %s keyboard ring of a pressable as ink at 60 %%, 3:1 or more on the pane, the fill and a float', (mode) => {
    const colors = palettes[mode];
    expect(ringColor(colors)).toBe(`${colors.ink}99`);
    for (const ground of [colors.bgPane, colors.fill, colors.raised, colors.bgSide]) {
      expect(ratio(blend(ringColor(colors), ground), ground)).toBeGreaterThanOrEqual(3);
    }
    expect(focusRing.width).toBe(2);
  });

  it.each(['light', 'dark'])('stays on the fill with no edge and fades by the shared 0.45 when disabled in %s', (mode) => {
    const colors = palettes[mode];
    expect(wellStyle(colors, { disabled: true, focused: true, error: true })).toEqual({ backgroundColor: colors.fill, borderRadius: radii.control, borderWidth: fieldFocus.width, borderColor: 'transparent', opacity: 0.45 });
    expect(alpha.disabled).toBe(0.45);
  });

  it.each(['light', 'dark'])('rings an invalid field in the danger text colour in %s, as desktop does', (mode) => {
    expect(wellStyle(palettes[mode], { error: true }).borderColor).toBe(palettes[mode][wellStates.error.ring]);
    expect(wellStates.error.ring).toBe('dangerText');
  });

  it('recesses a well inside a float to the pane in dark and keeps the field in light', () => {
    expect(wellStyle(palettes.dark, { float: true }).backgroundColor).toBe(palettes.dark.bgPane);
    expect(wellStyle(palettes.light, { float: true }).backgroundColor).toBe(palettes.light.fill);
    expect(ratio(palettes.dark.bgPane, palettes.dark.bgElev)).toBeGreaterThanOrEqual(1.1);
    expect(ratio(palettes.dark.ink3, palettes.dark.bgPane)).toBeGreaterThanOrEqual(4.5);
  });
});

describe('wells and field blocks inside a float', () => {
  it.each([
    ['components/ConfirmDialog.jsx', /useWell\(colors, false, false, true\)[\s\S]*backgroundColor: recess\(colors\)|backgroundColor: recess\(colors\)[\s\S]*useWell\(colors, false, false, true\)/],
    ['components/TextPrompt.jsx', /useWell\(colors, false, false, true\)/],
    ['features/clarification/ClarificationSheet.jsx', /useWell\(colors, false, false, true\)/],
    ['features/approval/ApprovalSheet.jsx', /backgroundColor: recess\(colors\)/],
    ['features/connections/PairingSheet.jsx', /backgroundColor: recess\(colors\)/],
    ['features/chat/ToolDetailSheet.jsx', /backgroundColor: recess\(colors\)/],
  ])('%s recesses under the float instead of sitting on field', async (file, pattern) => {
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    const source = readFileSync(join(import.meta.dirname, '..', file), 'utf8');
    expect(source).toMatch(pattern);
    expect(source).not.toMatch(/backgroundColor: colors\.field,\s*\n\s*border(Width|Radius)/);
  });
});

describe('the composer is not a well', () => {
  it('draws one fill pill with no focus edge, the caret being its focus', async () => {
    const { readFileSync } = await import('node:fs');
    const { join } = await import('node:path');
    const source = readFileSync(join(import.meta.dirname, '../features/chat/Composer.jsx'), 'utf8');
    expect(source).not.toMatch(/wellStyle|useWell/);
    expect(source).toMatch(/borderRadius: radii\.sheet,\s*backgroundColor: colors\.fill/);
  });
});

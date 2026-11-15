import { describe, expect, it } from 'vitest';

import { ACCENTS } from '../../../common/accents.mjs';
import { MARK_EYE_FLOOR, MARK_STEP, markTone, markTones } from '../../../common/markTone.mjs';
import { contrastRatio, nameTone } from '../../../common/name.mjs';
import { shiftLightness } from '../../../common/shapes.mjs';
import { palettes } from '../../../common/tokens.mjs';

const LIGHT = {
  amber: '#c08915', orange: '#dd7a28', vermilion: '#f05940', rose: '#ec6a88', magenta: '#df4b9d', violet: '#9b5ad9',
  indigo: '#6572e4', blue: '#3899e2', sky: '#10a1c7', teal: '#20a2a4', green: '#2aa961', lime: '#799f08',
};

describe('mark tone', () => {
  it.each(ACCENTS)("draws %s's body so the theme's eyes hold 3:1, deeper in light only", (name, accent) => {
    const light = markTone(accent, 'light');
    expect(light).toBe(LIGHT[name]);
    expect(markTone(accent, 'dark')).toBe(accent);
    expect(contrastRatio(light, palettes.light.markEye)).toBeGreaterThanOrEqual(MARK_EYE_FLOOR);
    expect(contrastRatio(accent, palettes.dark.markEye)).toBeGreaterThanOrEqual(MARK_EYE_FLOOR);
    expect(contrastRatio(light, palettes.light.bgPane)).toBeGreaterThanOrEqual(MARK_EYE_FLOOR);
    expect(contrastRatio(nameTone(accent, palettes.light.bgPane), palettes.light.bgPane)).toBeGreaterThanOrEqual(4.5);
    if (light === accent) {
      expect(contrastRatio(accent, palettes.light.markEye)).toBeGreaterThanOrEqual(MARK_EYE_FLOOR);
      expect(markTones(accent)).toBeNull();
    } else {
      const steps = Array.from({ length: 100 }, (_, i) => Number(((i + 1) * MARK_STEP).toFixed(2)));
      const step = steps.find((d) => shiftLightness(accent, -d) === light);
      const before = step === MARK_STEP ? accent : shiftLightness(accent, -Number((step - MARK_STEP).toFixed(2)));
      expect(contrastRatio(before, palettes.light.markEye)).toBeLessThan(MARK_EYE_FLOOR);
      expect(markTones(accent)).toEqual({ light, dark: accent });
    }
  });

  it('leaves anything that is not a six-digit hex as it is', () => {
    for (const value of [undefined, null, '', 'var(--accent)', '#abc', 'red']) {
      expect(markTone(value, 'light')).toBe(value);
      expect(markTones(value)).toBeNull();
    }
    expect(markTone('#F0B447', 'light')).toBe('#c08915');
    expect(markTone('#f0b447')).toBe('#f0b447');
  });
});

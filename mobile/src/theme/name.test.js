import { describe, expect, it } from 'vitest';

import { NAME_MAX_FONT_SCALE, NAME_MIN_FIT, NAME_TEXT, nameColor, nameSize, nameStyle } from './name';

describe('name type', () => {
  it('folds the system text size into the name itself, capped, so the tracking scales with it on iOS too', () => {
    expect(NAME_TEXT.allowFontScaling).toBe(false);
    expect(nameSize(28, 1.5)).toBe(42);
    expect(nameSize(28, 3)).toBe(28 * NAME_MAX_FONT_SCALE);
    expect(nameSize(28, undefined)).toBe(28);
    expect(nameStyle(56, '#000').letterSpacing).toBeCloseTo(-0.04 * 56);
  });

  it('shrinks a long name to fit down to 24 of 28 before it truncates, on one line, as a header', () => {
    expect(NAME_TEXT).toMatchObject({ adjustsFontSizeToFit: true, minimumFontScale: NAME_MIN_FIT, numberOfLines: 1, accessibilityRole: 'header' });
    expect(NAME_MIN_FIT).toBeCloseTo(24 / 28);
  });

  it('falls back to ink for a missing accent', () => {
    expect(nameColor(null, { bg: '#ffffff', ink: '#141414' })).toBe('#141414');
  });
});

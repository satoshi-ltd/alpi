import { describe, expect, it } from 'vitest';

import * as shared from '../../../common/tokens.mjs';
import {
  controlHeight,
  countBadge,
  dotScale,
  eyebrow,
  focusRing,
  fontSizes,
  fontWeights,
  iconStrokeFor,
  iconStrokeRendered,
  ladderDirection,
  motion,
  palettes,
  pulseDuration,
  radii,
  spaceScale,
  tracking,
  typeLadder,
} from './tokens';

const channels = (hex) => [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
const luminance = (hex) => {
  const [r, g, b] = channels(hex).map((c) => (c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4));
  return 0.2126 * r + 0.7152 * g + 0.0722 * b;
};
const contrast = (a, b) => {
  const [hi, lo] = [luminance(a), luminance(b)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
};

describe('scales on the phone', () => {
  it('declares the 4/8/12/16/24/32 spacing scale and the 24/28/32/40 control heights', () => {
    expect(Object.values(spaceScale)).toEqual([4, 8, 12, 16, 24, 32]);
    expect(Object.values(controlHeight)).toEqual([24, 28, 32, 40]);
  });

  it('declares the type ladder 11/13/15/18/22/28, weights 400/500/600 and one 0.08 eyebrow', () => {
    expect(Object.values(typeLadder)).toEqual([11, 13, 15, 18, 22, 28]);
    expect(Object.values(fontWeights)).toEqual([400, 500, 600]);
    expect(eyebrow).toEqual({ size: 11, tracking: 0.08, family: 'mono', ink: 'ink3' });
    expect(tracking.eyebrow).toBe(0.08);
    for (const size of Object.values(typeLadder)) expect(Object.values(fontSizes)).toContain(size);
  });

  it('keeps dots on a 6/8 ladder and the count badge on radii.xs', () => {
    expect(dotScale).toEqual({ sm: 6, md: 8 });
    expect(countBadge.size).toBe(18);
    expect(countBadge.radius).toBe(radii.xs);
  });
});

describe('motion on the phone', () => {
  it('exports enter 180, exit 130, one easing pair and one pulse from the shared record', () => {
    expect(motion.enter).toBe(180);
    expect(motion.exit).toBe(130);
    expect(motion.easeEnter).toEqual([0.2, 0.7, 0.2, 1]);
    expect(motion.easeExit).toEqual([0.8, 0, 0.8, 0.3]);
    expect(motion.pulse).toBe(1600);
    expect(pulseDuration).toBe(motion.pulse);
    expect(motion.pulseLow).toBe(0.4);
    expect(motion.exit).toBeLessThan(motion.enter);
    expect(motion.duration.base).toBe(shared.motionTokens.enter);
  });
});

describe('icons on the phone', () => {
  it('renders every allowed size at no less than 1.33 pt', () => {
    expect(iconStrokeRendered).toBe(1.33);
    for (const size of shared.iconSizesAllowed.mobile) {
      expect((iconStrokeFor(size) * size) / 24).toBeGreaterThanOrEqual(1.33 - 1e-9);
    }
    expect(iconStrokeFor(24)).toBeCloseTo(1.33, 5);
  });
});

describe('surface ladder on the phone', () => {
  it('lifts card over the ground at 1.10:1 and the field inside it at 1.07:1 in light', () => {
    expect(Number(contrast(palettes.light.card, palettes.light.bg).toFixed(2))).toBeGreaterThanOrEqual(1.1);
    expect(Number(contrast(palettes.light.field, palettes.light.card).toFixed(2))).toBeGreaterThanOrEqual(1.07);
  });

  it('keeps the dark ladder ascending with elev at #202020', () => {
    expect(palettes.dark.bgElev).toBe('#202020');
    expect(luminance(palettes.dark.card)).toBeGreaterThan(luminance(palettes.dark.bg));
    expect(luminance(palettes.dark.field)).toBeGreaterThan(luminance(palettes.dark.card));
    expect(luminance(palettes.dark.bgElev)).toBeGreaterThan(luminance(palettes.dark.card));
  });

  it('writes the direction per mode and the palettes obey it', () => {
    expect(ladderDirection).toEqual({ light: 'descends', dark: 'ascends' });
    expect(luminance(palettes.light.card)).toBeLessThan(luminance(palettes.light.bg));
    expect(luminance(palettes.dark.card)).toBeGreaterThan(luminance(palettes.dark.bg));
  });

  it('declares the focus ring as 2 pt at 60% with a 2 pt offset', () => {
    expect(focusRing).toEqual({ width: 2, offset: 2, alpha: 0.6 });
  });
});

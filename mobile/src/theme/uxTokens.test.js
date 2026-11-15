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
  nestInset,
  motion,
  palettes,
  pulseDuration,
  radii,
  spaceScale,
  stateFill,
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
  it('declares the one 4 pt grid and the 32/40/48 control heights', () => {
    expect(Object.values(spaceScale)).toEqual([4, 8, 12, 16, 24, 32, 48]);
    expect(Object.values(controlHeight)).toEqual([32, 40, 48]);
    expect(shared.controlRole).toEqual({ compact: 32, control: 40, touch: 48 });
    expect(shared.touchTarget).toEqual({ min: 44, control: 48 });
  });

  it('declares the six-size ladder 12/14/15/16/20/28, weights 400/500/600 and the sentence-case section label', () => {
    expect(Object.values(typeLadder)).toEqual([12, 14, 15, 16, 20, 28]);
    expect(Object.values(fontWeights)).toEqual([400, 500, 600]);
    expect(eyebrow).toEqual({ size: 14, tracking: 0, family: 'sans', weight: 500, ink: 'ink3', case: 'sentence' });
    expect(tracking.eyebrow).toBe(0);
    for (const size of Object.values(typeLadder)) expect(Object.values(fontSizes)).toContain(size);
  });

  it('keeps dots on a 6/8 ladder and the count badge round, on radii.pill', () => {
    expect(dotScale).toEqual({ sm: 6, md: 8 });
    expect(countBadge.size).toBe(18);
    expect(countBadge.radius).toBe(radii.pill);
  });

  it('declares the five radii by role and nothing else', () => {
    expect(radii).toEqual({ xs: 6, control: 12, surface: 20, sheet: 28, pill: 999 });
    expect(Object.keys(shared.radiusRole)).toEqual(Object.keys(radii));
  });

  it('nests an 8 pt inset child at its parent radius minus the inset', () => {
    expect(nestInset).toBe(8);
    expect(radii.surface - nestInset).toBe(radii.control);
  });

  it('steps hover under selected under pressed, one point darker in dark', () => {
    expect(stateFill).toEqual({ hover: 0.04, selected: 0.08, pressed: 0.12 });
    expect(shared.stateFills.dark).toEqual({ hover: 0.05, selected: 0.09, pressed: 0.13 });
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
  it('draws 16, 20 and 24 at a rendered 1.5 pt stroke', () => {
    expect(iconStrokeRendered).toBe(1.5);
    expect(shared.iconSizesAllowed.mobile).toEqual([16, 20, 24]);
    for (const size of shared.iconSizesAllowed.mobile) {
      expect((iconStrokeFor(size) * size) / 24).toBeCloseTo(1.5, 9);
    }
  });
});

describe('surface ladder on the phone', () => {
  it('draws one fill under bubbles, fields, chips and groups, a step off the pane in both modes', () => {
    for (const mode of ['light', 'dark']) {
      const p = palettes[mode];
      expect(p.card).toBe(p.fill);
      expect(p.field).toBe(p.fill);
      expect(p.bgInput).toBe(p.fill);
      expect(contrast(p.fill, p.bgPane)).toBeGreaterThan(1.08);
    }
  });

  it('raises dark floats to #2c2c2c over the #262626 fill and keeps light raised white', () => {
    expect(palettes.dark.bgElev).toBe('#2c2c2c');
    expect(palettes.light.bgElev).toBe('#ffffff');
    expect(luminance(palettes.dark.raised)).toBeGreaterThan(luminance(palettes.dark.fill));
  });

  it('writes the direction per mode and the palettes obey it', () => {
    expect(ladderDirection).toEqual({ light: 'descends', dark: 'ascends' });
    expect(luminance(palettes.light.fill)).toBeLessThan(luminance(palettes.light.bg));
    expect(luminance(palettes.dark.fill)).toBeGreaterThan(luminance(palettes.dark.bg));
  });

  it('declares the focus ring as 2 pt at 60% with a 2 pt offset and the field line as 1.5 pt ink3', () => {
    expect(focusRing).toEqual({ width: 2, offset: 2, alpha: 0.6 });
    expect(shared.fieldFocus).toEqual({ width: 1.5, ink: 'ink3' });
  });
});

import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { buttonHeights } from '../../../common/button.mjs';
import { ALPACA_FOLD, FOLD_SIZES, foldFacets } from '../../../common/folds.mjs';
import { TEXT_SCALES, scaleFontSizes } from '../theme/textScale';
import { fonts, lineHeights, mobile, palettes, space } from '../theme/tokens';
import {
  BUSY_MARK_PX,
  FIRST_RUN_MAX_W,
  busyMarkStyle,
  firstRun,
  firstRunActions,
  firstRunBottom,
  firstRunColumn,
  firstRunEdge,
  firstRunScroll,
  firstRunType,
  foldMarkStyle,
  markInset,
} from './firstRun';
import { MASTER_DETAIL_MIN_W } from './panes';

const ROOT = join(import.meta.dirname, '..', '..');
const source = (path) => readFileSync(join(ROOT, path), 'utf8');
const SANS_EM = 0.58;
const MONO_EM = 0.62;
const PHONES = [320, 360, 390, 430];
const FOLD = { width: 852, height: 884 };
const INSETS = { top: 47, bottom: 34, left: 0, right: 0 };
const SCREENS = ['app/onboarding.jsx', 'app/pair.jsx', 'app/paired.jsx'];

describe('first run grid', () => {
  it('keeps the 480 column, the 16 pt phone edge, the 24 pt fold edge and the 24 / 16 / 8 rhythm on tokens', () => {
    expect(FIRST_RUN_MAX_W).toBe(480);
    expect(firstRun).toEqual({ top: 24, gap: 24, stack: 16, tight: 8, edge: 16, foldEdge: 24 });
    expect(firstRun.foldEdge).toBe(space.s9);
    expect(firstRun.edge).toBe(space.s7);
    expect(firstRunColumn).toEqual({ width: '100%', maxWidth: 480, alignSelf: 'flex-start' });
    expect(firstRunActions).toMatchObject({ maxWidth: 480, alignSelf: 'flex-start', gap: 8 });
  });

  it('anchors the column on the left edge instead of centring it', () => {
    expect(firstRunColumn.alignSelf).not.toBe('center');
    for (const path of SCREENS) {
      const text = source(path);
      expect(text, path).not.toMatch(/textAlign: 'center'/);
      expect(text, path).not.toMatch(/alignItems: 'center'/);
      expect(text, path).toMatch(/style=\{firstRunColumn\}/);
    }
  });

  it('draws with tokens and the board sizes only: no cards, no literal padding, margin or gap', () => {
    for (const path of SCREENS) {
      const text = source(path);
      expect(text, path).not.toMatch(/firstRun\.(card|hero|body)\b/);
      expect(text, path).not.toMatch(/backgroundColor: colors\.hover/);
      expect(text, path).not.toMatch(/(?:padding|margin|gap)\w*: -?[1-9]/);
    }
    expect(source('src/lib/firstRun.js')).not.toMatch(/^\s*\/\/|\/\*/m);
  });
});

describe('first run edge', () => {
  it('is 16 on every phone and 24 on a fold', () => {
    for (const width of PHONES) expect(firstRunEdge(width, 844)).toBe(16);
    expect(firstRunEdge(FOLD.width, FOLD.height)).toBe(24);
    expect(firstRunEdge(MASTER_DETAIL_MIN_W, 600)).toBe(24);
    expect(firstRunEdge(956, 440)).toBe(16);
  });

  it('puts the ink of the Fold on the edge: the box is pulled back by 17.256 % of its size', () => {
    const left = Math.min(...foldFacets(ALPACA_FOLD).flatMap(({ points }) => points.map(([x]) => x)));
    expect(foldMarkStyle.marginLeft).toBeCloseTo(-(left * FOLD_SIZES.hero) / 100, 6);
    expect(markInset(FOLD_SIZES.hero)).toBeCloseTo(12.42, 2);
    for (const edge of [16, 24]) {
      expect(edge + foldMarkStyle.marginLeft + markInset(FOLD_SIZES.hero)).toBeCloseTo(edge, 6);
    }
  });

  it('puts the ink of Busy on the same edge and keeps the Fold box height while it waits', () => {
    expect(BUSY_MARK_PX).toBe(77);
    expect(busyMarkStyle.marginLeft).toBeCloseTo(-13.29, 2);
    expect(busyMarkStyle.marginTop).toBeCloseTo(-2.31, 2);
    expect(BUSY_MARK_PX + busyMarkStyle.marginTop + busyMarkStyle.marginBottom).toBeCloseTo(FOLD_SIZES.hero, 6);
    expect(busyMarkStyle).toMatchObject({ padding: 0, gap: 0, alignItems: 'flex-start' });
  });
});

describe('first run page arithmetic', () => {
  it('rides 24 below the safe top, with a 16 gutter, and 16 above the safe bottom', () => {
    for (const edge of [16, 24]) {
      expect(firstRunScroll(INSETS, edge)).toMatchObject({ paddingTop: 71, paddingHorizontal: edge, paddingBottom: 16 });
      expect(firstRunBottom(INSETS, edge)).toEqual({ paddingHorizontal: edge, paddingTop: 16, paddingBottom: 50 });
    }
  });

  it('drops the safe-area pad under the actions while the keyboard is up', () => {
    expect(firstRunBottom(INSETS, 16, true).paddingBottom).toBe(16);
  });

  it.each(TEXT_SCALES.map((step) => step.value))('keeps both buttons on screen at text scale %s on every phone and the fold', (scale) => {
    const sizes = scaleFontSizes(scale);
    const hero = buttonHeights.hero.mobile;
    const ghost = buttonHeights.lg.mobile;
    expect([hero, ghost]).toEqual([56, 48]);
    expect(sizes.xl + 2 * space.s2).toBeLessThanOrEqual(hero);
    expect(sizes.lg + 2 * space.s2).toBeLessThanOrEqual(ghost);
    const bottom = firstRun.stack + hero + 2 * (firstRun.tight + ghost) + firstRun.stack + INSETS.bottom;
    for (const [width, height] of [...PHONES.map((w) => [w, w === 320 ? 568 : 844]), [FOLD.width, FOLD.height]]) {
      const edge = firstRunEdge(width, height);
      const room = Math.min(FIRST_RUN_MAX_W, width - 2 * edge);
      const page = height - INSETS.top - firstRun.top - bottom;
      expect(page, `scroll viewport at ${width}x${height}`).toBeGreaterThanOrEqual(mobile.tap * 4);
      expect(bottom, `actions at ${width}`).toBeLessThan(height / 2);
      expect(room).toBeGreaterThanOrEqual(width < 480 ? 272 : FIRST_RUN_MAX_W);
      const title = Math.ceil((15 * SANS_EM * sizes.display) / room);
      expect(title, `title lines at ${width}`).toBeLessThanOrEqual(3);
      const paste = 2 * space.s6 + 'Paste from clipboard'.length * SANS_EM * sizes.md;
      expect(paste, `paste action at ${width}`).toBeLessThanOrEqual(room);
      const fact = Math.ceil(('casa · ws://100.99.29.84:49200'.length * MONO_EM * sizes.sm) / room);
      expect(fact, `host fact lines at ${width}`).toBeLessThanOrEqual(3);
    }
  });

  it('leaves the Enable button and the label room on a 320 row at the Largest step', () => {
    const sizes = scaleFontSizes(1.3);
    const enable = 2 * space.s6 + 'Enable'.length * SANS_EM * sizes.md;
    const room = 320 - 2 * space.s7;
    expect(enable).toBeLessThan(room / 2);
    expect(mobile.tap).toBe(44);
  });
});

describe('first run type', () => {
  const theme = { colors: palettes.light, fonts, fontSizes: scaleFontSizes(1) };
  const type = firstRunType(theme);

  it('sets the display title at 28 with the 24 gap under the mark, mono facts at 12 and the sentence at 14', () => {
    expect(type.title).toMatchObject({ fontSize: 28, lineHeight: 36, marginTop: 24 });
    expect(type.fact).toMatchObject({ fontFamily: fonts.mono, fontSize: 12, marginTop: 8 });
    expect(type.sentence).toMatchObject({ fontSize: 14, lineHeight: 21, marginTop: 8 });
    expect(Math.round(14 * lineHeights.normal)).toBe(21);
  });

  it('takes the title size of the roster page from the caller and scales with the text step', () => {
    expect(firstRunType(theme, 22).title).toMatchObject({ fontSize: 22, lineHeight: 29 });
    const largest = firstRunType({ ...theme, fontSizes: scaleFontSizes(1.3) });
    expect(largest.title.fontSize).toBeGreaterThan(type.title.fontSize);
    expect(largest.failureTitle.fontSize).toBeGreaterThan(type.failureTitle.fontSize);
  });

  it('shows failures in the danger text ink', () => {
    expect(type.failureTitle.color).toBe(palettes.light.dangerText);
  });
});

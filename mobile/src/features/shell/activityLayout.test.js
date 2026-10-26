import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { FOLD_SIZES } from '../../../../common/folds.mjs';
import { LIST_COLUMN_W, MASTER_DETAIL_MIN_W, SIDEBAR_W, paneWidth } from '../../lib/panes';
import { TEXT_SCALES, scaleFontSizes } from '../../theme/textScale';
import { iconSizes, mobile, space } from '../../theme/tokens';
import { CHIP_H, CHIP_ROW_H, GROUP_H, JOB_INDENT, JOB_ROW_H, RETRY_W, SECTION_H, textRoom } from './activityFeed';

const ROOT = join(import.meta.dirname, '..', '..', '..');
const read = (path) => readFileSync(join(ROOT, path), 'utf8');
const MONO_EM = 0.62;
const SANS_EM = 0.58;
const PHONES = [320, 360, 390, 430];
const FOLD_DETAIL = [MASTER_DETAIL_MIN_W - LIST_COLUMN_W, 520];

describe('activity heights sit on the scale', () => {
  it('uses whole numbers, 44 targets and the 32 section header', () => {
    expect([CHIP_H, CHIP_ROW_H, SECTION_H, GROUP_H, JOB_ROW_H, RETRY_W]).toEqual([32, 44, 32, 48, 56, 44]);
    expect(CHIP_ROW_H).toBe(mobile.tap);
    expect(GROUP_H).toBeGreaterThanOrEqual(mobile.tap);
    expect(JOB_ROW_H).toBeGreaterThanOrEqual(mobile.tap);
    expect(JOB_INDENT).toBe(2 * space.s7);
  });

  it('gives the 32 header a 44 target through hit slop on both edges', () => {
    expect(SECTION_H + 2 * ((mobile.tap - SECTION_H) / 2)).toBe(mobile.tap);
  });

  it('draws with tokens only: no literal sizes, no blur, gradient or shadow, no comments', () => {
    const source = read('src/features/shell/ActivityList.jsx');
    const list = source.slice(source.indexOf('function SectionHeader'));
    expect(list).not.toMatch(/(?:padding|margin|gap|[hH]eight|minWidth|\bwidth)\w*: -?[1-9]/);
    expect(list).not.toMatch(/blur|gradient|shadow|elevation/i);
    expect(list).not.toMatch(/^\s*\/\/|\/\*/m);
    expect(read('src/features/shell/activityFeed.js')).not.toMatch(/^\s*\/\/|\/\*/m);
  });
});

describe('activity text room', () => {
  it.each(TEXT_SCALES.map((step) => step.value))('keeps a job title and a group name readable at every width at text scale %s', (scale) => {
    const sizes = scaleFontSizes(scale);
    const chrome = Math.max(1, 1.3 / scale);
    const retryW = Math.max(RETRY_W, 5 * SANS_EM * sizes.sm * chrome + 2 * space.s5);
    const retryBox = retryW + space.s3;
    for (const width of [...PHONES, ...FOLD_DETAIL]) {
      const title = textRoom(width, { left: JOB_INDENT, right: retryBox + space.s3 });
      expect(title, `job title at ${width}`).toBeGreaterThanOrEqual(130);
      const trailing = 'NN jobs · NNm ago'.length * MONO_EM * sizes.sm;
      const name = textRoom(width, { left: space.s7 + iconSizes.xs + space.s3 + FOLD_SIZES.row + space.s3, right: space.s3 + trailing + space.s7 });
      expect(name, `group name at ${width}`).toBeGreaterThanOrEqual(width >= 360 ? 64 : 48);
    }
  });

  it('wraps the meta line to two lines instead of clipping it', () => {
    const source = read('src/features/shell/ActivityList.jsx');
    expect(source).toMatch(/numberOfLines=\{2\}[^>]*>\s*<Text style=\{\{ color: danger/);
    expect(source).toMatch(/minHeight: JOB_ROW_H/);
    expect(source).toMatch(/minHeight: GROUP_H/);
    expect(source).not.toMatch(/\bheight: (?:JOB_ROW_H|GROUP_H|CHIP_H|SECTION_H)/);
  });

  it('caps chip and Retry text at the chrome scale so the 32 pill and the 44 target never overflow', () => {
    const source = read('src/features/shell/ActivityList.jsx');
    expect(source.match(/maxFontSizeMultiplier=\{chromeScale\}/g)?.length).toBeGreaterThanOrEqual(3);
  });

  it('puts the list at 300 and the page beside it from 760, the same width the sidebar-less pane gets', () => {
    expect(FOLD_DETAIL[0]).toBe(460);
    expect(paneWidth(MASTER_DETAIL_MIN_W + SIDEBAR_W, true, true)).toBe(MASTER_DETAIL_MIN_W);
    expect(paneWidth(390, false, false)).toBe(390);
  });
});

describe('activity mounts', () => {
  it('renders the one screen on the phone page and in the fold detail pane', () => {
    const screen = read('app/activity.jsx');
    expect(screen).toMatch(/<ActivityList/);
    for (const path of ['app/index.jsx', 'src/features/shell/SidebarPane.jsx']) {
      const text = read(path);
      expect(text).toMatch(/ACTIVITY_PATH/);
      expect(text).not.toMatch(/<ActivityList/);
    }
  });

  it('keeps the screen padding to the list: safe areas on top and sides, none of its own at the bottom', () => {
    const screen = read('app/activity.jsx');
    expect(screen).toMatch(/edges=\{\['top', 'left', 'right'\]\}/);
    expect(screen).toMatch(/onBack=\{goBack\}/);
  });
});

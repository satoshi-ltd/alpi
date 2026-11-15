import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

import { nestInset, radii, retiredRadii } from '../../../common/tokens.mjs';

const ROOT = join(import.meta.dirname, '..', '..');
const SLATE = /11, ?17, ?23|230, ?237, ?243|#0b1117|#3d4955|#626e7d|#b1bac4|#eef0f2|#f5f6f8|#f1f3f5|#0a0d11|#0c1014|#11151a|#161b22|#e6edf3|#828b97|#484f58|#1c242c/i;
const TOKENS = Object.keys(radii);
const RETIRED = new RegExp(`radii\\.(${retiredRadii.filter((n) => /^\w+$/.test(n) && !/^\d/.test(n)).join('|')})\\b|radii\\[['"](${retiredRadii.join('|')})['"]\\]`, 'g');

const SHADOW_OK = new Set(['src/theme/tokens.js', 'src/components/Segmented.jsx']);

const HALF_OK = new Set(['DOT', 'px']);

const walk = (dir) =>
  readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return walk(path);
    return /\.jsx?$/.test(entry.name) && !/\.test\.jsx?$/.test(entry.name) ? [path] : [];
  });

const paperViolations = (file, source) => {
  const found = [];
  if (SLATE.test(source)) found.push(`${file}: slate grey`);
  for (const m of source.matchAll(RETIRED)) found.push(`${file}: retired corner ${m[0]}`);
  for (const m of source.matchAll(/radii\.(\w+)/g)) if (!TOKENS.includes(m[1]) && !retiredRadii.includes(m[1])) found.push(`${file}: unknown corner ${m[0]}`);
  for (const m of source.matchAll(/shadowRadius:\s*([\d.]+)/g)) if (parseFloat(m[1]) !== 0 && !SHADOW_OK.has(file)) found.push(`${file}: blurred shadow`);
  for (const m of source.matchAll(/(?:border\w*Radius|\bradius):\s*(\d+(?:\.\d+)?)\b/g)) if (parseFloat(m[1]) !== 0) found.push(`${file}: literal corner ${m[1]}`);
  for (const m of source.matchAll(/\bradius=\{(\d+(?:\.\d+)?)\}/g)) found.push(`${file}: literal corner ${m[1]}`);
  if (/[Rr]adius:\s*space\./.test(source)) found.push(`${file}: corner from spacing`);
  if (/BlurView|expo-blur/.test(source)) found.push(`${file}: blur`);
  if (/border(Left|Right|Top|Bottom)Color:\s*(colors\.)?(danger|dangerText|warning|warningText|success|successText|accent)\b/.test(source)) found.push(`${file}: coloured side stripe`);
  for (const m of source.matchAll(/elevation:\s*([\d.]+)/g)) if (parseFloat(m[1]) !== 0 && !SHADOW_OK.has(file)) found.push(`${file}: elevation`);
  if (/[Rr]adius:\s*['"]50%['"]/.test(source)) found.push(`${file}: percent corner`);
  for (const m of source.matchAll(/[Rr]adius:\s*([A-Za-z_][\w.]*)\s*\/\s*2\b/g)) if (!HALF_OK.has(m[1])) found.push(`${file}: half-height corner ${m[1]}`);
  return found;
};

const read = (rel) => readFileSync(join(ROOT, rel), 'utf8');

describe('paper direction scanner', () => {
  it('passes the five shape tokens, a seam and a pill', () => {
    const source = "const s = { a: { borderRadius: radii.xs }, c: { borderRadius: radii.control }, d: { borderRadius: radii.surface }, e: { borderTopLeftRadius: radii.sheet }, seam: { shadowRadius: 0 }, dot: { borderRadius: radii.pill }, flat: { borderRadius: 0 } };";
    expect(paperViolations('src/features/inbox/Pip.jsx', source)).toEqual([]);
  });

  it.each([
    ['{ borderRadius: radii.chip }', 'retired corner'],
    ['{ borderRadius: radii.tag }', 'retired corner'],
    ['{ borderRadius: radii.lg }', 'retired corner'],
    ['{ borderRadius: radii.md }', 'retired corner'],
    ['{ borderRadius: radii.sm }', 'retired corner'],
    ["{ borderRadius: radii['3xl'] }", 'retired corner'],
    ["{ borderRadius: radii['2xl'] }", 'retired corner'],
    ['{ borderRadius: radii.huge }', 'unknown corner'],
    ['{ shadowRadius: 12 }', 'blurred shadow'],
    ['{ borderRadius: 999 }', 'literal corner'],
    ['{ borderRadius: 4 }', 'literal corner'],
    ['{ borderRadius: 2 }', 'literal corner'],
    ['{ borderTopRightRadius: 12 }', 'literal corner'],
    ['<SkeletonBar radius={3} />', 'literal corner'],
    ['{ borderRadius: space.s2 }', 'corner from spacing'],
    ["import { BlurView } from 'expo-blur';", 'blur'],
    ["{ color: '#626e7d' }", 'slate grey'],
    ["{ color: 'rgba(11,17,23,0.4)' }", 'slate grey'],
    ['{ elevation: 8 }', 'elevation'],
    ['{ borderLeftWidth: 2, borderLeftColor: colors.danger }', 'coloured side stripe'],
    ["{ borderRadius: '50%' }", 'percent corner'],
    ['{ borderRadius: CHIP_H / 2 }', 'half-height corner'],
  ])('flags %s', (source, kind) => {
    expect(paperViolations('src/Planted.jsx', source).join('\n')).toContain(kind);
  });

  it('lets only the theme and the segmented cell cast a blurred shadow', () => {
    expect(paperViolations('src/theme/tokens.js', '{ shadowRadius: 16, elevation: 8 }')).toEqual([]);
    expect(paperViolations('src/components/Sheet.jsx', '{ shadowRadius: 16 }')).toHaveLength(1);
  });
});

describe('the shape of the phone', () => {
  const files = [...walk(join(ROOT, 'src')), ...walk(join(ROOT, 'app'))];

  it('leaves no blur, retired or literal corner or slate grey in any screen, component or the theme', () => {
    const found = files.flatMap((path) => paperViolations(relative(ROOT, path), readFileSync(path, 'utf8')));
    expect(found).toEqual([]);
  });

});

describe('concentric corners', () => {
  it('nests an 8 pt inset child at the parent radius minus the inset', () => {
    expect(nestInset).toBe(8);
    expect(radii.surface - nestInset).toBe(radii.control);
  });

  it('draws the segmented choice as a raised pill cell on a fill pill track', () => {
    const source = read('src/components/Segmented.jsx');
    expect(source).toMatch(/padding: INSET, borderRadius: radii\.pill, backgroundColor: colors\.fill/);
    expect(source).toMatch(/borderRadius: radii\.pill,\s*borderWidth: 1,\s*borderColor: [^,]+,\s*backgroundColor: on \? colors\.raised/);
  });

  it('pairs the action popover at surface with its rows at control, 4 pt in', () => {
    const source = read('src/components/ActionSheet.jsx');
    expect(source).toMatch(/borderRadius: radii\.surface,\s*overflow: 'hidden',\s*padding: nestInset/);
    expect(source).toMatch(/marginHorizontal: popover \? 0 : ACTION_GUTTER[\s\S]*?borderRadius: radii\.control/);
  });

  it('grows the usage ring by its inset around the bar', () => {
    const source = read('src/components/UsageChart.jsx');
    expect(source).toMatch(/borderRadius: radii\.xs,\s*overflow: 'hidden'/);
    expect(source).toMatch(/borderRadius: radii\.xs \+ RING_W \* 2/);
  });

  it('cuts the sheet top at sheet and leaves its bottom square on the screen edge', () => {
    for (const file of ['src/components/Sheet.jsx', 'src/components/ActionSheet.jsx']) {
      const source = read(file);
      expect(source, file).toMatch(/borderTopLeftRadius: radii\.sheet,\s*borderTopRightRadius: radii\.sheet/);
      expect(source, file).not.toMatch(/borderBottom(Left|Right)Radius/);
    }
  });

  it('keeps banners square, a flat bar across their pane', () => {
    for (const file of ['src/components/Banner.jsx', 'src/components/AlertBanner.jsx']) expect(read(file), file).not.toMatch(/[Rr]adius/);
  });
});

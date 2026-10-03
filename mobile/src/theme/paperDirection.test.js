import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = join(import.meta.dirname, '..', '..');
const SLATE = /11, ?17, ?23|230, ?237, ?243|#0b1117|#3d4955|#626e7d|#b1bac4|#eef0f2|#f5f6f8|#f1f3f5|#0a0d11|#0c1014|#11151a|#161b22|#e6edf3|#828b97|#484f58|#1c242c/i;

const ROUND = {
  'src/components/Meter.jsx': [2, 'meter track and fill'],
  'src/features/shell/ShellFooter.jsx': [1, 'unread count badge'],
  'src/features/inbox/Pip.jsx': [1, 'working pip on the avatar corner'],
  'src/features/sheets/TasksSheet.jsx': [1, 'skipped status ring'],
  'src/features/chat/MarkerCard.jsx': [1, 'skipped status ring'],
  'src/features/clarification/ClarificationSheet.jsx': [2, 'radio ring and knob'],
  'src/features/notifications/NotificationRow.jsx': [1, 'unread dot in the notification row gutter'],
  'app/biometric.jsx': [2, 'switch track and thumb'],
  'app/wg/[id]/settings.jsx': [1, 'budget bar'],
};

const HALF_OK = new Set(['DOT', 'dotSize']);

const walk = (dir) =>
  readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return walk(path);
    return /\.jsx?$/.test(entry.name) && !/\.test\.jsx?$/.test(entry.name) ? [path] : [];
  });

const paperViolations = (file, source, round = ROUND) => {
  const found = [];
  if (SLATE.test(source)) found.push(`${file}: slate grey`);
  for (const m of source.matchAll(/radii\.(lg|xl|md|sm)\b|radii\[['"](2xl|3xl)['"]\]/g)) found.push(`${file}: old corner ${m[0]}`);
  for (const m of source.matchAll(/shadowRadius:\s*([\d.]+)/g)) if (parseFloat(m[1]) !== 0) found.push(`${file}: blurred shadow`);
  for (const m of source.matchAll(/[Rr]adius:\s*(\d+(?:\.\d+)?)\b/g)) if (parseFloat(m[1]) > 4) found.push(`${file}: literal corner ${m[1]}`);
  if (/[Rr]adius:\s*space\./.test(source)) found.push(`${file}: corner from spacing`);
  if (/BlurView|expo-blur/.test(source)) found.push(`${file}: blur`);
  if (/border(Left|Right|Top|Bottom)Color:\s*(colors\.)?(danger|dangerText|warning|warningText|success|successText|accent)\b/.test(source)) found.push(`${file}: coloured side stripe`);
  for (const m of source.matchAll(/elevation:\s*([\d.]+)/g)) if (parseFloat(m[1]) !== 0) found.push(`${file}: elevation`);
  if (/[Rr]adius:\s*['"]50%['"]/.test(source)) found.push(`${file}: percent corner`);
  for (const m of source.matchAll(/[Rr]adius:\s*([A-Za-z_][\w.]*)\s*\/\s*2\b/g)) if (!HALF_OK.has(m[1])) found.push(`${file}: half-height corner ${m[1]}`);
  const pills = (source.match(/radii\.pill\b/g) || []).length;
  if (pills > (round[file]?.[0] ?? 0)) found.push(`${file}: pill`);
  return found;
};

describe('paper direction scanner', () => {
  it('passes a sheet, a tag, a seam and an allowed dot', () => {
    const source = "const s = { borderRadius: radii.xs, chip: { borderRadius: radii.tag }, seam: { shadowRadius: 0 }, dot: { borderRadius: radii.pill } };";
    expect(paperViolations('src/features/notifications/NotificationRow.jsx', source)).toEqual([]);
  });

  it.each([
    ['{ borderRadius: radii.lg }', 'old corner'],
    ['{ borderRadius: radii.md }', 'old corner'],
    ["{ borderRadius: radii['3xl'] }", 'old corner'],
    ['{ shadowRadius: 12 }', 'blurred shadow'],
    ['{ borderRadius: 999 }', 'literal corner'],
    ['{ borderTopRightRadius: 12 }', 'literal corner'],
    ['{ borderRadius: space.s2 }', 'corner from spacing'],
    ["import { BlurView } from 'expo-blur';", 'blur'],
    ['{ borderRadius: radii.pill }', 'pill'],
    ["{ color: '#626e7d' }", 'slate grey'],
    ["{ color: 'rgba(11,17,23,0.4)' }", 'slate grey'],
    ['{ elevation: 8 }', 'elevation'],
    ['{ borderLeftWidth: 2, borderLeftColor: colors.danger }', 'coloured side stripe'],
    ["{ borderRadius: '50%' }", 'percent corner'],
    ['{ borderRadius: CHIP_H / 2 }', 'half-height corner'],
  ])('flags %s', (source, kind) => {
    expect(paperViolations('src/Planted.jsx', source).join('\n')).toContain(kind);
  });

  it('flags a pill beyond the count a file is allowed', () => {
    expect(paperViolations('src/features/inbox/Pip.jsx', 'a: radii.pill, b: radii.pill')).toHaveLength(1);
  });
});

describe('the paper phone', () => {
  const files = [...walk(join(ROOT, 'src')), ...walk(join(ROOT, 'app'))];

  it('leaves no blur, old corner, stray pill or slate grey in any screen, component or the theme', () => {
    const found = files.flatMap((path) => paperViolations(relative(ROOT, path), readFileSync(path, 'utf8')));
    expect(found).toEqual([]);
  });

  it('spends every allowed pill on a dot, a badge, a switch or a bar that still exists', () => {
    for (const [file, [count]] of Object.entries(ROUND)) {
      expect((readFileSync(join(ROOT, file), 'utf8').match(/radii\.pill\b/g) || []).length, file).toBe(count);
    }
  });
});

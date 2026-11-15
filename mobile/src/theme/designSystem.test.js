import { readdirSync, readFileSync } from 'node:fs';
import { join, relative } from 'node:path';
import { describe, expect, it } from 'vitest';

import { buttonHeights, buttonRadius } from '../../../common/button.mjs';
import { wellStates } from '../../../common/well.mjs';
import { CHROME_BTN } from '../lib/panes';
import { codeSize } from './code';
import { alpha, fonts, mobile, monoScale, radii, typeFloor } from './tokens';

const ROOT = join(import.meta.dirname, '..', '..');
const walk = (dir) =>
  readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const path = join(dir, entry.name);
    if (entry.isDirectory()) return walk(path);
    return /\.jsx?$/.test(entry.name) && !/\.test\./.test(entry.name) ? [path] : [];
  });
const SOURCES = [...walk(join(ROOT, 'src')), ...walk(join(ROOT, 'app'))].map((path) => [relative(ROOT, path), readFileSync(path, 'utf8')]);
const read = (rel) => readFileSync(join(ROOT, rel), 'utf8');
const hits = (pattern, skip = () => false) =>
  SOURCES.filter(([path]) => !skip(path)).flatMap(([path, text]) =>
    text.split('\n').flatMap((line, i) => (pattern.test(line) ? [`${path}:${i + 1} ${line.trim()}`] : [])));

const RULED_BARS = new Set(['src/components/NotificationBody.jsx', 'src/components/RichText.jsx', 'src/components/Chart.jsx']);

describe('no hairlines on the phone', () => {
  it('draws no 0.5 or 1 pt rule, hairlineWidth or side border anywhere', () => {
    expect(hits(/hairlineWidth|Width:\s*[^,\n]*\b0\.5\b|height:\s*0\.5\b/, (p) => p === 'src/components/Chart.jsx')).toEqual([]);
    expect(hits(/border(Top|Bottom|Left|Right)Width/, (p) => RULED_BARS.has(p))).toEqual([]);
  });

  it('never strokes an edge in a line tone', () => {
    expect(hits(/border\w*Color:\s*(theme\.)?colors\.line2?\b/, (p) => RULED_BARS.has(p))).toEqual([]);
  });
});

describe('disabled is 0.45 everywhere', () => {
  it('dims every disabled or busy control by the shared alpha, never a literal', () => {
    expect(alpha.disabled).toBe(0.45);
    expect(hits(/(disabled|busy|blocked|dimmed)\w*\s*\?\s*0\.\d/i)).toEqual([]);
  });
});

describe('Geist Mono only for machine text', () => {
  it('sets mono at 0.92 of its role and never under the 12 pt floor', () => {
    expect(monoScale).toBe(0.92);
    expect(codeSize(16)).toBe(15);
    expect(codeSize(14)).toBe(13);
    expect(codeSize(12)).toBe(typeFloor);
  });

  it('reaches mono only through the code helper', () => {
    expect(hits(/fonts\.mono/, (p) => p.startsWith('src/theme/'))).toEqual([]);
    expect(typeof fonts.mono).toBe('string');
  });

  it('spends the helper on machine values: code, commands, paths, model ids, keys and ids', () => {
    const users = SOURCES.filter(([, text]) => /\bcode\((theme\.)?fonts\b/.test(text)).map(([path]) => path).sort();
    for (const path of ['src/components/RichText.jsx', 'src/features/approval/ApprovalSheet.jsx', 'src/features/chat/ProfileDetails.jsx', 'src/components/Field.jsx']) {
      expect(users, path).toContain(path);
    }
    for (const path of ['src/components/Eyebrow.jsx', 'src/components/Row.jsx', 'src/components/Pill.jsx', 'src/features/inbox/InboxRow.jsx', 'src/features/chat/Bubble.jsx', 'src/components/Toast.jsx']) {
      expect(users, path).not.toContain(path);
    }
  });
});

describe('radius says what a thing does', () => {
  it('cuts what you press as a pill and what you type in at 12', () => {
    expect(buttonRadius).toBe('pill');
    expect(radii[wellStates.radius]).toBe(12);
    expect(read('src/components/Button.jsx')).toMatch(/borderRadius: radii\[buttonRadius\]/);
    expect(read('src/components/Segmented.jsx')).toMatch(/borderRadius: radii\.pill/);
    expect(read('src/components/Pill.jsx')).toMatch(/borderRadius: radii\.pill/);
    expect(read('src/features/chat/ChatHeader.jsx')).not.toMatch(/borderRadius: radii\.control/);
  });

  it('holds bubbles, toasts, menus and groups at 20 and sheets, dialogs and the composer at 28', () => {
    expect(radii.surface).toBe(20);
    expect(radii.sheet).toBe(28);
    expect(read('src/features/chat/Bubble.jsx')).toMatch(/borderTopLeftRadius: radii\.surface/);
    expect(read('src/components/Toast.jsx')).toMatch(/borderRadius: radii\.surface/);
    expect(read('src/components/Row.jsx')).toMatch(/borderRadius: radii\.surface/);
    expect(read('src/components/Sheet.jsx')).toMatch(/borderTopLeftRadius: radii\.sheet/);
    expect(read('src/features/chat/Composer.jsx')).toMatch(/borderRadius: radii\.sheet/);
  });
});

describe('targets on the phone', () => {
  it('keeps every button at 44 pt or more and every control at 48', () => {
    for (const size of Object.values(buttonHeights)) expect(size.mobile).toBeGreaterThanOrEqual(44);
    expect(buttonHeights.md.mobile).toBe(48);
    expect(mobile.inputH).toBe(48);
    expect(mobile.btnH).toBe(48);
    expect(CHROME_BTN).toBe(mobile.tap);
    expect(mobile.tap).toBe(44);
  });
});

describe('keyboard focus on pressables', () => {
  it.each(['src/components/Button.jsx', 'src/components/Segmented.jsx', 'src/features/chat/Composer.jsx'])('rings %s only on a keyboard focus', (file) => {
    const source = read(file);
    expect(source).toMatch(/useFocusRing\(\)/);
    expect(source).toMatch(/focusRingStyle\(colors, focused\)/);
  });

  it('draws the ring 2 pt out at 60 % ink and nothing at rest', async () => {
    const { focusRingStyle } = await import('../components/focusRing');
    expect(focusRingStyle({ ink: '#141414' }, false)).toBeNull();
    expect(focusRingStyle({ ink: '#141414' }, true)).toEqual({ outlineStyle: 'solid', outlineWidth: 2, outlineOffset: 2, outlineColor: '#14141499' });
  });
});

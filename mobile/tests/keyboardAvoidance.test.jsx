import { readdirSync, readFileSync, statSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

const ROOT = join(import.meta.dirname, '..');

function jsxFiles(dir) {
  return readdirSync(dir).flatMap((name) => {
    const full = join(dir, name);
    if (statSync(full).isDirectory()) return jsxFiles(full);
    return name.endsWith('.jsx') && !name.includes('.test.') ? [full] : [];
  });
}

const screens = jsxFiles(join(ROOT, 'app'));

describe('keyboard avoidance', () => {
  it('routes every text-entry screen through the shared pane', () => {
    const raw = screens.filter((f) => readFileSync(f, 'utf8').includes('<KeyboardAvoidingView'));
    expect(raw).toEqual([]);
  });

  it('drives its own padding and zeroes it on hide, so no gap survives the keyboard', () => {
    const pane = readFileSync(join(ROOT, 'src/components/KeyboardPane.jsx'), 'utf8');
    expect(pane).toMatch(/setPad\(0\)/);
    expect(pane).toMatch(/paddingBottom: pad/);
    expect(pane).not.toMatch(/KeyboardAvoidingView/);
  });

  it('measures the keyboard by screenY — under edge-to-edge its height omits the navigation bar', () => {
    const pane = readFileSync(join(ROOT, 'src/components/KeyboardPane.jsx'), 'utf8');
    expect(pane).toMatch(/screen - frame\.screenY/);
    expect(pane).not.toMatch(/frame\.height/);
    expect(pane).not.toMatch(/endCoordinates\.height/);
  });

  it('subscribes on both platforms — Android edge-to-edge stops the window resizing on its own', () => {
    const pane = readFileSync(join(ROOT, 'src/components/KeyboardPane.jsx'), 'utf8');
    expect(pane).toMatch(/keyboardDidShow/);
    expect(pane).toMatch(/keyboardWillShow/);
    expect(pane).not.toMatch(/Platform\.OS === 'ios' \? 'padding' : undefined/);
    for (const file of screens) {
      expect(readFileSync(file, 'utf8')).not.toMatch(/behavior=\{Platform/);
    }
  });

  it('keeps at least the chat and pairing screens on it, so the guard has real subjects', () => {
    const users = screens.filter((f) => readFileSync(f, 'utf8').includes('<KeyboardPane>'));
    expect(users.length).toBeGreaterThanOrEqual(10);
    expect(users.some((f) => f.endsWith(join('chat', '[id].jsx')))).toBe(true);
    expect(users.some((f) => f.endsWith('pair.jsx'))).toBe(true);
  });
});

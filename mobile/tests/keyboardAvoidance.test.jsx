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

  it('pads by the keyboard frame on the UI thread, so the pane rides it instead of jumping after it lands', () => {
    const pane = readFileSync(join(ROOT, 'src/components/KeyboardPane.jsx'), 'utf8');
    expect(pane).toMatch(/useAnimatedKeyboard\(\)/);
    expect(pane).toMatch(/paddingBottom: keyboard\.height\.value/);
    expect(pane).not.toMatch(/KeyboardAvoidingView/);
    expect(pane).not.toMatch(/Keyboard\.addListener/);
    for (const file of screens) {
      expect(readFileSync(file, 'utf8')).not.toMatch(/behavior=\{Platform/);
    }
  });

  it('keeps the default edge-to-edge insets, which count the navigation bar the old screenY maths measured', () => {
    const pane = readFileSync(join(ROOT, 'src/components/KeyboardPane.jsx'), 'utf8');
    expect(pane).not.toMatch(/isNavigationBarTranslucentAndroid: false/);
  });

  it('pads by the live keyboard height and returns to zero when it hides', async () => {
    const React = await import('react');
    const { render } = await import('@testing-library/react');
    const mock = await import('./mocks/reanimated.js');
    const { KeyboardPane } = await import('../src/components/KeyboardPane');
    const padOf = () => {
      const { container, unmount } = render(React.createElement(KeyboardPane, null, 'x'));
      const style = JSON.parse(container.firstChild.getAttribute('data-style'));
      unmount();
      return style.paddingBottom;
    };
    mock.state.keyboardHeight = 300;
    expect(padOf()).toBe(300);
    mock.state.keyboardHeight = 0;
    expect(padOf()).toBe(0);
  });

  it('keeps at least the chat and pairing screens on it, so the guard has real subjects', () => {
    const users = screens.filter((f) => readFileSync(f, 'utf8').includes('<KeyboardPane>'));
    expect(users.length).toBeGreaterThanOrEqual(10);
    expect(users.some((f) => f.endsWith(join('chat', '[id].jsx')))).toBe(true);
    expect(users.some((f) => f.endsWith('pair.jsx'))).toBe(true);
  });
});

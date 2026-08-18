import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, render } from '@testing-library/react';

afterEach(cleanup);

const h = vi.hoisted(() => ({ options: [], mounts: 0, role: 'admin' }));

vi.mock('react-native', () => ({
  View: ({ children }) => React.createElement('div', {}, children),
  Platform: { OS: 'ios', select: (sel) => sel?.ios ?? sel?.default },
  Keyboard: { addListener: () => ({ remove: () => {} }) },
  StyleSheet: { create: (s) => s },
}));

vi.mock('expo-router', () => ({
  useRouter: () => ({ push: vi.fn(), back: vi.fn(), replace: vi.fn(), canGoBack: () => true }),
  Stack: ({ screenOptions }) => {
    h.options.push(screenOptions);
    React.useEffect(() => {
      h.mounts += 1;
    }, []);
    return React.createElement('div', { 'data-testid': 'nested-stack' });
  },
}));

vi.mock('../src/hooks/useActiveRole', () => ({ useActiveRole: () => h.role }));

import { PaneContext } from '../src/nav/PaneContext';
import { stackAnimation } from '../src/lib/panes';
import ProfileSettingsLayout from '../app/profile/[id]/_layout.jsx';

function inPane(twoPane) {
  return render(
    <PaneContext.Provider value={{ twoPane, side: twoPane ? 'detail' : 'full' }}>
      <ProfileSettingsLayout />
    </PaneContext.Provider>,
  );
}

function lastOptions() {
  return h.options[h.options.length - 1];
}

function stackNode(container) {
  return container.querySelector('[data-testid="nested-stack"]');
}

beforeEach(() => {
  h.options = [];
  h.mounts = 0;
  h.role = 'admin';
});

describe('profile settings nested stack', () => {
  it('slides the settings screens on a phone', () => {
    inPane(false);
    expect(lastOptions().animation).toBe(stackAnimation(false));
    expect(lastOptions().animation).toBe('slide_from_right');
  });

  it('drops the animation under two panes so the detail pane never slides', () => {
    inPane(true);
    expect(lastOptions().animation).toBe('none');
  });

  it('keeps the phone behaviour outside any pane provider', () => {
    render(<ProfileSettingsLayout />);
    expect(lastOptions().animation).toBe('slide_from_right');
  });

  it('keeps the header hidden in both modes', () => {
    inPane(true);
    expect(lastOptions().headerShown).toBe(false);
    cleanup();
    inPane(false);
    expect(lastOptions().headerShown).toBe(false);
  });

  it('hands the navigator one stable options object across redundant renders', () => {
    const { rerender } = inPane(true);
    const before = lastOptions();
    rerender(
      <PaneContext.Provider value={{ twoPane: true, side: 'detail' }}>
        <ProfileSettingsLayout />
      </PaneContext.Provider>,
    );
    expect(lastOptions()).toBe(before);
  });

  it('flips the animation without remounting the navigator', () => {
    const { container, rerender } = inPane(true);
    const node = stackNode(container);
    expect(h.mounts).toBe(1);

    for (const [twoPane, animation] of [[false, 'slide_from_right'], [true, 'none'], [false, 'slide_from_right']]) {
      rerender(
        <PaneContext.Provider value={{ twoPane, side: twoPane ? 'detail' : 'full' }}>
          <ProfileSettingsLayout />
        </PaneContext.Provider>,
      );
      expect(lastOptions().animation).toBe(animation);
      expect(stackNode(container)).toBe(node);
      expect(h.mounts).toBe(1);
    }
  });

  it('renders no navigator for a member', () => {
    h.role = 'member';
    const { container } = inPane(true);
    expect(stackNode(container)).toBeNull();
  });
});

import React from 'react';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook } from '@testing-library/react';

const h = vi.hoisted(() => ({
  pathname: '/wg/alpha',
  canGoBack: vi.fn(() => true),
  isPaneRoot: vi.fn(() => false),
}));

vi.mock('expo-router', () => ({
  usePathname: () => h.pathname,
  useRouter: () => ({ canGoBack: h.canGoBack }),
}));

vi.mock('../lib/panes', () => ({ isPaneRoot: (pathname) => h.isPaneRoot(pathname) }));

import { PaneContext } from '../nav/PaneContext';
import { useShowBack } from './useShowBack';

function paneWrapper(value) {
  return ({ children }) => <PaneContext.Provider value={value}>{children}</PaneContext.Provider>;
}

beforeEach(() => {
  h.pathname = '/wg/alpha';
  h.canGoBack.mockClear().mockReturnValue(true);
  h.isPaneRoot.mockClear().mockReturnValue(false);
});

describe('useShowBack', () => {
  it('shows back outside any provider even at a pane root', () => {
    h.pathname = '/';
    h.isPaneRoot.mockReturnValue(true);
    const { result } = renderHook(() => useShowBack(() => {}));
    expect(result.current).toBe(true);
    expect(h.isPaneRoot).not.toHaveBeenCalled();
    expect(h.canGoBack).not.toHaveBeenCalled();
  });

  it('never shows back without a handler', () => {
    const { result } = renderHook(() => useShowBack(null));
    expect(result.current).toBe(false);
  });

  it('hides back at a pane root in two-pane mode', () => {
    h.isPaneRoot.mockReturnValue(true);
    const { result } = renderHook(() => useShowBack(() => {}), {
      wrapper: paneWrapper({ twoPane: true, side: 'detail' }),
    });
    expect(result.current).toBe(false);
    expect(h.isPaneRoot).toHaveBeenCalledWith('/wg/alpha');
  });

  it('keeps back on a drilled screen in two-pane mode', () => {
    h.pathname = '/wg/alpha/settings';
    const { result } = renderHook(() => useShowBack(() => {}), {
      wrapper: paneWrapper({ twoPane: true, side: 'detail' }),
    });
    expect(result.current).toBe(true);
    expect(h.isPaneRoot).toHaveBeenCalledWith('/wg/alpha/settings');
  });

  it('keeps back on a cold deep link with no history — useBack owns the fallback route', () => {
    h.pathname = '/wg/alpha/settings';
    h.canGoBack.mockReturnValue(false);
    const { result } = renderHook(() => useShowBack(() => {}), {
      wrapper: paneWrapper({ twoPane: true, side: 'detail' }),
    });
    expect(result.current).toBe(true);
  });

  it.each([
    ['single-pane subject', false, '/chat/doc', true],
    ['two-pane subject', true, '/chat/doc', false],
    ['single-pane drill', false, '/wg/alpha/settings', true],
    ['two-pane drill', true, '/wg/alpha/settings', true],
  ])('reads the same on %s however deep the stack is', (_name, twoPane, pathname, expected) => {
    h.pathname = pathname;
    h.isPaneRoot.mockImplementation((p) => p === '/chat/doc');
    for (const depth of [false, true]) {
      h.canGoBack.mockReturnValue(depth);
      const { result, unmount } = renderHook(() => useShowBack(() => {}), {
        wrapper: paneWrapper({ twoPane, side: twoPane ? 'detail' : 'full' }),
      });
      expect(result.current).toBe(expected);
      unmount();
    }
    expect(h.canGoBack).not.toHaveBeenCalled();
  });

  it('recomputes when the pathname changes', () => {
    h.pathname = '/wg/alpha/settings';
    const { result, rerender } = renderHook(() => useShowBack(() => {}), {
      wrapper: paneWrapper({ twoPane: true, side: 'detail' }),
    });
    expect(result.current).toBe(true);
    h.pathname = '/wg/alpha';
    h.isPaneRoot.mockReturnValue(true);
    rerender();
    expect(result.current).toBe(false);
  });
});

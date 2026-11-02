import { readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { renderHook } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({ handlers: [], pathname: '/chat/a', canGoBack: false, replace: null }));

vi.mock('react-native', () => ({
  BackHandler: {
    addEventListener: (_event, fn) => {
      h.handlers.push(fn);
      return { remove: () => { h.handlers = h.handlers.filter((f) => f !== fn); } };
    },
  },
}));
vi.mock('expo-router', () => ({
  usePathname: () => h.pathname,
  useRouter: () => ({ replace: h.replace, canGoBack: () => h.canGoBack }),
}));

import { useSystemBack } from './useBack';

const press = () => h.handlers.at(-1)?.() ?? false;

beforeEach(() => {
  h.handlers = [];
  h.pathname = '/chat/a';
  h.canGoBack = false;
  h.replace = vi.fn();
});

describe('useSystemBack', () => {
  it('returns a detail left without history by a fold to the list instead of closing the app', () => {
    renderHook(() => useSystemBack(false));
    expect(press()).toBe(true);
    expect(h.replace).toHaveBeenCalledWith('/');
  });

  it('falls back to the parent screen of a nested detail', () => {
    h.pathname = '/wg/w1/settings';
    renderHook(() => useSystemBack(false));
    expect(press()).toBe(true);
    expect(h.replace).toHaveBeenCalledWith('/wg/w1');
  });

  it('leaves the system its default when there is history or the list is showing', () => {
    h.canGoBack = true;
    renderHook(() => useSystemBack(false));
    expect(press()).toBe(false);
    h.canGoBack = false;
    h.pathname = '/';
    renderHook(() => useSystemBack(false));
    expect(press()).toBe(false);
    expect(h.replace).not.toHaveBeenCalled();
  });

  it('leaves first-run screens alone, so back still leaves the app from onboarding', () => {
    for (const path of ['/onboarding', '/pair', '/paired', '/biometric', '/debug/aln']) {
      h.pathname = path;
      renderHook(() => useSystemBack(false));
      expect(press()).toBe(false);
    }
    expect(h.replace).not.toHaveBeenCalled();
  });

  it('stays out of the way with two panes and lets go when it unmounts', () => {
    renderHook(() => useSystemBack(true));
    expect(h.handlers).toHaveLength(0);
    const { unmount } = renderHook(() => useSystemBack(false));
    unmount();
    expect(h.handlers).toHaveLength(0);
  });

  it('listens only while the navigator is mounted, never over the connecting or locked screen', () => {
    const layout = readFileSync(resolve(process.cwd(), 'app/_layout.jsx'), 'utf8');
    const inside = layout.slice(layout.indexOf('<AppBootstrap>'), layout.indexOf('</AppBootstrap>'));
    expect(inside).toMatch(/<SystemBack twoPane=\{twoPane\} \/>/);
    expect(layout).not.toMatch(/useSystemBack\(/);
  });
});

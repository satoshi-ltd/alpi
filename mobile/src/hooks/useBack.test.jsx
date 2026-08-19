import { readdirSync, readFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook } from '@testing-library/react';

const h = vi.hoisted(() => ({
  pathname: '/chat/doc',
  canGoBack: vi.fn(() => true),
  answersCanGoBack: true,
  back: vi.fn(),
  replace: vi.fn(),
}));

vi.mock('expo-router', () => ({
  usePathname: () => h.pathname,
  useRouter: () => (h.answersCanGoBack
    ? { back: h.back, replace: h.replace, canGoBack: h.canGoBack }
    : { back: h.back, replace: h.replace }),
}));

import { useBack } from './useBack';

function press() {
  const { result, rerender } = renderHook(() => useBack());
  result.current();
  return { result, rerender };
}

beforeEach(() => {
  h.pathname = '/chat/doc';
  h.answersCanGoBack = true;
  h.canGoBack.mockClear().mockReturnValue(true);
  h.back.mockClear();
  h.replace.mockClear();
});

describe('useBack', () => {
  it('pops the stack whenever there is history to pop', () => {
    press();
    expect(h.back).toHaveBeenCalledTimes(1);
    expect(h.replace).not.toHaveBeenCalled();
  });

  it('replaces its way to the roster when a two-pane open left no history', () => {
    h.canGoBack.mockReturnValue(false);
    press();
    expect(h.replace).toHaveBeenCalledWith('/');
    expect(h.back).not.toHaveBeenCalled();
  });

  it('replaces its way to the section a drilled screen hangs off', () => {
    h.pathname = '/profile/doc/brain/memory/MEMORY.md';
    h.canGoBack.mockReturnValue(false);
    press();
    expect(h.replace).toHaveBeenCalledWith('/profile/doc/brain/memory');
  });

  it('treats a router with no canGoBack as historyless instead of doing nothing', () => {
    h.answersCanGoBack = false;
    press();
    expect(h.replace).toHaveBeenCalledWith('/');
    expect(h.back).not.toHaveBeenCalled();
  });

  it('always moves the router — one call, never zero', () => {
    for (const history of [true, false]) {
      h.back.mockClear();
      h.replace.mockClear();
      h.canGoBack.mockReturnValue(history);
      press();
      expect(h.back.mock.calls.length + h.replace.mock.calls.length).toBe(1);
    }
  });

  it('follows the pathname as the user drills, without a remount', () => {
    h.canGoBack.mockReturnValue(false);
    const { result, rerender } = renderHook(() => useBack());
    result.current();
    expect(h.replace).toHaveBeenLastCalledWith('/');
    h.pathname = '/wg/alpha/settings';
    rerender();
    result.current();
    expect(h.replace).toHaveBeenLastCalledWith('/wg/alpha');
  });
});

const ROOTS = ['app', 'src'];
const EXEMPT = resolve(process.cwd(), 'src/hooks/useBack.js');

function sourceFiles(dir) {
  return readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
    const full = `${dir}/${entry.name}`;
    if (entry.isDirectory()) return sourceFiles(full);
    if (!/\.jsx?$/.test(entry.name) || /\.test\.jsx?$/.test(entry.name)) return [];
    return [full];
  });
}

function offenders(pattern) {
  return ROOTS.flatMap((root) => sourceFiles(resolve(process.cwd(), root)))
    .filter((file) => file !== EXEMPT && pattern.test(readFileSync(file, 'utf8')))
    .map((file) => file.slice(process.cwd().length + 1));
}

describe('one back helper for both pane modes', () => {
  it('leaves no screen calling router.back() on its own', () => {
    expect(offenders(/\.back\(\)/)).toEqual([]);
  });

  it('leaves no screen deciding for itself whether history exists', () => {
    expect(offenders(/canGoBack/)).toEqual([]);
  });
});

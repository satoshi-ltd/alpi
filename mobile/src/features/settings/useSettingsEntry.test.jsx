import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook } from '@testing-library/react';

const h = vi.hoisted(() => ({
  pathname: '/',
  canAdmin: true,
  push: vi.fn(),
  replace: vi.fn(),
  showSheet: vi.fn(),
}));

vi.mock('expo-router', () => ({
  useRouter: () => ({ push: h.push, replace: h.replace }),
}));

vi.mock('../../hooks/useActiveRole', () => ({ useCanAdminEarly: () => h.canAdmin }));

import { SETTINGS_PATH, useSettingsEntry } from './useSettingsEntry';

function press(twoPane, pathname = h.pathname) {
  const { result } = renderHook(() =>
    useSettingsEntry({ twoPane, pathname, showSheet: h.showSheet }),
  );
  result.current();
}

beforeEach(() => {
  h.pathname = '/';
  h.canAdmin = true;
  h.push.mockClear();
  h.replace.mockClear();
  h.showSheet.mockClear();
});

describe('useSettingsEntry', () => {
  it('targets the route desktop uses for its settings pane', () => {
    expect(SETTINGS_PATH).toBe('/settings');
  });

  it('replaces the detail pane in two-pane mode, like opening a chat from the sidebar', () => {
    press(true);
    expect(h.replace).toHaveBeenCalledWith('/settings');
    expect(h.push).not.toHaveBeenCalled();
  });

  it('closes any open overlay before taking the pane', () => {
    press(true);
    expect(h.showSheet).toHaveBeenCalledWith(false);
  });

  it('pushes from a drilled screen so its back stack survives', () => {
    h.pathname = '/wg/alpha/settings';
    press(true);
    expect(h.push).toHaveBeenCalledWith('/settings');
    expect(h.replace).not.toHaveBeenCalled();
  });

  it('replaces from another pane root', () => {
    h.pathname = '/chat/doc';
    press(true);
    expect(h.replace).toHaveBeenCalledWith('/settings');
  });

  it('keeps the phone on the bottom sheet and never navigates', () => {
    press(false);
    expect(h.showSheet).toHaveBeenCalledWith(true);
    expect(h.push).not.toHaveBeenCalled();
    expect(h.replace).not.toHaveBeenCalled();
  });

  it('keeps a member on the sheet even on a tablet — the route would refuse them', () => {
    h.canAdmin = false;
    press(true);
    expect(h.showSheet).toHaveBeenCalledWith(true);
    expect(h.push).not.toHaveBeenCalled();
    expect(h.replace).not.toHaveBeenCalled();
  });

  it('keeps a member on the sheet on a phone too', () => {
    h.canAdmin = false;
    press(false);
    expect(h.showSheet).toHaveBeenCalledWith(true);
    expect(h.replace).not.toHaveBeenCalled();
  });

  it('needs no pathname from the phone surface, which never navigates', () => {
    press(false, undefined);
    expect(h.showSheet).toHaveBeenCalledWith(true);
    expect(h.push).not.toHaveBeenCalled();
    expect(h.replace).not.toHaveBeenCalled();
  });

  it('falls back to root semantics when a caller omits the pathname', () => {
    press(true, undefined);
    expect(h.replace).toHaveBeenCalledWith('/settings');
  });
});

import { beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({
  impactAsync: vi.fn(async () => {}),
  selectionAsync: vi.fn(async () => {}),
  notificationAsync: vi.fn(async () => {}),
}));

vi.mock('expo-haptics', () => ({
  impactAsync: h.impactAsync,
  selectionAsync: h.selectionAsync,
  notificationAsync: h.notificationAsync,
  ImpactFeedbackStyle: { Light: 'light' },
  NotificationFeedbackType: { Warning: 'warning', Success: 'success' },
}));

import { _resetHapticsForTests, selection, success, tap, warning } from './haptics';

beforeEach(() => {
  _resetHapticsForTests();
  for (const fn of Object.values(h)) fn.mockClear();
});

describe('haptics map', () => {
  it('plays a light impact for send and stop', async () => {
    await tap();
    expect(h.impactAsync).toHaveBeenCalledWith('light');
  });

  it('ticks a selection for toggles, pull to refresh and sheet menus', async () => {
    await selection();
    expect(h.selectionAsync).toHaveBeenCalledTimes(1);
  });

  it('plays a warning when an agent needs the user and a success when it lands', async () => {
    await warning();
    expect(h.notificationAsync).toHaveBeenLastCalledWith('warning');
    await success();
    expect(h.notificationAsync).toHaveBeenLastCalledWith('success');
  });

  it('never throws when the device has no haptics', async () => {
    h.selectionAsync.mockRejectedValueOnce(new Error('no vibrator'));
    h.impactAsync.mockRejectedValueOnce(new Error('no vibrator'));
    await expect(selection()).resolves.toBeUndefined();
    await expect(tap()).resolves.toBeUndefined();
  });
});

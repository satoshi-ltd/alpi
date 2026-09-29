import { beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({
  selectionAsync: vi.fn(async () => {}),
  notificationAsync: vi.fn(async () => {}),
}));

vi.mock('expo-haptics', () => ({
  selectionAsync: h.selectionAsync,
  notificationAsync: h.notificationAsync,
  NotificationFeedbackType: { Warning: 'warning' },
}));

import { _resetHapticsForTests, tapFeedback, warnFeedback } from './haptics';

beforeEach(() => {
  _resetHapticsForTests();
  h.selectionAsync.mockClear();
  h.notificationAsync.mockClear();
});

describe('haptics', () => {
  it('plays a selection tick for a toggle and a warning for a destructive confirm', async () => {
    await tapFeedback();
    expect(h.selectionAsync).toHaveBeenCalledTimes(1);
    await warnFeedback();
    expect(h.notificationAsync).toHaveBeenCalledWith('warning');
  });

  it('never throws when the device has no haptics', async () => {
    h.selectionAsync.mockRejectedValueOnce(new Error('no vibrator'));
    await expect(tapFeedback()).resolves.toBeUndefined();
  });
});

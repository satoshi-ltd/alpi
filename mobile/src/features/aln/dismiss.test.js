import { beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({ presented: [], dismiss: vi.fn(async () => {}) }));

vi.mock('expo-notifications', () => ({
  getPresentedNotificationsAsync: async () => h.presented,
  dismissNotificationAsync: h.dismiss,
}));

import { _resetDismissForTests, dismissRequestNotifications } from './dismiss';

const note = (identifier, data) => ({ request: { identifier, content: { data } } });

beforeEach(() => {
  _resetDismissForTests();
  h.dismiss.mockClear();
});

describe('dismissRequestNotifications', () => {
  it('removes only the banners for the resolved request', async () => {
    h.presented = [
      note('aln:d:approval.request:1', { requestId: 'r1' }),
      note('aln:d:clarification.request:2', { rawData: { request_id: 'r1' } }),
      note('aln:d:approval.request:3', { requestId: 'r2' }),
      note('aln:d:wg.done:4', {}),
    ];
    expect(await dismissRequestNotifications('r1')).toBe(2);
    expect(h.dismiss.mock.calls.map(([id]) => id)).toEqual(['aln:d:approval.request:1', 'aln:d:clarification.request:2']);
  });

  it('does nothing without an id and never throws', async () => {
    expect(await dismissRequestNotifications('')).toBe(0);
    h.presented = [note('x', { requestId: 'r1' })];
    h.dismiss.mockRejectedValueOnce(new Error('gone'));
    expect(await dismissRequestNotifications('r1')).toBe(0);
  });
});

import { describe, expect, it } from 'vitest';

import {
  dateBucket,
  filterNotifications,
  groupNotifications,
  isNeedsYou,
  notificationKey,
  triageCounts,
} from '../../../common/notificationTriage.mjs';
import { headlineParts } from '../../../common/notificationHeadline.mjs';

const NOW = new Date(2026, 9, 3, 12, 0, 0).getTime();
const at = (hoursAgo) => Math.floor(NOW / 1000 - hoursAgo * 3600);
const r = (id, extra = {}) => ({ id, profile: 'abby', connectionId: 'casa', type: 'info', status: 'read', created_at: at(1), ...extra });
const unread = (row) => row.status === 'unread';

const ROWS = [
  r('err', { type: 'error', status: 'unread' }),
  r('warn', { type: 'warning', status: 'read' }),
  r('info', { status: 'unread' }),
  r('old', { profile: 'doc', connectionId: 'mirai', created_at: at(30) }),
];

describe('notification triage', () => {
  it('needs you only for an unread error or warning', () => {
    expect(isNeedsYou(ROWS[0], true)).toBe(true);
    expect(isNeedsYou(ROWS[1], false)).toBe(false);
    expect(isNeedsYou(ROWS[2], true)).toBe(false);
  });

  it('counts all, needs you and unread', () => {
    expect(triageCounts(ROWS, unread)).toEqual({ all: 4, needs: 1, unread: 2 });
  });

  it('pins Needs you above the day groups, except under Unread', () => {
    const groups = groupNotifications(ROWS, { filter: 'all', isUnread: unread, nowMs: NOW });
    expect(groups.map((g) => g.label)).toEqual(['Needs you · 1', 'Today', 'Yesterday']);
    expect(groups[1].rows.map((x) => x.id)).toEqual(['warn', 'info']);
    const plain = groupNotifications(filterNotifications(ROWS, 'unread', { isUnread: unread }), { filter: 'unread', isUnread: unread, nowMs: NOW });
    expect(plain.map((g) => g.label)).toEqual(['Today']);
  });

  it('keeps a frozen row in its filter and group after it is read', () => {
    const read = ROWS.map((x) => ({ ...x, status: 'read' }));
    const frozen = { key: notificationKey(ROWS[0]), pinned: true, unread: true };
    expect(filterNotifications(read, 'unread', { isUnread: unread, frozen }).map((x) => x.id)).toEqual(['err']);
    expect(filterNotifications(read, 'needs', { isUnread: unread, frozen }).map((x) => x.id)).toEqual(['err']);
    expect(groupNotifications(read, { filter: 'all', isUnread: unread, frozen, nowMs: NOW })[0].label).toBe('Needs you · 1');
  });


  it('buckets days by the calendar', () => {
    expect(dateBucket(at(1), NOW)).toBe('Today');
    expect(dateBucket(at(13), NOW)).toBe('Yesterday');
    expect(dateBucket(at(24 * 40), NOW)).toBe('Earlier');
  });

  it('splits a body-only notification into a headline and a preview', () => {
    expect(headlineParts({ body: 'Build finished. All 40 checks passed.' })).toEqual({ title: 'Build finished.', preview: 'All 40 checks passed.' });
    expect(headlineParts({ title: 'Digest', body: '\n**14** new emails' })).toEqual({ title: 'Digest', preview: '14 new emails' });
  });
});

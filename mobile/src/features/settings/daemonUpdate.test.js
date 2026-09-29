import { describe, expect, it } from 'vitest';

import { updateOutcome } from './daemonUpdate';

describe('updateOutcome', () => {
  it('names the version it is updating to', () => {
    expect(updateOutcome({ ok: true, updated: true, current: '0.15.26', latest: '0.15.27' })).toEqual({
      title: 'Updating to alpi 0.15.27',
      message: 'the daemon restarts on its own',
    });
  });

  it('says up to date only when the daemon says so', () => {
    expect(updateOutcome({ ok: true, updated: false, current: '0.15.26', latest: '0.15.26', reason: 'up-to-date' })).toEqual({
      title: 'Already up to date',
      message: 'alpi 0.15.26',
    });
  });

  it('tells a Docker or source install how to update by hand instead of claiming success', () => {
    const out = updateOutcome({ ok: false, updated: false, current: '0.15.26', latest: '0.15.27', installer: null, reason: 'manual' });
    expect(out.title).toBe("Can't self-update this install");
    expect(out.message).toMatch(/docker compose pull/);
    expect(out.message).toMatch(/git pull/);
  });

  it('surfaces an offline check and any other reason verbatim', () => {
    expect(updateOutcome({ ok: false, updated: false, reason: 'offline' }).title).toBe('Update check failed');
    expect(updateOutcome({ ok: false, updated: false, reason: 'exit 1' })).toEqual({ title: 'Update failed', message: 'exit 1' });
    expect(updateOutcome(undefined)).toEqual({ title: 'Update failed', message: 'unknown reason' });
  });
});

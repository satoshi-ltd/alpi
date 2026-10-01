import { describe, expect, it } from 'vitest';

import { UPDATE_HINT_CASES } from '../../../../common/updateHint.fixtures.mjs';
import { updateHint } from '../../../../common/updateHint.mjs';
import { updateOutcome } from './daemonUpdate';

describe('the shared manual step', () => {
  it.each(UPDATE_HINT_CASES)('%s with %j reads the shared sentence', (installer, version, sentence) => {
    expect(updateHint(installer, version)).toBe(sentence);
  });
});

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

  it('tells a Docker install which tag to set instead of claiming success', () => {
    const out = updateOutcome({ ok: false, updated: false, current: '0.15.26', latest: '0.15.27', installer: 'docker', reason: 'manual' });
    expect(out.title).toBe("Can't self-update this install");
    expect(out.message).toBe('Set the image tag to 0.15.27 in docker-compose.yml, then docker compose up -d.');
  });

  it('tells a source install to pull, and an older daemon that only says dev both ways', () => {
    expect(updateOutcome({ reason: 'manual', installer: 'source', latest: '0.16.19' }).message).toBe('Run git pull and restart the daemon.');
    const legacy = updateOutcome({ reason: 'manual', installer: 'dev' }).message;
    expect(legacy).toMatch(/docker compose up -d/);
    expect(legacy).toMatch(/git pull/);
  });

  it('surfaces an offline check and any other reason verbatim', () => {
    expect(updateOutcome({ ok: false, updated: false, reason: 'offline' }).title).toBe('Update check failed');
    expect(updateOutcome({ ok: false, updated: false, reason: 'exit 1' })).toEqual({ title: 'Update failed', message: 'exit 1' });
    expect(updateOutcome(undefined)).toEqual({ title: 'Update failed', message: 'unknown reason' });
  });
});

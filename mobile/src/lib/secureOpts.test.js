import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it, vi, beforeEach } from 'vitest';

// Like iOS: an existing item keeps the class it was created with; only its value changes.
const h = vi.hoisted(() => ({ items: new Map(), writes: [], classes: new Map() }));

vi.mock('expo-secure-store', () => ({
  AFTER_FIRST_UNLOCK: 'afu',
  AFTER_FIRST_UNLOCK_THIS_DEVICE_ONLY: 'afu-this-device',
  getItemAsync: async (key) => h.items.get(key) ?? null,
  setItemAsync: async (key, value, opts) => {
    if (!h.classes.has(key)) h.classes.set(key, opts?.keychainAccessible ?? 'default');
    h.items.set(key, value);
    h.writes.push({ key, opts });
  },
  deleteItemAsync: async (key) => { h.items.delete(key); h.classes.delete(key); },
}));

import { loadConnections, saveConnection } from './store';
import { isSpentPairing } from './spentPairings';
import { rememberSpentPairing, _resetSpentPairingsForTests } from './spentPairings';
import { loadState, saveState } from '../features/aln/state';

beforeEach(() => {
  h.items.clear();
  h.classes.clear();
  h.writes.length = 0;
  _resetSpentPairingsForTests?.();
});

describe('secrets stay on this phone', () => {
  it('writes device tokens, notification state and spent grants as this-device-only', async () => {
    await saveConnection({ name: 'casa', url: 'wss://casa.example', token: 't', deviceId: 'd1', kind: 'remote' });
    await saveState('c1', { afterSeq: 3, seenIds: [] });
    await rememberSpentPairing('grant-1');
    const classes = new Set(h.writes.map((w) => w.opts?.keychainAccessible));
    expect(h.writes.length).toBeGreaterThanOrEqual(3);
    expect([...classes]).toEqual(['afu-this-device']);
  });

  it('turns Android backup off so tokens never leave in a device backup', () => {
    const app = JSON.parse(readFileSync(join(import.meta.dirname, '..', '..', 'app.json'), 'utf8'));
    expect(app.expo.android.allowBackup).toBe(false);
  });

  it('moves items an older build created to device-only keys, keeping their contents', async () => {
    const legacy = JSON.stringify({ v: 1, active_id: 'c1', connections: [{ id: 'c1', name: 'casa', url: 'wss://casa.example', token: 't', deviceId: 'd1' }] });
    h.items.set('alpi.connections', legacy);
    h.classes.set('alpi.connections', 'afu');
    h.items.set('alpi.spent-pairings.v1', JSON.stringify(['old-grant']));
    h.classes.set('alpi.spent-pairings.v1', 'default');
    h.items.set('aln.state.c1', JSON.stringify({ afterSeq: 9, seenIds: [], anchored: true }));
    h.classes.set('aln.state.c1', 'afu');

    expect((await loadConnections()).connections.map((c) => c.id)).toEqual(['c1']);
    expect(await isSpentPairing('old-grant')).toBe(true);
    expect((await loadState('c1')).afterSeq).toBe(9);

    for (const legacyKey of ['alpi.connections', 'alpi.spent-pairings.v1', 'aln.state.c1']) {
      expect(h.items.has(legacyKey)).toBe(false);
    }
    expect([...h.classes.values()]).toEqual(['afu-this-device', 'afu-this-device', 'afu-this-device']);
  });

  it('shares one move between concurrent first reads', async () => {
    h.items.set('alpi.spent-pairings.v1', JSON.stringify(['g']));
    const { readMovedItem } = await import('./secureOpts');
    const [a, b] = await Promise.all([
      readMovedItem('alpi.spent-pairings.v2', 'alpi.spent-pairings.v1'),
      readMovedItem('alpi.spent-pairings.v2', 'alpi.spent-pairings.v1'),
    ]);
    expect(a).toBe(b);
    expect(h.writes.filter((w) => w.key === 'alpi.spent-pairings.v2')).toHaveLength(1);
  });
});

import { beforeEach, describe, expect, it, vi } from 'vitest';
import * as SecureStore from 'expo-secure-store';

import { _resetSpentPairingsForTests, isSpentPairing, rememberSpentPairing } from './spentPairings';

beforeEach(() => {
  vi.resetAllMocks();
  _resetSpentPairingsForTests();
  SecureStore.getItemAsync.mockResolvedValue(null);
  SecureStore.setItemAsync.mockResolvedValue(undefined);
});

describe('spent pairing tokens', () => {
  it('remembers a used token and nothing else', async () => {
    expect(await isSpentPairing('tok-1')).toBe(false);
    await rememberSpentPairing('tok-1');
    expect(await isSpentPairing('tok-1')).toBe(true);
    expect(await isSpentPairing('tok-2')).toBe(false);
  });

  it('survives a restart by reading the keychain', async () => {
    SecureStore.getItemAsync.mockResolvedValue(JSON.stringify(['tok-old']));
    expect(await isSpentPairing('tok-old')).toBe(true);
  });

  it('keeps only the ten most recent and ignores empty input and a broken keychain', async () => {
    for (let i = 0; i < 12; i += 1) await rememberSpentPairing(`t${i}`);
    const written = JSON.parse(SecureStore.setItemAsync.mock.calls.at(-1)[1]);
    expect(written).toHaveLength(10);
    expect(written.at(-1)).toBe('t11');
    expect(await isSpentPairing('t0')).toBe(false);
    await rememberSpentPairing('');
    expect(await isSpentPairing(undefined)).toBe(false);
    _resetSpentPairingsForTests();
    SecureStore.getItemAsync.mockRejectedValue(new Error('locked'));
    expect(await isSpentPairing('x')).toBe(false);
  });
});

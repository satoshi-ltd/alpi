import { describe, expect, it, beforeEach, vi } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';

const store = new Map();

vi.mock('expo-secure-store', () => ({
  getItemAsync: vi.fn(async (k) => (store.has(k) ? store.get(k) : null)),
  setItemAsync: vi.fn(async (k, v) => { store.set(k, v); }),
  deleteItemAsync: vi.fn(async (k) => { store.delete(k); }),
}));

import { usePins } from './pins';

beforeEach(() => {
  store.clear();
});

describe('usePins · per-connection scoping', () => {
  it('writes pins under a connection-specific key', async () => {
    const { result } = renderHook(() => usePins('c-A'));
    await waitFor(() => expect(result.current.ready).toBe(true));
    act(() => result.current.toggleProfile('default'));
    await waitFor(() => expect(store.get('alpi.pinned.c-A')).toBeTruthy());
    expect(JSON.parse(store.get('alpi.pinned.c-A'))).toEqual(['p:default']);
    expect(store.get('alpi.pinned.c-B')).toBeUndefined();
  });

  it('does not share `default` pins between two connections', async () => {
    store.set('alpi.pinned.c-A', JSON.stringify(['p:default']));
    const { result } = renderHook(() => usePins('c-B'));
    await waitFor(() => expect(result.current.ready).toBe(true));
    expect(result.current.isProfilePinned('default')).toBe(false);
  });

  it('migrates the legacy global key into the first connection that reads it, then deletes it', async () => {
    store.set('alpi.pinned', JSON.stringify(['p:vera', 'legacy-bare']));
    const { result } = renderHook(() => usePins('c-A'));
    await waitFor(() => expect(result.current.ready).toBe(true));
    expect(result.current.isProfilePinned('vera')).toBe(true);
    expect(result.current.isProfilePinned('legacy-bare')).toBe(true);
    expect(store.has('alpi.pinned')).toBe(false);
    expect(JSON.parse(store.get('alpi.pinned.c-A'))).toEqual(['p:vera', 'p:legacy-bare']);
  });

  it('does not re-migrate the legacy key for a second connection', async () => {
    store.set('alpi.pinned', JSON.stringify(['p:vera']));
    const first = renderHook(() => usePins('c-A'));
    await waitFor(() => expect(first.result.current.ready).toBe(true));
    const second = renderHook(() => usePins('c-B'));
    await waitFor(() => expect(second.result.current.ready).toBe(true));
    expect(second.result.current.isProfilePinned('vera')).toBe(false);
  });

  it('toggles workgroup pins by profile/id under the connection key', async () => {
    const { result } = renderHook(() => usePins('c-A'));
    await waitFor(() => expect(result.current.ready).toBe(true));
    act(() => result.current.toggleWorkgroup('default', 'wg-1'));
    await waitFor(() => expect(result.current.isWorkgroupPinned('default', 'wg-1')).toBe(true));
    expect(JSON.parse(store.get('alpi.pinned.c-A'))).toEqual(['wg:default/wg-1']);
  });

  it('is inert with no active connection', async () => {
    const { result } = renderHook(() => usePins(undefined));
    await waitFor(() => expect(result.current.ready).toBe(true));
    act(() => result.current.toggleProfile('default'));
    expect([...store.keys()]).toEqual([]);
  });
});

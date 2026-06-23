import { beforeEach, describe, expect, it, vi } from 'vitest';
import { renderHook, waitFor } from '@testing-library/react';

import { clearImageCache, useCachedImage } from './useCachedImage';

beforeEach(() => clearImageCache());

describe('useCachedImage', () => {
  it('fetches and exposes the image as a data uri', async () => {
    const call = vi.fn().mockResolvedValue({ data_base64: 'AAA', mime: 'image/png' });
    const { result } = renderHook(() =>
      useCachedImage(call, { id: 'c-A' }, 'default', '/one.png'));
    await waitFor(() => expect(result.current.uri).toBe('data:image/png;base64,AAA'));
    expect(call).toHaveBeenCalledWith('host.attachments.fetch', { profile: 'default', path: '/one.png' });
  });

  it('reloads (does not keep the stale image) when the cache key changes on a reused component', async () => {
    const call = vi.fn()
      .mockResolvedValueOnce({ data_base64: 'AAA', mime: 'image/png' })
      .mockResolvedValueOnce({ data_base64: 'BBB', mime: 'image/png' });
    const { result, rerender } = renderHook(
      ({ ep }) => useCachedImage(call, ep, 'default', '/two.png'),
      { initialProps: { ep: { id: 'c-A' } } },
    );
    await waitFor(() => expect(result.current.uri).toBe('data:image/png;base64,AAA'));

    rerender({ ep: { id: 'c-B' } });
    await waitFor(() => expect(result.current.uri).toBe('data:image/png;base64,BBB'));
    expect(call).toHaveBeenCalledTimes(2);
  });

  it('clears a previous error when the key changes', async () => {
    const call = vi.fn(async (_method, { path }) => {
      if (path === '/err.png') throw new Error('boom');
      return { data_base64: 'CCC', mime: 'image/png' };
    });
    const { result, rerender } = renderHook(
      ({ p }) => useCachedImage(call, { id: 'c-A' }, 'default', p),
      { initialProps: { p: '/err.png' } },
    );
    await waitFor(() => expect(result.current.err).toBe('boom'));

    rerender({ p: '/ok.png' });
    await waitFor(() => expect(result.current.uri).toBe('data:image/png;base64,CCC'));
    expect(result.current.err).toBeNull();
  });

  it('reports an empty response when the daemon returns no data', async () => {
    const call = vi.fn().mockResolvedValue({});
    const { result } = renderHook(() =>
      useCachedImage(call, { id: 'c-A' }, 'default', '/empty.png'));
    await waitFor(() => expect(result.current.err).toBe('empty response'));
    expect(result.current.uri).toBeNull();
  });

  it('serves a key from cache on switch without showing the old image or refetching', async () => {
    const call = vi.fn()
      .mockResolvedValueOnce({ data_base64: 'AAA', mime: 'image/png' })
      .mockResolvedValueOnce({ data_base64: 'BBB', mime: 'image/png' });
    const a = renderHook(() => useCachedImage(call, { id: 'c-A' }, 'default', '/cached.png'));
    await waitFor(() => expect(a.result.current.uri).toBe('data:image/png;base64,AAA'));
    const b = renderHook(() => useCachedImage(call, { id: 'c-B' }, 'default', '/cached.png'));
    await waitFor(() => expect(b.result.current.uri).toBe('data:image/png;base64,BBB'));

    call.mockClear();
    const { result, rerender } = renderHook(
      ({ ep }) => useCachedImage(call, ep, 'default', '/cached.png'),
      { initialProps: { ep: { id: 'c-A' } } },
    );
    await waitFor(() => expect(result.current.uri).toBe('data:image/png;base64,AAA'));
    rerender({ ep: { id: 'c-B' } });
    await waitFor(() => expect(result.current.uri).toBe('data:image/png;base64,BBB'));
    expect(call).not.toHaveBeenCalled();
  });

  it('bounds the cache, evicting the oldest image so base64 data cannot grow without limit', async () => {
    const call = vi.fn(async (_method, { path }) => ({ data_base64: path, mime: 'image/png' }));
    const total = 34;
    for (let i = 0; i < total; i += 1) {
      const { result, unmount } = renderHook(() => useCachedImage(call, { id: 'c' }, 'p', `/n-${i}.png`));
      await waitFor(() => expect(result.current.uri).toBe(`data:image/png;base64,/n-${i}.png`));
      unmount();
    }
    const callsForFirst = () => call.mock.calls.filter((c) => c[1].path === '/n-0.png').length;
    expect(callsForFirst()).toBe(1);

    const { result } = renderHook(() => useCachedImage(call, { id: 'c' }, 'p', '/n-0.png'));
    await waitFor(() => expect(result.current.uri).toBe('data:image/png;base64,/n-0.png'));
    expect(callsForFirst()).toBe(2);
  });

  it('does not fetch without an endpoint', async () => {
    const call = vi.fn();
    const { result } = renderHook(() =>
      useCachedImage(call, null, 'default', '/x.png'));
    await waitFor(() => expect(result.current.uri).toBeNull());
    expect(call).not.toHaveBeenCalled();
  });
});

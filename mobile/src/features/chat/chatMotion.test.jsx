import React from 'react';
import { afterEach, describe, expect, it } from 'vitest';
import { cleanup, render, renderHook } from '@testing-library/react';

import { EnterOnce, listDismissMode, ownConfirmation, useSeenIds } from './chatMotion';

afterEach(cleanup);

function seen(initialProps) {
  return renderHook(({ ids, ready }) => useSeenIds(ids, ready), { initialProps });
}

describe('which rows fade in', () => {
  it('never fades the first ready page, then fades only rows appended after it', () => {
    const { result, rerender } = seen({ ids: [], ready: false });
    expect(result.current.isFresh(0)).toBe(false);
    rerender({ ids: [0, 1, 2], ready: true });
    expect(result.current.isFresh(2)).toBe(false);
    rerender({ ids: [0, 1, 2, 3], ready: true });
    expect(result.current.isFresh(3)).toBe(true);
  });

  it('fades the first turn of a brand-new thread, and keeps it seen when the session id appears', () => {
    const { result, rerender } = seen({ ids: [], ready: true });
    expect(result.current.isFresh(0)).toBe(true);
    result.current.markSeen(0);
    rerender({ ids: [0], ready: false });
    rerender({ ids: [0], ready: true });
    expect(result.current.isFresh(0)).toBe(false);
    expect(result.current.isFresh(1)).toBe(true);
  });

  it('does not fade a recycled cell that mounts again', () => {
    const { result, rerender } = seen({ ids: [0], ready: true });
    rerender({ ids: [0, 1], ready: true });
    const { unmount } = render(<EnterOnce id={1} fresh={result.current.isFresh(1)} onSeen={result.current.markSeen}>x</EnterOnce>);
    unmount();
    expect(result.current.isFresh(1)).toBe(false);
    const again = render(<EnterOnce id={1} fresh={result.current.isFresh(1)} onSeen={result.current.markSeen}>x</EnterOnce>);
    expect(again.container.querySelector('[data-entering]')).toBeNull();
  });

  it('leaves older pages that load above the first page still', () => {
    const { result, rerender } = seen({ ids: [30, 31], ready: true });
    rerender({ ids: [0, 1, 30, 31], ready: true });
    expect(result.current.isFresh(1)).toBe(false);
  });

  it('fades own optimistic posts but not the confirmation that replaces them', () => {
    const { result, rerender } = seen({ ids: [5], ready: true });
    rerender({ ids: [5, -1], ready: true });
    expect(result.current.isFresh(-1, Infinity)).toBe(true);
    expect(ownConfirmation({ seq: 6, from_pubkey: 'me' }, 'me')).toBe(true);
    expect(ownConfirmation({ seq: -1, pending: true, from_pubkey: 'me' }, 'me')).toBe(false);
    expect(ownConfirmation({ seq: 6, from_pubkey: 'hub' }, 'me')).toBe(false);
  });

  it('renders the entrance only for fresh rows', () => {
    const { container } = render(<EnterOnce id={1} fresh onSeen={() => {}}>x</EnterOnce>);
    expect(container.querySelector('[data-entering]').getAttribute('data-entering')).toBe('FadeIn:180');
  });
});

describe('keyboard dismissal on the chat list', () => {
  it('drags the keyboard down interactively on iOS', () => {
    expect(listDismissMode()).toBe('interactive');
  });
});

import { describe, it, expect } from 'vitest';

import { mergeStreamingTurn, isInterruptedTurn } from './chatTurns.js';

describe('mergeStreamingTurn', () => {
  it('returns turns unchanged when there is no pendingTurn', () => {
    const turns = [{ user: 'hi', assistant: 'hello' }];
    expect(mergeStreamingTurn(turns, null)).toEqual(turns);
  });

  it('appends pendingTurn when no persisted turn matches the user text', () => {
    const turns = [{ user: 'previous', assistant: 'earlier reply' }];
    const pendingTurn = { user: 'new question', assistant: 'streaming…' };
    expect(mergeStreamingTurn(turns, pendingTurn)).toEqual([
      { user: 'previous', assistant: 'earlier reply' },
      { user: 'new question', assistant: 'streaming…' },
    ]);
  });

  it('merges over the stub when the daemon already wrote a user-visible stub but assistant is empty', () => {
    const turns = [
      { user: 'previous', assistant: 'earlier reply' },
      { user: 'hola', assistant: '', tools: [] },
    ];
    const pendingTurn = { user: 'hola', assistant: 'stream…', tools: [], pending: true };
    const merged = mergeStreamingTurn(turns, pendingTurn);
    expect(merged).toHaveLength(2);
    expect(merged[1]).toEqual({ user: 'hola', assistant: 'stream…', tools: [], pending: true });
  });

  it('does NOT collapse two consecutive same-text turns when the previous one already finished', () => {
    const turns = [{ user: 'ok', assistant: 'first reply' }];
    const pendingTurn = { user: 'ok', assistant: 'streaming the second…' };
    expect(mergeStreamingTurn(turns, pendingTurn)).toEqual([
      { user: 'ok', assistant: 'first reply' },
      { user: 'ok', assistant: 'streaming the second…' },
    ]);
  });

  it('appends pendingTurn even when last has the same user + assistant — text identity is not a reliable turn id, so prefer a transient duplicate over swallowing a legitimate repeat', () => {
    const turns = [{ user: 'hola', assistant: 'Hola Javi.' }];
    const pendingTurn = { user: 'hola', assistant: 'Hola Javi.', pending: true };
    const merged = mergeStreamingTurn(turns, pendingTurn);
    expect(merged).toHaveLength(2);
    expect(merged[0]).toEqual({ user: 'hola', assistant: 'Hola Javi.' });
    expect(merged[1]).toEqual({ user: 'hola', assistant: 'Hola Javi.', pending: true });
  });

  it('starts a fresh conversation: empty turns + pendingTurn → just the pending', () => {
    const pendingTurn = { user: 'first message', assistant: 'streaming…' };
    expect(mergeStreamingTurn([], pendingTurn)).toEqual([pendingTurn]);
  });

  it('tolerates a non-array turns argument (defensive: hydration races can pass undefined)', () => {
    const pendingTurn = { user: 'hi', assistant: '' };
    expect(mergeStreamingTurn(undefined, pendingTurn)).toEqual([pendingTurn]);
    expect(mergeStreamingTurn(null, pendingTurn)).toEqual([pendingTurn]);
  });
});

describe('isInterruptedTurn', () => {
  it('is true for a server turn with no final reply', () => {
    expect(isInterruptedTurn({ user: 'q', unfinished: true })).toBe(true);
  });

  it('is false while the turn is still streaming live', () => {
    expect(isInterruptedTurn({ user: 'q', unfinished: true, pending: true })).toBe(false);
  });

  it('is false for a completed turn', () => {
    expect(isInterruptedTurn({ user: 'q', assistant: 'a', unfinished: false })).toBe(false);
  });

  it('is false when the flag is absent', () => {
    expect(isInterruptedTurn({ user: 'q', assistant: 'a' })).toBe(false);
  });
});

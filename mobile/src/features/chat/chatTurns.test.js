import { describe, it, expect } from 'vitest';

import { mergeStreamingTurn, isInterruptedTurn, isLastTurnInFlight, autoReadText, consumeAutoRead } from './chatTurns.js';

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

describe('isLastTurnInFlight', () => {
  it('is true for a trailing stub when the session is in_flight', () => {
    const turns = [{ user: 'hola', assistant: '', tools: [] }];
    expect(isLastTurnInFlight(turns, true)).toBe(true);
  });

  it('is false when the session is not in_flight', () => {
    const turns = [{ user: 'hola', assistant: '', tools: [] }];
    expect(isLastTurnInFlight(turns, false)).toBe(false);
  });

  it('is false when the last turn already has a real reply', () => {
    const turns = [{ user: 'hola', assistant: 'the full reply' }];
    expect(isLastTurnInFlight(turns, true)).toBe(false);
  });

  it('is false when the last turn already has tool activity', () => {
    const turns = [{ user: 'hola', assistant: '', tools: [{ tool_id: 't1' }] }];
    expect(isLastTurnInFlight(turns, true)).toBe(false);
  });

  it('is false once this device merged its own live pendingTurn over the stub', () => {
    const turns = [{ user: 'hola', assistant: '', tools: [], pending: true }];
    expect(isLastTurnInFlight(turns, true)).toBe(false);
  });

  it('is false with no turns', () => {
    expect(isLastTurnInFlight([], true)).toBe(false);
    expect(isLastTurnInFlight(undefined, true)).toBe(false);
  });
});

describe('autoReadText', () => {
  it('prefers the just-streamed reply over the persisted last turn (which can still hold the previous turn)', () => {
    expect(autoReadText('the new reply', [{ assistant: 'the previous reply' }])).toBe('the new reply');
  });

  it('falls back to the last persisted turn when there is no streamed reply', () => {
    expect(autoReadText('', [{ assistant: 'persisted' }])).toBe('persisted');
  });

  it('returns empty string when neither source has text', () => {
    expect(autoReadText('', [])).toBe('');
    expect(autoReadText('', null)).toBe('');
    expect(autoReadText(undefined, undefined)).toBe('');
  });
});

describe('consumeAutoRead', () => {
  it('speaks the streamed reply when auto-read is on', () => {
    expect(consumeAutoRead('new reply', true, [{ assistant: 'prev' }]))
      .toEqual({ speak: 'new reply', nextStreamed: '' });
  });

  it('clears the streamed reply but speaks nothing when auto-read is off — so it can\'t go stale across turns', () => {
    expect(consumeAutoRead('stale reply', false, [{ assistant: 'prev' }]))
      .toEqual({ speak: '', nextStreamed: '' });
  });
});

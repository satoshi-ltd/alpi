import { describe, it, expect } from 'vitest';

import { mergeStreamingTurn, isInterruptedTurn, isLastTurnInFlight, isUnfinishedStub, autoReadText, consumeAutoRead, routedModelFor, baselineModelFor, turnFrontier, turnLandedSince } from './chatTurns.js';

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

  it('does NOT merge over a finished tool-only turn that repeats the user text — only the daemon stub is mergeable', () => {
    const turns = [{ user: 'go', assistant: '', tools: [{ tool_id: 't1' }], ended_at: 5 }];
    const pendingTurn = { user: 'go', assistant: '', tools: [], pending: true };
    const merged = mergeStreamingTurn(turns, pendingTurn);
    expect(merged).toHaveLength(2);
    expect(merged[0].tools).toHaveLength(1);
  });

  it('does NOT merge over a finished empty turn that repeats the user text', () => {
    const turns = [{ user: 'go', assistant: '', tools: [], ended_at: 5 }];
    const pendingTurn = { user: 'go', assistant: 'the new answer', tools: [], pending: true };
    expect(mergeStreamingTurn(turns, pendingTurn)).toHaveLength(2);
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

  it('keeps a settled retry visible over the same-text turn it replaces — a different answer is a different turn', () => {
    const turns = [{ user: 'ok', assistant: 'first reply', ended_at: 2 }];
    const pendingTurn = { user: 'ok', assistant: 'the retried reply', pending: false };
    const merged = mergeStreamingTurn(turns, pendingTurn);
    expect(merged).toHaveLength(2);
    expect(merged[1].assistant).toBe('the retried reply');
  });

  it('keeps a settled turn whose answer repeats the persisted one — only the state machine may drop it', () => {
    const turns = [{ user: 'hola', assistant: 'the answer', ended_at: 2 }];
    const pendingTurn = { user: 'hola', assistant: 'the answer', pending: false };
    expect(mergeStreamingTurn(turns, pendingTurn)).toHaveLength(2);
  });

  it('keeps a settled pendingTurn that carries an error visible next to history', () => {
    const turns = [{ user: 'hola', assistant: 'the answer', ended_at: 2 }];
    const pendingTurn = { user: 'hola', assistant: '', pending: false, error: 'ws died' };
    expect(mergeStreamingTurn(turns, pendingTurn)).toHaveLength(2);
  });
});

describe('isUnfinishedStub', () => {
  it('is true only for the daemon stub: user text, no answer, no tools, no ended_at', () => {
    expect(isUnfinishedStub({ user: 'hola', assistant: '', tools: [], ended_at: 0 })).toBe(true);
    expect(isUnfinishedStub({ user: 'hola' })).toBe(true);
    expect(isUnfinishedStub({ user: 'hola', assistant: 'answer' })).toBe(false);
    expect(isUnfinishedStub({ user: 'hola', assistant: '', tools: [{ tool_id: 't1' }] })).toBe(false);
    expect(isUnfinishedStub({ user: 'hola', assistant: '', tools: [], ended_at: 9 })).toBe(false);
    expect(isUnfinishedStub(undefined)).toBe(false);
  });
});

describe('turnFrontier', () => {
  const snap = (turns, extra = {}) => ({ data: { id: 's1', turns }, turnsOffset: 0, ...extra });

  it('counts the daemon total, not the local slice — the two must not be able to coincide', () => {
    const slice = [{ user: 'a', ended_at: 2 }, { user: 'b', ended_at: 3 }];
    expect(turnFrontier(snap(slice, { turnsOffset: 40, totalTurns: 45 })))
      .toEqual({ count: 45, endedAt: 3 });
  });

  it('falls back to offset + slice length when the daemon ships no total', () => {
    expect(turnFrontier(snap([{ user: 'a', ended_at: 3 }], { turnsOffset: 7 })))
      .toEqual({ count: 8, endedAt: 3 });
  });

  it('is the zero frontier for a new thread, an empty read, or a failed read', () => {
    expect(turnFrontier(snap([]))).toEqual({ count: 0, endedAt: 0 });
    expect(turnFrontier({ data: null, turnsOffset: 0 })).toEqual({ count: 0, endedAt: 0 });
    expect(turnFrontier(null)).toEqual({ count: 0, endedAt: 0 });
  });

  it('reads the stub as not-yet-ended so its frontier cannot be mistaken for a finished one', () => {
    expect(turnFrontier(snap([{ user: 'hola', assistant: '', tools: [], ended_at: 0 }])).endedAt).toBe(0);
  });
});

describe('turnLandedSince', () => {
  const snap = (turns, extra = {}) => ({ data: { id: 's1', turns }, turnsOffset: 0, ...extra });
  const ZERO = { count: 0, endedAt: 0 };

  it('is true when a finished turn appeared past the frontier we sent against', () => {
    expect(turnLandedSince(snap([{ user: 'hola', assistant: 'the answer', ended_at: 2 }]), ZERO)).toBe(true);
  });

  it('is true for a finished turn that answered with tools and no prose', () => {
    expect(turnLandedSince(snap([{ user: 'hola', assistant: '', tools: [{ tool_id: 't1' }] }]), ZERO)).toBe(true);
  });

  it('is true for an attachments-only send, whose user text is empty', () => {
    expect(turnLandedSince(snap([{ user: '', assistant: 'described it', ended_at: 2 }]), ZERO)).toBe(true);
  });

  it('is false while the daemon still shows only its in-flight stub', () => {
    expect(turnLandedSince(snap([{ user: 'hola', assistant: '', tools: [], ended_at: 0 }]), ZERO)).toBe(false);
  });

  it('is false when a repeated question finds only its own previous turn — a stale read must not answer for the new one', () => {
    const stale = snap([{ user: 'continue', assistant: 'first answer', ended_at: 10 }]);
    expect(turnLandedSince(stale, turnFrontier(stale))).toBe(false);
  });

  it('is true for an @-mention turn the daemon persisted under a rewritten user string', () => {
    const landed = snap([{ user: '@alice hey can you check?', assistant: 'she says yes', ended_at: 4 }]);
    expect(turnLandedSince(landed, ZERO)).toBe(true);
  });

  it('is true for a retry that rewrote the last turn in place: same count, newer ended_at', () => {
    const before = snap([{ user: 'ok', assistant: 'first reply', ended_at: 10 }]);
    const after = snap([{ user: 'ok', assistant: 'the retried reply', ended_at: 20 }]);
    expect(turnLandedSince(after, turnFrontier(before))).toBe(true);
  });

  it('is true when a rewrite dropped turns: the count moved even though it shrank', () => {
    const before = snap([{ user: 'a', ended_at: 1 }, { user: 'b', ended_at: 2 }, { user: 'c', ended_at: 3 }]);
    const after = snap([{ user: 'a', ended_at: 1 }, { user: 'b2', assistant: 'redone', ended_at: 9 }]);
    expect(turnLandedSince(after, turnFrontier(before))).toBe(true);
  });

  it('is false for an empty, missing, or failed read', () => {
    expect(turnLandedSince(snap([]), ZERO)).toBe(false);
    expect(turnLandedSince(null, ZERO)).toBe(false);
    expect(turnLandedSince({ data: null, turnsOffset: 0 }, ZERO)).toBe(false);
  });

  it('is false without a baseline — an unknown frontier can never prove a landing', () => {
    expect(turnLandedSince(snap([{ user: 'hola', assistant: 'the answer', ended_at: 2 }]), null)).toBe(false);
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

describe('routedModelFor', () => {
  it('returns the short model name when the turn ran on a different model', () => {
    expect(routedModelFor({ model: 'openrouter/deep' }, 'openrouter/main')).toBe('deep');
  });

  it('returns null when the turn ran on the profile model, has no model, or the profile model is unknown', () => {
    expect(routedModelFor({ model: 'openrouter/main' }, 'openrouter/main')).toBeNull();
    expect(routedModelFor({ user: 'old turn' }, 'openrouter/main')).toBeNull();
    expect(routedModelFor({ model: 'openrouter/deep' }, null)).toBeNull();
    expect(routedModelFor(null, 'openrouter/main')).toBeNull();
  });
});

describe('baselineModelFor', () => {
  it('prefers the session model over the profile default so history survives model switches', () => {
    expect(baselineModelFor({ model: 'openrouter/old' }, 'openrouter/new')).toBe('openrouter/old');
    expect(baselineModelFor({}, 'openrouter/new')).toBe('openrouter/new');
    expect(baselineModelFor(null, 'openrouter/new')).toBe('openrouter/new');
    expect(baselineModelFor(null, null)).toBeNull();
  });
});

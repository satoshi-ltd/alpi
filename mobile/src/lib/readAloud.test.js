import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('expo-audio', () => ({
  createAudioPlayer: vi.fn(() => ({ addListener: vi.fn(), play: vi.fn(), remove: vi.fn(), pause: vi.fn() })),
  setAudioModeAsync: vi.fn(async () => {}),
}));

import { enqueueReadAloud, clearReadAloud, stopReadAloud, stripMarkdown } from './readAloud';

beforeEach(() => {
  clearReadAloud();
});

describe('stripMarkdown', () => {
  it('drops code fences, headings, and link syntax', () => {
    expect(stripMarkdown('# Hi\n```x```\n[a](u) **b**')).toBe('Hi a b');
  });

  it('removes emojis, arrows and table pipes', () => {
    expect(stripMarkdown('Done ✅🚀 a → b | c ⭐')).toBe('Done a b c');
  });

  it('reduces bare URLs to their domain', () => {
    expect(stripMarkdown('see https://github.com/soyjavi/alf/pull/1 now')).toBe('see github.com now');
  });
});

describe('enqueueReadAloud', () => {
  it('skips empty / markdown-only text without calling the daemon', () => {
    const call = vi.fn(async () => ({}));
    enqueueReadAloud({ call, key: 'k', voiceId: 'v', text: '   ' });
    enqueueReadAloud({ call, key: 'k2', voiceId: 'v', text: '```only```' });
    expect(call).not.toHaveBeenCalled();
  });

  it('synthesizes stripped text directly when no profile is given', async () => {
    const call = vi.fn(async () => ({}));
    enqueueReadAloud({ call, key: 'k', voiceId: 'v', text: 'hello there' });
    await vi.waitFor(() => expect(call).toHaveBeenCalled());
    expect(call.mock.calls[0][0]).toBe('host.voice.preview');
    expect(call.mock.calls[0][1]).toMatchObject({ voice_id: 'v', text: 'hello there' });
  });

  it('asks the daemon for a script and synthesizes it when a profile is given', async () => {
    const call = vi.fn(async (method) =>
      method === 'host.voice.script' ? { script: 'Spoken version.' } : {},
    );
    enqueueReadAloud({ call, key: 'k', voiceId: 'v', text: 'Done ✅ ok', profile: 'doc' });
    await vi.waitFor(() =>
      expect(call.mock.calls.map(([m]) => m)).toContain('host.voice.preview'),
    );
    expect(call.mock.calls[0]).toEqual(['host.voice.script', { profile: 'doc', text: 'Done ✅ ok' }]);
    const preview = call.mock.calls.find(([m]) => m === 'host.voice.preview');
    expect(preview[1]).toMatchObject({ voice_id: 'v', text: 'Spoken version.' });
  });

  it('falls back to the local strip when the script verb fails (older daemon)', async () => {
    const call = vi.fn(async (method) => {
      if (method === 'host.voice.script') throw new Error('method-not-found');
      return {};
    });
    enqueueReadAloud({ call, key: 'k', voiceId: 'v', text: 'Done ✅ **ok**', profile: 'doc' });
    await vi.waitFor(() =>
      expect(call.mock.calls.map(([m]) => m)).toContain('host.voice.preview'),
    );
    const preview = call.mock.calls.find(([m]) => m === 'host.voice.preview');
    expect(preview[1]).toMatchObject({ text: 'Done ok' });
  });

  it('clear unblocks the queue when the player never finishes', async () => {
    const call = vi.fn(async () => ({ audio_b64: 'AA', mime: 'audio/mpeg' }));
    enqueueReadAloud({ call, key: 'a', voiceId: 'v', text: 'first' });
    await vi.waitFor(() => expect(call).toHaveBeenCalledTimes(1));
    clearReadAloud();
    enqueueReadAloud({ call, key: 'b', voiceId: 'v', text: 'second' });
    await vi.waitFor(() => expect(call).toHaveBeenCalledTimes(2));
  });
});

describe('stop races', () => {
  it('a stop during synth aborts that chain; the next queued item still plays', async () => {
    const { createAudioPlayer } = await import('expo-audio');
    createAudioPlayer.mockClear();
    let releaseFirstPreview;
    const call = vi.fn((verb, args) => {
      if (verb === 'host.voice.preview') {
        if (args?.text === 'first') return new Promise((res) => { releaseFirstPreview = res; });
        return Promise.resolve({ audio_b64: 'AA', mime: 'audio/mpeg' });
      }
      return Promise.resolve({});
    });
    enqueueReadAloud({ call, key: 'a', voiceId: 'v', text: 'first' });
    await vi.waitFor(() => expect(call).toHaveBeenCalledTimes(1));
    stopReadAloud();
    enqueueReadAloud({ call, key: 'a', voiceId: 'v', text: 'again' });
    releaseFirstPreview?.({ audio_b64: 'ZZ', mime: 'audio/mpeg' });
    await vi.waitFor(() => expect(call).toHaveBeenCalledTimes(2));
    // Only the live chain reaches the player — the aborted chain's late audio never plays.
    await vi.waitFor(() => expect(createAudioPlayer).toHaveBeenCalledTimes(1));
    clearReadAloud();
  });
});

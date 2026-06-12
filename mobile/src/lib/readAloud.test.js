import { describe, it, expect, beforeEach, vi } from 'vitest';

vi.mock('expo-audio', () => ({
  createAudioPlayer: vi.fn(() => ({ addListener: vi.fn(), play: vi.fn(), remove: vi.fn(), pause: vi.fn() })),
  setAudioModeAsync: vi.fn(async () => {}),
}));

import { enqueueReadAloud, clearReadAloud, stripMarkdown } from './readAloud';

beforeEach(() => {
  clearReadAloud();
});

describe('stripMarkdown', () => {
  it('drops code fences, headings, and link syntax', () => {
    expect(stripMarkdown('# Hi\n```x```\n[a](u) **b**')).toBe('Hi a b');
  });
});

describe('enqueueReadAloud', () => {
  it('skips empty / markdown-only text without calling the daemon', () => {
    const call = vi.fn(async () => ({}));
    enqueueReadAloud({ call, key: 'k', voiceId: 'v', text: '   ' });
    enqueueReadAloud({ call, key: 'k2', voiceId: 'v', text: '```only```' });
    expect(call).not.toHaveBeenCalled();
  });

  it('synthesizes real text via host.voice.preview', async () => {
    const call = vi.fn(async () => ({}));
    enqueueReadAloud({ call, key: 'k', voiceId: 'v', text: 'hello there' });
    await vi.waitFor(() => expect(call).toHaveBeenCalled());
    expect(call.mock.calls[0][0]).toBe('host.voice.preview');
    expect(call.mock.calls[0][1]).toMatchObject({ voice_id: 'v', text: 'hello there' });
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

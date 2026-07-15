import { describe, expect, it } from 'vitest';

import { CURATED_BY_PROVIDER, DEFAULT_MODEL_BY_PROVIDER, noteFor } from './curatedModels';

describe('anthropic catalog', () => {
  const ids = CURATED_BY_PROVIDER.anthropic.map((m) => m.id);

  it('leads with Fable 5 as flagship and offers Sonnet 5', () => {
    expect(ids[0]).toBe('claude-fable-5');
    expect(noteFor('anthropic/claude-fable-5')).toBe('flagship · 1M');
    expect(ids).toContain('claude-sonnet-5');
  });

  it('no longer offers the retired Sonnet 4.6 / Opus 4.7', () => {
    expect(ids).not.toContain('claude-sonnet-4-6');
    expect(ids).not.toContain('claude-opus-4-7');
  });
});

describe('openai catalog', () => {
  const ids = CURATED_BY_PROVIDER.openai.map((m) => m.id);

  it('is the GPT-5.6 family, not the retired 5.3–5.5 lineup', () => {
    expect(ids).toEqual(['gpt-5.6-sol', 'gpt-5.6-terra', 'gpt-5.6-luna']);
  });
});

describe('default models', () => {
  it('pin the balanced tier of each provider', () => {
    expect(DEFAULT_MODEL_BY_PROVIDER.anthropic).toBe('anthropic/claude-sonnet-5');
    expect(DEFAULT_MODEL_BY_PROVIDER.openai).toBe('openai/gpt-5.6-terra');
  });

  it('only reference ids present in the catalog (drift guard)', () => {
    for (const [provider, qualified] of Object.entries(DEFAULT_MODEL_BY_PROVIDER)) {
      const id = qualified.slice(qualified.indexOf('/') + 1);
      expect(CURATED_BY_PROVIDER[provider].map((m) => m.id)).toContain(id);
    }
  });
});

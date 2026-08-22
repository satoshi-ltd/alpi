import { describe, expect, it } from 'vitest';

import { CLOUD_PROVIDERS, cloudProvider } from './providers';

describe('CLOUD_PROVIDERS', () => {
  it('is the one ordered table behind the create sheet, the list and the key screen', () => {
    expect(CLOUD_PROVIDERS.map((p) => [p.id, p.label, p.env, p.placeholder, p.console])).toEqual([
      ['anthropic', 'Anthropic', 'ANTHROPIC_API_KEY', 'sk-ant-…', 'console.anthropic.com'],
      ['openai', 'OpenAI', 'OPENAI_API_KEY', 'sk-…', 'platform.openai.com'],
      ['openrouter', 'OpenRouter', 'OPENROUTER_API_KEY', 'sk-or-…', 'openrouter.ai'],
      ['gemini', 'Gemini', 'GEMINI_API_KEY', 'AIza…', 'aistudio.google.com'],
    ]);
  });
});

describe('cloudProvider', () => {
  it('resolves a known id', () => expect(cloudProvider('openrouter').env).toBe('OPENROUTER_API_KEY'));

  it.each(['mistral', 'constructor', '__proto__', 'toString'])('is null for %s', (id) => expect(cloudProvider(id)).toBeNull());
});

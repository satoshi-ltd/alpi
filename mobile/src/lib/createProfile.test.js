import { describe, expect, it, vi } from 'vitest';

import { createProfileWithProvider } from './createProfile';

function mockCall() {
  return vi.fn(async (method) => {
    if (method === 'host.providers.ollama_models') return { models: ['local/llama-3'] };
    return {};
  });
}

describe('createProfileWithProvider', () => {
  it('pins the current Anthropic balanced model via host.config.set_field', async () => {
    const call = mockCall();
    const model = await createProfileWithProvider(call, {
      name: 'doc', providerId: 'anthropic', env: 'ANTHROPIC_API_KEY', apiKey: 'sk-ant-x',
    });
    expect(model).toBe('anthropic/claude-sonnet-5');
    expect(call).toHaveBeenCalledWith('host.config.set_field', {
      profile: 'doc', key: 'model', value: 'anthropic/claude-sonnet-5',
    });
  });

  it('pins the current OpenAI balanced model', async () => {
    const call = mockCall();
    const model = await createProfileWithProvider(call, {
      name: 'doc', providerId: 'openai', env: 'OPENAI_API_KEY', apiKey: 'sk-x',
    });
    expect(model).toBe('openai/gpt-5.6-terra');
    expect(call).toHaveBeenCalledWith('host.config.set_field', {
      profile: 'doc', key: 'model', value: 'openai/gpt-5.6-terra',
    });
  });

  it('creates the profile, then sets the key, then the model — in that order', async () => {
    const seq = [];
    const call = vi.fn(async (method) => { seq.push(method); return {}; });
    await createProfileWithProvider(call, {
      name: 'doc', providerId: 'anthropic', env: 'ANTHROPIC_API_KEY', apiKey: 'sk-ant-x',
    });
    expect(seq).toEqual(['host.profile.create', 'host.providers.set_key', 'host.config.set_field']);
  });

  it('openrouter pins the prefixed model the user picked', async () => {
    const call = mockCall();
    const model = await createProfileWithProvider(call, {
      name: 'doc', providerId: 'openrouter', env: 'OPENROUTER_API_KEY', apiKey: 'sk-or-x',
      openrouterModel: 'deepseek/deepseek-v4-pro',
    });
    expect(model).toBe('openrouter/deepseek/deepseek-v4-pro');
    expect(call).toHaveBeenCalledWith('host.config.set_field', {
      profile: 'doc', key: 'model', value: 'openrouter/deepseek/deepseek-v4-pro',
    });
  });

  it('ollama resolves the first matching model (no hardcoded default)', async () => {
    const call = mockCall();
    const model = await createProfileWithProvider(call, {
      name: 'doc', providerId: 'ollama', ollamaName: 'local', ollamaUrl: 'http://localhost:11434/',
    });
    expect(model).toBe('local/llama-3');
  });
});

import { describe, expect, it } from 'vitest';

import { modelLabel } from './modelLabel';

describe('modelLabel', () => {
  it('drops gateway and vendor prefixes from a three-segment id', () => {
    expect(modelLabel('openrouter/deepseek/deepseek-v4-flash-0731')).toBe('deepseek-v4-flash-0731');
  });

  it('drops the vendor prefix from a two-segment id', () => {
    expect(modelLabel('anthropic/claude-opus-5')).toBe('claude-opus-5');
  });

  it('leaves a bare Ollama id untouched', () => {
    expect(modelLabel('llama3')).toBe('llama3');
    expect(modelLabel('gpt-oss:20b')).toBe('gpt-oss:20b');
  });

  it('keeps the tag of a prefixed Ollama id', () => {
    expect(modelLabel('ollama/llama3:8b')).toBe('llama3:8b');
  });

  it('degrades to the last real segment when the id has empty ones', () => {
    expect(modelLabel('openrouter/')).toBe('openrouter');
    expect(modelLabel('openrouter//deepseek-v4-pro')).toBe('deepseek-v4-pro');
    expect(modelLabel('  anthropic/claude-opus-5  ')).toBe('claude-opus-5');
  });

  it('returns an empty string for anything that is not a model id', () => {
    expect(modelLabel('')).toBe('');
    expect(modelLabel('   ')).toBe('');
    expect(modelLabel('/')).toBe('');
    expect(modelLabel(null)).toBe('');
    expect(modelLabel(undefined)).toBe('');
    expect(modelLabel(42)).toBe('');
  });
});

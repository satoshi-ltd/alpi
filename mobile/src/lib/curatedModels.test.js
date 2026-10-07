import { readFileSync } from 'node:fs';
import { join } from 'node:path';
import { describe, expect, it } from 'vitest';

import { CURATED_BY_PROVIDER, DEFAULT_MODEL_BY_PROVIDER, noteFor } from './curatedModels';

const YAML = readFileSync(join(import.meta.dirname, '..', '..', '..', 'alpi', 'providers', 'curated_models.yaml'), 'utf8');

function daemonCatalog(provider) {
  const block = YAML.split(/\n(?=\S)/).find((part) => part.startsWith(`${provider}:`)) ?? '';
  const rows = [];
  for (const match of block.matchAll(/- id: (\S+)\n\s+note: (.+)/g)) rows.push({ id: match[1], note: match[2].trim() });
  return rows;
}

describe('the mirror of the daemon catalog', () => {
  it.each(['openai', 'anthropic'])('lists exactly the daemon\'s %s models, in order, with the same notes', (provider) => {
    expect(daemonCatalog(provider).length).toBeGreaterThan(0);
    expect(CURATED_BY_PROVIDER[provider]).toEqual(daemonCatalog(provider));
  });
});

describe('anthropic catalog', () => {
  const ids = CURATED_BY_PROVIDER.anthropic.map((m) => m.id);

  it('leads with Fable 5.1 as flagship and offers Opus 5.5 and Sonnet 5.5', () => {
    expect(ids[0]).toBe('claude-fable-5-1');
    expect(noteFor('anthropic/claude-fable-5-1')).toBe('flagship · 1M');
    expect(ids).toContain('claude-opus-5-5');
    expect(ids).toContain('claude-sonnet-5-5');
  });

  it('no longer offers the superseded Fable 5, Opus 4.8 or Sonnet 5', () => {
    expect(ids).not.toContain('claude-fable-5');
    expect(ids).not.toContain('claude-opus-4-8');
    expect(ids).not.toContain('claude-sonnet-5');
  });
});

describe('openai catalog', () => {
  const ids = CURATED_BY_PROVIDER.openai.map((m) => m.id);

  it('is the GPT-6 family, not the superseded GPT-5.6 lineup', () => {
    expect(ids).toEqual(['gpt-6-astra', 'gpt-6.1-sol', 'gpt-6-luna']);
  });
});

describe('default models', () => {
  it('pin the balanced tier of each provider', () => {
    expect(DEFAULT_MODEL_BY_PROVIDER.anthropic).toBe('anthropic/claude-sonnet-5-5');
    expect(DEFAULT_MODEL_BY_PROVIDER.openai).toBe('openai/gpt-6.1-sol');
  });

  it('only reference ids present in the catalog (drift guard)', () => {
    for (const [provider, qualified] of Object.entries(DEFAULT_MODEL_BY_PROVIDER)) {
      const id = qualified.slice(qualified.indexOf('/') + 1);
      expect(CURATED_BY_PROVIDER[provider].map((m) => m.id)).toContain(id);
    }
  });
});

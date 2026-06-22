import { describe, expect, it } from 'vitest';

import { CURATED_BY_PROVIDER, noteFor } from './curatedModels';

describe('anthropic catalog', () => {
  const ids = CURATED_BY_PROVIDER.anthropic.map((m) => m.id);

  it('includes Opus 4.8 as flagship', () => {
    expect(ids).toContain('claude-opus-4-8');
    expect(noteFor('anthropic/claude-opus-4-8')).toBe('flagship');
  });

  it('keeps Opus 4.7 but no longer labels it flagship', () => {
    expect(ids).toContain('claude-opus-4-7');
    expect(noteFor('anthropic/claude-opus-4-7')).not.toBe('flagship');
  });

  it('orders the catalog with 4.8 above 4.7 above sonnet/haiku', () => {
    expect(ids.indexOf('claude-opus-4-8')).toBeLessThan(ids.indexOf('claude-opus-4-7'));
    expect(ids.indexOf('claude-opus-4-7')).toBeLessThan(ids.indexOf('claude-sonnet-4-6'));
  });
});

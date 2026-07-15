// Mirror of alpi/providers/curated_models.yaml — keep in sync. Local copy so the picker works even when daemon summary is stale (umbrel docker, custom path).

export const CURATED_BY_PROVIDER = {
  openai: [
    { id: 'gpt-5.6-sol', note: 'flagship · coding' },
    { id: 'gpt-5.6-terra', note: 'balanced' },
    { id: 'gpt-5.6-luna', note: 'cheap · fast' },
  ],
  anthropic: [
    { id: 'claude-fable-5', note: 'flagship · 1M' },
    { id: 'claude-opus-4-8', note: 'agentic coding' },
    { id: 'claude-sonnet-5', note: 'balanced' },
    { id: 'claude-haiku-4-5', note: 'cheap · fast' },
  ],
};

export const DEFAULT_MODEL_BY_PROVIDER = {
  anthropic: 'anthropic/claude-sonnet-5',
  openai: 'openai/gpt-5.6-terra',
};

// Flat tuples — Hermes/Metro dev mode has tripped on Object.entries+destructure for-of.
const ENV_PROVIDER_PAIRS = [
  ['OPENAI_API_KEY', 'openai'],
  ['ANTHROPIC_API_KEY', 'anthropic'],
];

export function synthesizeModels({ model, providerKeys, openrouterModels }) {
  const out = [];
  if (model) out.push(model);
  const keys = providerKeys || [];
  const envs = {};
  for (let i = 0; i < keys.length; i += 1) {
    const k = keys[i];
    if (k && k.env) envs[k.env] = true;
  }
  for (let i = 0; i < ENV_PROVIDER_PAIRS.length; i += 1) {
    const env = ENV_PROVIDER_PAIRS[i][0];
    const provider = ENV_PROVIDER_PAIRS[i][1];
    if (!envs[env]) continue;
    const rows = CURATED_BY_PROVIDER[provider] || [];
    for (let j = 0; j < rows.length; j += 1) {
      out.push(provider + '/' + rows[j].id);
    }
  }
  const orm = openrouterModels || [];
  for (let i = 0; i < orm.length; i += 1) {
    out.push('openrouter/' + orm[i]);
  }
  const seen = new Set();
  const dedup = [];
  for (let i = 0; i < out.length; i += 1) {
    if (!seen.has(out[i])) {
      seen.add(out[i]);
      dedup.push(out[i]);
    }
  }
  return dedup;
}

export function noteFor(modelId) {
  if (!modelId) return null;
  const slash = modelId.indexOf('/');
  if (slash < 0) return null;
  const provider = modelId.slice(0, slash);
  const tail = modelId.slice(slash + 1);
  const rows = CURATED_BY_PROVIDER[provider];
  if (!rows) return null;
  for (let i = 0; i < rows.length; i += 1) {
    if (rows[i].id === tail) return rows[i].note || null;
  }
  return null;
}

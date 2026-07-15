import { DEFAULT_MODEL_BY_PROVIDER } from './curatedModels';

export async function createProfileWithProvider(call, opts) {
  const { name, providerId, env, apiKey, ollamaName, ollamaUrl, openrouterModel } = opts;
  await call('host.profile.create', { name });

  let suggestedModel = null;
  if (providerId === 'ollama') {
    const oname = (ollamaName || '').trim();
    await call('host.providers.add_ollama', {
      profile: name,
      name: oname,
      url: (ollamaUrl || '').trim().replace(/\/$/, ''),
    });
    try {
      const envelope = await call('host.providers.ollama_models', { profile: name });
      const first = (envelope?.models ?? []).find((m) => m.startsWith(`${oname}/`));
      if (first) suggestedModel = first;
    } catch {}
  } else {
    await call('host.providers.set_key', { profile: name, key: env, value: (apiKey || '').trim() });
    if (providerId === 'openrouter') {
      const model = (openrouterModel || '').trim().replace(/^openrouter\//, '');
      await call('host.providers.add_openrouter_model', { profile: name, model });
      suggestedModel = `openrouter/${model}`;
    } else {
      suggestedModel = DEFAULT_MODEL_BY_PROVIDER[providerId] ?? null;
    }
  }

  if (suggestedModel) {
    await call('host.config.set_field', {
      profile: name, key: 'model', value: suggestedModel,
    }).catch(() => {});
  }
  return suggestedModel;
}

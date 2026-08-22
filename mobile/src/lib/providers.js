export const CLOUD_PROVIDERS = [
  { id: 'anthropic', label: 'Anthropic', env: 'ANTHROPIC_API_KEY', placeholder: 'sk-ant-…', console: 'console.anthropic.com' },
  { id: 'openai', label: 'OpenAI', env: 'OPENAI_API_KEY', placeholder: 'sk-…', console: 'platform.openai.com' },
  { id: 'openrouter', label: 'OpenRouter', env: 'OPENROUTER_API_KEY', placeholder: 'sk-or-…', console: 'openrouter.ai' },
  { id: 'gemini', label: 'Gemini', env: 'GEMINI_API_KEY', placeholder: 'AIza…', console: 'aistudio.google.com' },
];

export function cloudProvider(id) {
  return CLOUD_PROVIDERS.find((p) => p.id === id) ?? null;
}

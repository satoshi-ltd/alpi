export function modelLabel(model) {
  if (typeof model !== "string") return "";
  const segments = model.trim().split("/").filter(Boolean);
  return segments.length ? segments[segments.length - 1] : "";
}

const PROVIDER_NAMES = {
  openrouter: "OpenRouter",
  anthropic: "Anthropic",
  openai: "OpenAI",
  ollama: "Ollama",
  ollama_chat: "Ollama",
  groq: "Groq",
  gemini: "Google",
};

export function modelProvider(model) {
  if (typeof model !== "string") return "";
  const segments = model.trim().split("/").filter(Boolean);
  if (segments.length < 2) return "";
  return PROVIDER_NAMES[segments[0].toLowerCase()] ?? segments[0];
}

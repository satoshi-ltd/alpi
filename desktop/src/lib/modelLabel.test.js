import { describe, expect, it } from "vitest";

import { modelLabel, modelProvider } from "./modelLabel.js";

describe("modelLabel", () => {
  it("keeps only the model slug from a routed identifier", () => {
    expect(modelLabel("openrouter/deepseek/deepseek-v4-flash-latest"))
      .toBe("deepseek-v4-flash-latest");
  });

  it("preserves bare and Ollama model names", () => {
    expect(modelLabel("gpt-oss:20b")).toBe("gpt-oss:20b");
    expect(modelLabel("ollama/llama3:8b")).toBe("llama3:8b");
  });

  it("handles empty and malformed values", () => {
    expect(modelLabel("openrouter//deepseek-v4-pro")).toBe("deepseek-v4-pro");
    expect(modelLabel("   ")).toBe("");
    expect(modelLabel(null)).toBe("");
  });
});

describe("modelProvider", () => {
  it("names the provider a routed identifier goes through", () => {
    expect(modelProvider("openrouter/deepseek/deepseek-v4.1-flash:nitro")).toBe("OpenRouter");
    expect(modelProvider("anthropic/claude-fable-5-2")).toBe("Anthropic");
    expect(modelProvider("openai/gpt-6.2-sol")).toBe("OpenAI");
    expect(modelProvider("ollama/llama3:8b")).toBe("Ollama");
    expect(modelProvider("ollama_chat/llama3:8b")).toBe("Ollama");
    expect(modelProvider("groq/llama-4")).toBe("Groq");
    expect(modelProvider("gemini/gemini-4-neon")).toBe("Google");
    expect(modelProvider("chatgpt-plan/gpt-6.2-sol")).toBe("ChatGPT plan");
  });

  it("shows an unknown prefix as written and nothing for a bare name", () => {
    expect(modelProvider("bedrock/anthropic.claude-opus-5-5")).toBe("bedrock");
    expect(modelProvider("gpt-oss:20b")).toBe("");
    expect(modelProvider(null)).toBe("");
  });
});

describe("runsOnPlan", () => {
  it("is true only for a model of the ChatGPT plan", async () => {
    const { PLAN_BUDGET_HINT, runsOnPlan } = await import("./modelLabel.js");
    expect(runsOnPlan("chatgpt-plan/gpt-6.2-sol")).toBe(true);
    expect(runsOnPlan(" ChatGPT-Plan/gpt-6-luna")).toBe(true);
    for (const model of ["openai/gpt-6.2-sol", "openrouter/openai/gpt-6.2-sol", "chatgpt-plan", "", null, undefined]) {
      expect(runsOnPlan(model)).toBe(false);
    }
    expect(PLAN_BUDGET_HINT).toBe("ChatGPT plan turns are not counted.");
  });
});

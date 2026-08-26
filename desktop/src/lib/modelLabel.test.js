import { describe, expect, it } from "vitest";

import { modelLabel } from "./modelLabel.js";

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

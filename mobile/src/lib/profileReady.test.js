import { describe, it, expect } from "vitest";
import {
  profileHasProviders,
  profileReadyToChat,
  profileEmptyState,
} from "./profileReady.js";

describe("profileHasProviders", () => {
  it("returns false for null", () => {
    expect(profileHasProviders(null)).toBe(false);
  });

  it("trusts the precomputed flag when present", () => {
    expect(profileHasProviders({ has_any_provider: true })).toBe(true);
    expect(profileHasProviders({ has_any_provider: false })).toBe(false);
  });

  it("falls back to raw arrays for older daemons", () => {
    expect(profileHasProviders({ provider_ollama: [{ name: "local" }] })).toBe(true);
    expect(profileHasProviders({ models: ["openai/gpt-4o"] })).toBe(true);
    expect(profileHasProviders({ provider_keys: [{ env: "OPENAI_API_KEY" }] })).toBe(true);
    expect(profileHasProviders({})).toBe(false);
    expect(profileHasProviders({ provider_ollama: [], models: [], provider_keys: [] })).toBe(false);
  });

  it("explicit flag wins over arrays", () => {
    // If the daemon precomputed false, arrays leaked from a partial merge should not override.
    expect(
      profileHasProviders({ has_any_provider: false, provider_keys: [{ env: "X" }] }),
    ).toBe(false);
  });
});

describe("profileReadyToChat", () => {
  it.each([
    [null, false],
    [{}, false],
    [{ model: "" }, false],
    [{ model: "openai/gpt-4o" }, true],
  ])("%j → %s", (profile, expected) => {
    expect(profileReadyToChat(profile)).toBe(expected);
  });
});

describe("profileEmptyState", () => {
  it("null → needs-provider", () => {
    expect(profileEmptyState(null)).toBe("needs-provider");
  });

  it("model set → ready", () => {
    expect(profileEmptyState({ model: "openai/gpt-4o" })).toBe("ready");
  });

  it("providers but no model → needs-model", () => {
    expect(
      profileEmptyState({ has_any_provider: true }),
    ).toBe("needs-model");
  });

  it("no providers, no model → needs-provider", () => {
    expect(profileEmptyState({ has_any_provider: false })).toBe("needs-provider");
    expect(profileEmptyState({})).toBe("needs-provider");
  });
});

import { beforeEach, describe, expect, it } from "vitest";
import { invoke } from "@tauri-apps/api/core";
import { applyProvider } from "./ProviderPickerForm.jsx";

beforeEach(() => {
  invoke.mockReset();
  invoke.mockResolvedValue(null);
});

describe("applyProvider", () => {
  it("selects the OpenRouter model after registering it", async () => {
    await expect(applyProvider("work", {
      id: "openrouter",
      keyValue: "sk-or-test",
      model: "openrouter/deepseek/deepseek-chat",
    })).resolves.toBe("OpenRouter deepseek/deepseek-chat ready");

    expect(invoke).toHaveBeenNthCalledWith(1, "provider_set_key", {
      profile: "work",
      key: "OPENROUTER_API_KEY",
      value: "sk-or-test",
    });
    expect(invoke).toHaveBeenNthCalledWith(2, "provider_add_openrouter_model", {
      profile: "work",
      model: "deepseek/deepseek-chat",
    });
    expect(invoke).toHaveBeenNthCalledWith(3, "set_config_field", {
      profile: "work",
      key: "model",
      value: "openrouter/deepseek/deepseek-chat",
    });
  });
});

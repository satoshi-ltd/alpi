import { beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

const h = vi.hoisted(() => ({ invoke: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: h.invoke }));

import ProviderPickerForm, {
  applyProvider,
  isProviderValueValid,
  providerHint,
} from "./ProviderPickerForm.jsx";

const CATALOG = {
  OPENROUTER_API_KEY: 12,
  ANTHROPIC_API_KEY: 4,
  OPENAI_API_KEY: 3,
  GEMINI_API_KEY: 0,
};

describe("providerHint", () => {
  it("counts what the provider would offer once its key is set", () => {
    expect(providerHint("openrouter", { providerCatalog: CATALOG }))
      .toBe("12 models · needs a key");
    expect(providerHint("anthropic", { providerCatalog: CATALOG }))
      .toBe("4 models · needs a key");
  });

  it("says zero when alpi curates nothing for that provider", () => {
    expect(providerHint("gemini", { providerCatalog: CATALOG }))
      .toBe("0 models · needs a key");
  });

  it("falls back to the plain hint when the daemon sent no catalog", () => {
    expect(providerHint("openai", {})).toBe("needs a key");
  });

  it("shows the stored key preview once a provider is configured", () => {
    expect(
      providerHint("openrouter", {
        providerCatalog: CATALOG,
        configuredEnvs: new Set(["OPENROUTER_API_KEY"]),
        configuredPreviews: new Map([["OPENROUTER_API_KEY", "sk-…a6af"]]),
      }),
    ).toBe("12 models · key · sk-…a6af");
  });

  it("counts live ollama models only once an endpoint exists", () => {
    expect(
      providerHint("ollama", { ollamaEndpointCount: 0, ollamaModelCount: 9 }),
    ).toBe("local · no API key");
    expect(
      providerHint("ollama", { ollamaEndpointCount: 2, ollamaModelCount: 1 }),
    ).toBe("local · 1 model");
    expect(
      providerHint("ollama", { ollamaEndpointCount: 1, ollamaModelCount: 12 }),
    ).toBe("local · 12 models");
  });
});

describe("ProviderPickerForm", () => {
  const VALUE = { id: "ollama", name: "", url: "http://localhost:11434" };

  it("lists the providers in priority order", () => {
    render(<ProviderPickerForm value={VALUE} onChange={() => {}} />);
    fireEvent.click(screen.getByText("Ollama"));
    const labels = ["Ollama", "OpenRouter", "Anthropic", "OpenAI", "Gemini"];
    for (const label of labels) expect(screen.getAllByText(label).length).toBeGreaterThan(0);
    const html = document.body.innerHTML;
    const order = labels.map((l) => html.lastIndexOf(">" + l + "<"));
    expect(order).toEqual([...order].sort((a, b) => a - b));
  });

  it("switching provider resets the value to that provider", () => {
    const onChange = vi.fn();
    render(<ProviderPickerForm value={VALUE} onChange={onChange} />);
    fireEvent.click(screen.getByText("Ollama"));
    fireEvent.click(screen.getByText("OpenRouter"));
    expect(onChange).toHaveBeenCalledWith(
      expect.objectContaining({ id: "openrouter", model: "" }),
    );
  });
});

describe("model selection", () => {
  const OR = { id: "openrouter", keyValue: "", model: "" };

  it("picks a saved model from a dropdown instead of a chip grid", () => {
    const onChange = vi.fn();
    render(
      <ProviderPickerForm
        value={OR}
        onChange={onChange}
        savedOpenRouterModels={["deepseek/one", "z-ai/two"]}
      />,
    );
    fireEvent.click(screen.getByText("Known models"));
    fireEvent.click(screen.getByText("z-ai/two"));
    expect(onChange).toHaveBeenCalledWith(expect.objectContaining({ model: "z-ai/two" }));
  });

  const SLUG = "provider/model-id (optional)";

  it("toggles between the list and a manual slug from the label row", () => {
    render(
      <ProviderPickerForm
        value={OR}
        onChange={() => {}}
        savedOpenRouterModels={["deepseek/one"]}
      />,
    );
    expect(screen.queryByPlaceholderText(SLUG)).toBeNull();
    fireEvent.click(screen.getByText("Enter any slug"));
    expect(screen.getByPlaceholderText(SLUG)).toBeTruthy();
    fireEvent.click(screen.getByText("Pick from the list"));
    expect(screen.queryByPlaceholderText(SLUG)).toBeNull();
  });

  it("falls back to the text field when the profile has no saved models", () => {
    render(<ProviderPickerForm value={OR} onChange={() => {}} savedOpenRouterModels={[]} />);
    expect(screen.getByPlaceholderText(SLUG)).toBeTruthy();
    expect(screen.queryByText("Enter any slug")).toBeNull();
  });
});

describe("isProviderValueValid", () => {
  it("does not require a model: this dialog configures the provider, not the profile", () => {
    expect(
      isProviderValueValid({ id: "openrouter", keyValue: "sk-test", model: "" }, {
        configuredEnvs: new Set(),
      }),
    ).toBe(true);
  });

  it("still requires a key when none is stored", () => {
    expect(
      isProviderValueValid({ id: "openrouter", keyValue: "", model: "" }, {
        configuredEnvs: new Set(),
      }),
    ).toBe(false);
  });
});

describe("applyProvider", () => {
  beforeEach(() => {
    h.invoke.mockReset();
    h.invoke.mockResolvedValue(undefined);
  });

  function invokedCommands() {
    return h.invoke.mock.calls.map((c) => c[0]);
  }

  it("saves only the key when no model is given", async () => {
    const msg = await applyProvider("work", {
      id: "openrouter",
      keyValue: "sk-new",
      model: "",
    });
    expect(h.invoke).toHaveBeenCalledWith("provider_set_key", {
      profile: "work",
      key: "OPENROUTER_API_KEY",
      value: "sk-new",
    });
    expect(invokedCommands()).toEqual(["provider_set_key"]);
    expect(msg).toBe("OpenRouter key saved");
  });

  it("adds the model but leaves a configured profile on the model it already runs", async () => {
    const msg = await applyProvider(
      "work",
      { id: "openrouter", keyValue: "", model: "vendor/new" },
      { currentModel: "openrouter/vendor/old" },
    );
    expect(h.invoke).toHaveBeenCalledWith("provider_add_openrouter_model", {
      profile: "work",
      model: "vendor/new",
    });
    expect(invokedCommands()).not.toContain("set_config_field");
    expect(msg).toBe("vendor/new added to OpenRouter models");
  });

  it("seeds the profile model only when it has none", async () => {
    const msg = await applyProvider(
      "work",
      { id: "openrouter", keyValue: "", model: "openrouter/vendor/new" },
      { currentModel: "" },
    );
    expect(h.invoke).toHaveBeenCalledWith("set_config_field", {
      profile: "work",
      key: "model",
      value: "openrouter/vendor/new",
    });
    expect(msg).toBe("OpenRouter vendor/new ready");
  });

  it("registers an ollama endpoint without touching the model", async () => {
    const msg = await applyProvider("work", {
      id: "ollama",
      name: "home",
      url: "http://localhost:11434/",
    });
    expect(h.invoke).toHaveBeenCalledWith("provider_add_ollama", {
      profile: "work",
      name: "home",
      url: "http://localhost:11434",
    });
    expect(invokedCommands()).toEqual(["provider_add_ollama"]);
    expect(msg).toBe("Ollama @home added");
  });
});

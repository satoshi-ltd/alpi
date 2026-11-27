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

  it("offers Groq with what the daemon would list for its key", () => {
    expect(providerHint("groq", { providerCatalog: { GROQ_API_KEY: 2 } })).toBe("2 models · needs a key");
    expect(isProviderValueValid({ id: "groq", keyValue: "gsk_x" })).toBe(true);
    expect(isProviderValueValid({ id: "groq", keyValue: " " })).toBe(false);
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

describe("ChatGPT plan", () => {
  const VALUE = { id: "ollama", name: "", url: "http://localhost:11434" };
  const SIGNED = { signed_in: true, email: "a@example.com", plan_declined: false, models: 4 };

  it("is offered between OpenAI and Gemini only when the daemon reports its state", () => {
    const { unmount } = render(<ProviderPickerForm value={VALUE} onChange={() => {}} />);
    fireEvent.click(screen.getByText("Ollama"));
    expect(screen.queryByText("ChatGPT plan")).toBeNull();
    unmount();

    render(<ProviderPickerForm value={VALUE} onChange={() => {}} chatgpt={{ signed_in: false }} />);
    fireEvent.click(screen.getByText("Ollama"));
    const html = document.body.innerHTML;
    const at = (label) => html.lastIndexOf(">" + label + "<");
    expect(at("OpenAI")).toBeLessThan(at("ChatGPT plan"));
    expect(at("ChatGPT plan")).toBeLessThan(at("Gemini"));
  });

  it("says what selecting it does, and who is signed in once it is", () => {
    const onChange = vi.fn();
    const { rerender } = render(<ProviderPickerForm value={VALUE} onChange={onChange} chatgpt={{ signed_in: false }} />);
    fireEvent.click(screen.getByText("Ollama"));
    fireEvent.click(screen.getByText("ChatGPT plan"));
    expect(onChange).toHaveBeenCalledWith({ id: "chatgpt-plan" });

    const form = (chatgpt, extra = {}) => <ProviderPickerForm value={{ id: "chatgpt-plan" }} onChange={onChange} chatgpt={chatgpt} {...extra} />;
    rerender(form({ signed_in: false }));
    expect(screen.getByText("Opens your browser to sign in.")).toBeTruthy();
    expect(screen.queryByPlaceholderText("paste API key")).toBeNull();
    expect(screen.queryByText("Manage usage")).toBeNull();

    rerender(form({ signed_in: false }, { signingIn: true }));
    expect(screen.getByText("Waiting for your browser…")).toBeTruthy();

    rerender(form({ signed_in: false, plan_declined: true }));
    expect(screen.getByText("Plan use was declined. Sign in again to allow it.")).toBeTruthy();

    rerender(form(SIGNED));
    const account = screen.getByLabelText("ChatGPT account");
    expect(account.value).toBe("a@example.com");
    expect(account.readOnly).toBe(true);
    expect(account.disabled).toBe(false);
    expect(screen.getByText("Manage usage")).toBeTruthy();
    expect(screen.queryByText(/models/)).toBeNull();
    expect(screen.queryByText("Opens your browser to sign in.")).toBeNull();
  });

  it("hints its state and needs no key to be valid", () => {
    expect(providerHint("chatgpt-plan", { chatgpt: { signed_in: false } })).toBe("needs sign-in");
    expect(providerHint("chatgpt-plan", { chatgpt: SIGNED })).toBe("4 models · a@example.com");
    expect(providerHint("chatgpt-plan", { chatgpt: { signed_in: false, plan_declined: true } })).toBe("plan use declined");
    expect(isProviderValueValid({ id: "chatgpt-plan" })).toBe(true);
  });

  it("signs in through the app and confirms plan use the first time", async () => {
    h.invoke.mockReset();
    h.invoke.mockResolvedValueOnce({ signed_in: true, email: "a@example.com", first_sign_in: true });
    expect(await applyProvider("work", { id: "chatgpt-plan" })).toBe("You're using your ChatGPT plan · a@example.com");
    expect(h.invoke.mock.calls).toEqual([["chatgpt_sign_in", { profile: "work" }]]);

    h.invoke.mockResolvedValueOnce({ signed_in: true, email: "a@example.com", first_sign_in: false });
    expect(await applyProvider("work", { id: "chatgpt-plan" })).toBe("Signed in as a@example.com");

    h.invoke.mockResolvedValueOnce({ signed_in: false, plan_declined: true });
    await expect(applyProvider("work", { id: "chatgpt-plan" })).rejects.toThrow("Plan use was declined. Sign in again to allow it.");
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

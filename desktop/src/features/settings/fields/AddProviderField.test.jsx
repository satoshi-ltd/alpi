import { beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";

const h = vi.hoisted(() => ({ invoke: vi.fn(), notify: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: h.invoke }));
vi.mock("@tauri-apps/plugin-opener", () => ({ openUrl: vi.fn(async () => {}) }));
vi.mock("../../../primitives/Notification.jsx", () => ({ useNotify: () => h.notify }));

import { AddProviderField } from "./AddProviderField.jsx";
import { BudgetField } from "./boundaries.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

const PROFILE = { name: "work", model: "chatgpt-plan/gpt-6.2-sol", provider_keys: [], provider_ollama: [], models: [] };

function open(profile, onSaved = vi.fn()) {
  render(<AddProviderField profile={profile} onSaved={onSaved} />);
  fireEvent.click(screen.getByRole("button", { name: "Providers" }));
  fireEvent.click(screen.getByText("Ollama"));
  fireEvent.click(screen.getByText("ChatGPT plan"));
  return onSaved;
}

beforeEach(() => {
  cleanup();
  h.notify.mockReset();
  h.invoke.mockReset();
  h.invoke.mockImplementation(async (command) => (command === "ollama_models" ? [] : undefined));
});

describe("ChatGPT plan in Providers", () => {
  it("signed out offers one action, and the wait in the browser can be cancelled", async () => {
    let settle;
    h.invoke.mockImplementation((command) => {
      if (command === "chatgpt_sign_in") return new Promise((_resolve, reject) => { settle = reject; });
      return Promise.resolve(command === "ollama_models" ? [] : undefined);
    });
    open({ ...PROFILE, provider_chatgpt: { signed_in: false } });

    expect(screen.getByText("Opens your browser to sign in.")).toBeTruthy();
    expect(screen.queryByText("Sign out")).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Continue with ChatGPT" }));
    await waitFor(() => expect(screen.getByText("Waiting for your browser…")).toBeTruthy());

    const cancel = screen.getByRole("button", { name: "Cancel" });
    expect(cancel.disabled).toBe(false);
    fireEvent.click(cancel);
    expect(h.invoke).toHaveBeenCalledWith("chatgpt_sign_in_cancel");
    settle(new Error("sign-in cancelled"));
    await waitFor(() => expect(h.invoke.mock.calls.filter((c) => c[0] === "chatgpt_sign_in")).toHaveLength(1));
    expect(h.notify).not.toHaveBeenCalled();
  });

  it("shows only what the daemon said when the sign-in fails", async () => {
    h.invoke.mockImplementation(async (command) => {
      if (command === "chatgpt_sign_in") throw "alp -32010: chatgpt-sign-in — the sign-in was declined in the browser; nothing was saved";
      return command === "ollama_models" ? [] : undefined;
    });
    open({ ...PROFILE, provider_chatgpt: { signed_in: false } });
    fireEvent.click(screen.getByRole("button", { name: "Continue with ChatGPT" }));

    await waitFor(() => expect(h.notify).toHaveBeenCalledWith(expect.objectContaining({
      message: "the sign-in was declined in the browser; nothing was saved", variant: "error",
    })));
  });

  it("signed in shows the account, no sign-in button, and a sign out that says what it costs", async () => {
    h.invoke.mockImplementation(async (command) => {
      if (command === "chatgpt_sign_out") return { ok: true, revoked: true, model_cleared: true };
      return command === "ollama_models" ? [] : undefined;
    });
    const onSaved = open({ ...PROFILE, provider_chatgpt: { signed_in: true, email: "a@example.com", models: 10 } });

    expect(screen.getByLabelText("ChatGPT account").value).toBe("a@example.com");
    expect(screen.queryByRole("button", { name: "Continue with ChatGPT" })).toBeNull();
    expect(screen.getByRole("button", { name: "Close" })).toBeTruthy();

    fireEvent.click(screen.getByText("Sign out"));
    expect(screen.getByText("@work is left without a model.")).toBeTruthy();
    expect(h.invoke).not.toHaveBeenCalledWith("chatgpt_sign_out", expect.anything());
    fireEvent.click(screen.getAllByRole("button", { name: "Sign out" }).at(-1));

    await waitFor(() => expect(h.invoke).toHaveBeenCalledWith("chatgpt_sign_out", { profile: "work" }));
    await waitFor(() => expect(h.notify).toHaveBeenCalledWith({ message: "Signed out · @work has no model", variant: "success" }));
    expect(onSaved).toHaveBeenCalled();
  });

  it("offers Sign out when a registration is saved but its session ended", () => {
    open({ ...PROFILE, provider_chatgpt: { signed_in: false, email: "a@example.com", registered: true } });

    expect(screen.getByText("Sign out")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Continue with ChatGPT" })).toBeTruthy();
  });

  it("warns for longer when OpenAI did not confirm the sign out", async () => {
    h.invoke.mockImplementation(async (command) => {
      if (command === "chatgpt_sign_out") return { ok: true, revoked: false, model_cleared: false };
      return command === "ollama_models" ? [] : undefined;
    });
    open({ ...PROFILE, model: "openrouter/x/y", provider_chatgpt: { signed_in: true, email: "a@example.com" } });
    fireEvent.click(screen.getByText("Sign out"));
    expect(screen.getByText("@work can no longer use plan models.")).toBeTruthy();
    fireEvent.click(screen.getAllByRole("button", { name: "Sign out" }).at(-1));

    await waitFor(() => expect(h.notify).toHaveBeenCalledWith({
      message: "Signed out here only. Remove alpi in ChatGPT settings.", variant: "error", duration: 8000,
    }));
  });
});

describe("Budget on a plan profile", () => {
  it("says plan turns are not counted, and says nothing on a paid model", () => {
    const { rerender } = render(<BudgetField profile={{ name: "work", model: "chatgpt-plan/gpt-6.2-sol", budget_daily_usd: 2 }} />);
    expect(screen.getByText("ChatGPT plan turns are not counted.")).toBeTruthy();

    rerender(<BudgetField profile={{ name: "work", model: "openai/gpt-6.2-sol", budget_daily_usd: 2 }} />);
    expect(screen.queryByText("ChatGPT plan turns are not counted.")).toBeNull();
  });
});

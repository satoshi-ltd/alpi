import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";

vi.mock("@tauri-apps/api/core", () => ({ invoke: vi.fn(async () => []) }));
vi.mock("../primitives/Notification.jsx", () => ({ useNotify: () => () => {} }));

import CreateProfileModal from "./CreateProfileModal.jsx";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };

const backdrop = () => document.querySelector('[role="dialog"]').parentElement;

describe("CreateProfileModal", () => {
  it("uses the shared Field for every text input", () => {
    render(<CreateProfileModal open onClose={() => {}} />);
    const inputs = document.querySelectorAll('[role="dialog"] input');
    expect(inputs.length).toBeGreaterThan(0);
    for (const input of inputs) expect(input).toHaveClass("ds-field");
  });

  it("closes on a backdrop click while pristine", () => {
    const onClose = vi.fn();
    render(<CreateProfileModal open onClose={onClose} />);
    fireEvent.mouseDown(backdrop());
    expect(onClose).toHaveBeenCalled();
  });

  it("ignores the backdrop once a name is typed, but Cancel still closes", () => {
    const onClose = vi.fn();
    render(<CreateProfileModal open onClose={onClose} />);
    fireEvent.change(screen.getByPlaceholderText(/work · personal/), { target: { value: "work" } });
    fireEvent.mouseDown(backdrop());
    expect(onClose).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }));
    expect(onClose).toHaveBeenCalled();
  });

  it("links the name field to its validation message", () => {
    render(<CreateProfileModal open existingNames={["work"]} onClose={() => {}} />);
    const input = screen.getByPlaceholderText(/work · personal/);
    expect(input).not.toHaveAttribute("aria-invalid");
    fireEvent.change(input, { target: { value: "work" } });
    const message = screen.getByText("@work already exists");
    expect(input).toHaveAttribute("aria-invalid", "true");
    expect(input.getAttribute("aria-describedby")).toBe(message.id);
  });
});

describe("ChatGPT plan in New profile", () => {
  it("is offered when the daemon answers for it, then creates the profile and signs in", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    invoke.mockReset();
    invoke.mockImplementation(async (command) => {
      if (command === "chatgpt_status") return { signed_in: false };
      if (command === "chatgpt_sign_in") return { signed_in: true, email: "a@example.com", first_sign_in: true };
      return [];
    });
    const onCreated = vi.fn();
    render(<CreateProfileModal open existingNames={["default"]} onCreated={onCreated} onClose={() => {}} />);

    fireEvent.click(screen.getByText("Ollama"));
    fireEvent.click(await screen.findByText("ChatGPT plan"));
    fireEvent.change(screen.getAllByRole("textbox")[0], { target: { value: "work" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue with ChatGPT" }));

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("work"));
    expect(invoke.mock.calls.map((c) => c[0])).toEqual(["chatgpt_status", "profile_create", "chatgpt_sign_in"]);
    expect(invoke).toHaveBeenCalledWith("chatgpt_sign_in", { profile: "work" });
  });

  it("stays out when the daemon does not know the sign-in", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    invoke.mockReset();
    invoke.mockImplementation(async (command) => {
      if (command === "chatgpt_status") throw new Error("host.providers.chatgpt_status: method-not-found");
      return [];
    });
    render(<CreateProfileModal open existingNames={["default"]} onCreated={() => {}} onClose={() => {}} />);

    fireEvent.click(screen.getByText("Ollama"));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("chatgpt_status", { profile: "default" }));
    expect(screen.queryByText("ChatGPT plan")).toBeNull();
    expect(screen.getAllByText("OpenAI").length).toBeGreaterThan(0);
  });
});

describe("cancelling the ChatGPT sign-in from New profile", () => {
  it("ends the wait and still opens the profile that was created", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    let refuse;
    invoke.mockReset();
    invoke.mockImplementation((command) => {
      if (command === "chatgpt_status") return Promise.resolve({ signed_in: false });
      if (command === "chatgpt_sign_in") return new Promise((_resolve, reject) => { refuse = reject; });
      return Promise.resolve([]);
    });
    const onCreated = vi.fn();
    render(<CreateProfileModal open existingNames={["default"]} onCreated={onCreated} onClose={() => {}} />);
    fireEvent.click(screen.getByText("Ollama"));
    fireEvent.click(await screen.findByText("ChatGPT plan"));
    fireEvent.change(screen.getAllByRole("textbox")[0], { target: { value: "work" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue with ChatGPT" }));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("chatgpt_sign_in", { profile: "work" }));

    const cancel = screen.getByRole("button", { name: "Cancel" });
    expect(cancel.disabled).toBe(false);
    fireEvent.click(cancel);
    expect(invoke).toHaveBeenCalledWith("chatgpt_sign_in_cancel");
    expect(onCreated).not.toHaveBeenCalled();
    refuse("sign-in cancelled");

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("work"));
  });
});

describe("closing New profile during the ChatGPT sign-in", () => {
  async function start(invoke, signIn) {
    invoke.mockReset();
    invoke.mockImplementation((command) => {
      if (command === "chatgpt_status") return Promise.resolve({ signed_in: false });
      if (command === "chatgpt_sign_in") return signIn();
      return Promise.resolve([]);
    });
    const view = render(<CreateProfileModal open existingNames={["default"]} onCreated={() => {}} onClose={() => {}} />);
    fireEvent.click(screen.getByText("Ollama"));
    fireEvent.click(await screen.findByText("ChatGPT plan"));
    fireEvent.change(screen.getAllByRole("textbox")[0], { target: { value: "work" } });
    fireEvent.click(screen.getByRole("button", { name: "Continue with ChatGPT" }));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("chatgpt_sign_in", { profile: "work" }));
    return view;
  }

  it("ends the wait when the dialog is closed by any route", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    const view = await start(invoke, () => new Promise(() => {}));
    expect(invoke).not.toHaveBeenCalledWith("chatgpt_sign_in_cancel");

    view.rerender(<CreateProfileModal open={false} existingNames={["default"]} onCreated={() => {}} onClose={() => {}} />);

    await waitFor(() => expect(invoke).toHaveBeenCalledWith("chatgpt_sign_in_cancel"));
  });

  it("sends no cancel when the sign-in finished and the dialog then closes", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    const view = await start(invoke, () => Promise.resolve({ signed_in: true, email: "a@example.com", first_sign_in: true }));
    await waitFor(() => expect(screen.getByRole("button", { name: "Continue with ChatGPT" }).disabled).toBe(false));

    view.rerender(<CreateProfileModal open={false} existingNames={["default"]} onCreated={() => {}} onClose={() => {}} />);

    expect(invoke).not.toHaveBeenCalledWith("chatgpt_sign_in_cancel");
  });
});

describe("closing New profile before the ChatGPT sign-in starts", () => {
  async function submitHeld(invoke, onCreated, onCreatedBehind = () => {}) {
    const created = {};
    invoke.mockReset();
    invoke.mockImplementation((command, args) => {
      if (command === "chatgpt_status") return Promise.resolve({ signed_in: false });
      if (command === "profile_create") return new Promise((resolve) => { created[args.name] = resolve; });
      if (command === "chatgpt_sign_in") return new Promise(() => {});
      return Promise.resolve([]);
    });
    const props = { existingNames: ["default"], onCreated, onCreatedBehind, onClose: () => {} };
    const view = render(<CreateProfileModal open {...props} />);
    const fill = async (name) => {
      fireEvent.click(screen.getByText("Ollama"));
      fireEvent.click(await screen.findByText("ChatGPT plan"));
      fireEvent.change(screen.getAllByRole("textbox")[0], { target: { value: name } });
      fireEvent.click(screen.getByRole("button", { name: "Continue with ChatGPT" }));
      await waitFor(() => expect(created[name]).toBeTypeOf("function"));
    };
    await fill("work");
    const show = (open) => view.rerender(<CreateProfileModal open={open} {...props} />);
    return { created, fill, show };
  }

  it("creates the profile without opening the browser", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    const onCreated = vi.fn();
    const { created, show } = await submitHeld(invoke, onCreated);

    show(false);
    created.work([]);

    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("work"));
    expect(invoke).not.toHaveBeenCalledWith("chatgpt_sign_in", expect.anything());
  });

  it("stays out of the browser when the dialog was reopened meanwhile", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    const onCreated = vi.fn();

    const onCreatedBehind = vi.fn();
    const { created, show } = await submitHeld(invoke, onCreated, onCreatedBehind);

    show(false);
    show(true);
    created.work([]);

    await waitFor(() => expect(onCreatedBehind).toHaveBeenCalledWith("work"));
    expect(invoke).not.toHaveBeenCalledWith("chatgpt_sign_in", expect.anything());
    expect(onCreated).not.toHaveBeenCalled();
  });

  it("has the app only reload its roster for a profile created behind the dialog", () => {
    const app = readFileSync(join(import.meta.dirname, "..", "App.jsx"), "utf8");
    expect(app).toMatch(/<CreateProfileModal[\s\S]{0,300}onCreatedBehind=\{\(\) => reload\(\)\}/);
  });

  it("leaves a second profile in the making alone when the first one lands", async () => {
    const { invoke } = await import("@tauri-apps/api/core");
    const onCreated = vi.fn();
    const onCreatedBehind = vi.fn();
    const { created, fill, show } = await submitHeld(invoke, onCreated, onCreatedBehind);

    show(false);
    show(true);
    await fill("home");
    invoke.mockClear();
    created.work([]);

    await waitFor(() => expect(onCreatedBehind).toHaveBeenCalledWith("work"));
    expect(onCreated).not.toHaveBeenCalled();
    expect(invoke).not.toHaveBeenCalledWith("chatgpt_sign_in_cancel");
    expect(screen.getByRole("button", { name: "Continue with ChatGPT" }).disabled).toBe(true);
  });
});

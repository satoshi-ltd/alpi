import { describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor } from "@testing-library/react";

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

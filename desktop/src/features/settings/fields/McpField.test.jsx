import { describe, it, expect, beforeEach, vi } from "vitest";
import { render, screen, fireEvent, act } from "@testing-library/react";

const h = vi.hoisted(() => ({ invoke: vi.fn() }));
vi.mock("@tauri-apps/api/core", () => ({ invoke: h.invoke }));
vi.mock("../../../primitives/Notification.jsx", () => ({ useNotify: () => () => {} }));

import { McpField } from "./McpField.jsx";

const CONN = "conn-123";

beforeEach(() => {
  h.invoke.mockReset();
  h.invoke.mockResolvedValue([]);
});

describe("McpField — every daemon call is scoped to the connection", () => {
  it("profile_mcp_tools carries connectionId when a server is opened", async () => {
    const profile = { name: "work", mcps: [{ name: "fs", command: "uvx", args: [], env_keys: [] }] };
    render(<McpField profile={profile} connectionId={CONN} onSaved={() => {}} />);
    await act(async () => { fireEvent.click(screen.getByText("fs")); });
    expect(h.invoke).toHaveBeenCalledWith(
      "profile_mcp_tools",
      { profile: "work", name: "fs", connectionId: CONN },
    );
  });

  it("mcp_remove carries connectionId", async () => {
    const profile = { name: "work", mcps: [{ name: "fs", command: "uvx", args: [], env_keys: [] }] };
    render(<McpField profile={profile} connectionId={CONN} onSaved={() => {}} />);
    await act(async () => { fireEvent.click(screen.getByText("fs")); });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Remove" })); });
    const removes = screen.getAllByRole("button", { name: "Remove" });
    await act(async () => { fireEvent.click(removes[removes.length - 1]); });
    expect(h.invoke).toHaveBeenCalledWith(
      "mcp_remove",
      expect.objectContaining({ profile: "work", name: "fs", connectionId: CONN }),
    );
  });

  it("mcp_add carries connectionId", async () => {
    render(<McpField profile={{ name: "work", mcps: [] }} connectionId={CONN} onSaved={() => {}} />);
    await act(async () => { fireEvent.click(screen.getByText("+ Add MCP")); });
    fireEvent.change(screen.getByPlaceholderText("github · notion · linear"), { target: { value: "fs" } });
    fireEvent.change(screen.getByPlaceholderText("npx · uvx · python · /path/to/server"), { target: { value: "uvx" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Add" })); });
    expect(h.invoke).toHaveBeenCalledWith(
      "mcp_add",
      expect.objectContaining({ profile: "work", name: "fs", command: "uvx", connectionId: CONN }),
    );
  });
});

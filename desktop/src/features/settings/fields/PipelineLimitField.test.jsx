import { act, fireEvent, render, screen } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";

const { invoke, notify } = vi.hoisted(() => ({ invoke: vi.fn(), notify: vi.fn() }));

vi.mock("@tauri-apps/api/core", () => ({ invoke }));
vi.mock("../../../primitives/Notification.jsx", () => ({ useNotify: () => notify }));

import { PipelineLimitField, pipelineLimitLabel } from "./PipelineLimitField.jsx";

describe("PipelineLimitField", () => {
  beforeEach(() => { invoke.mockReset(); notify.mockReset(); });

  it("labels the cap, its origin and the admission queue", () => {
    expect(pipelineLimitLabel(0)).toBe("unlimited");
    expect(pipelineLimitLabel(5, 3)).toBe("5 workgroups · 3 queued");
    expect(pipelineLimitLabel(5, 0, "default")).toBe("5 workgroups · from default");
  });

  it("persists a cap above 99 through the host config field", async () => {
    invoke.mockResolvedValue({ ok: true });
    const onSaved = vi.fn();
    render(<PipelineLimitField profile={{ name: "mira", max_active_workgroups: 5, queued_pipelines: 0 }} onSaved={onSaved} />);

    fireEvent.click(screen.getByText("5 workgroups"));
    fireEvent.change(screen.getByRole("textbox"), { target: { value: "100" } });
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Save" })); });

    expect(invoke).toHaveBeenCalledWith("set_config_field", { profile: "mira", key: "alp.max_active_workgroups", value: "100" });
    expect(onSaved).toHaveBeenCalled();
  });

  it("lets a hub with its own cap go back to the default profile's", async () => {
    invoke.mockResolvedValue({ ok: true });
    render(<PipelineLimitField profile={{ name: "mira", max_active_workgroups: 5, max_active_workgroups_origin: "profile" }} />);

    fireEvent.click(screen.getByText("5 workgroups"));
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Use default" })); });

    expect(invoke).toHaveBeenCalledWith("unset_config_field", { profile: "mira", key: "alp.max_active_workgroups" });
  });

  it("hides the inherit action on the default profile and on inherited values", () => {
    render(<PipelineLimitField profile={{ name: "scout", max_active_workgroups: 5, max_active_workgroups_origin: "default" }} />);
    fireEvent.click(screen.getByText("5 workgroups · from default"));
    expect(screen.queryByRole("button", { name: "Use default" })).toBeNull();
  });
  it("pins the inherited number as an explicit override on save", async () => {
    invoke.mockResolvedValue({ ok: true });
    render(<PipelineLimitField profile={{ name: "mira", max_active_workgroups: 5, max_active_workgroups_origin: "default" }} />);

    fireEvent.click(screen.getByText("5 workgroups · from default"));
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Save" })); });

    expect(invoke).toHaveBeenCalledWith("set_config_field", { profile: "mira", key: "alp.max_active_workgroups", value: "5" });
  });
});

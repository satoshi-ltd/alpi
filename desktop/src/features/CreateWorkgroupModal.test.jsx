import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { invoke } from "@tauri-apps/api/core";

const { notifyMock } = vi.hoisted(() => ({ notifyMock: vi.fn() }));

vi.mock("../primitives/Notification.jsx", () => ({
  useNotify: () => notifyMock,
}));

vi.mock("../hooks/useProfileDetail.js", () => ({
  useProfileDetail: () => ({
    detail: {
      peers: [
        { id: "peer-1", name: "Muse", pubkey_b64: "pub-1" },
      ],
    },
  }),
}));

import CreateWorkgroupModal from "./CreateWorkgroupModal.jsx";

beforeEach(() => {
  invoke.mockReset();
  notifyMock.mockReset();
});

describe("CreateWorkgroupModal", () => {
  it("creates a workgroup by hand when no recipe is chosen", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "workgroup_create") return "wg-1";
      return null;
    });
    render(
      <CreateWorkgroupModal
        open
        profiles={[{ name: "mira", counts: { peers: 1 } }]}
        connectionId="casa"
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("team-alpha · roadmap · customers"), {
      target: { value: "Launch" },
    });
    fireEvent.click(screen.getByText("@peer-1"));
    fireEvent.click(screen.getByRole("button", { name: "Create" }));

    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("workgroup_create", {
        profile: "mira",
        name: "Launch",
        memberPeerIds: ["peer-1"],
        budgetUsd: null,
        briefing: null,
        pipeline: null,
        connectionId: "casa",
      });
    });
  });

  const HOTEL_RECIPE = {
    yaml: "hub: mira\nname: proj-{slug}\n",
    recipe_id: "hotel",
    meta: {
      id: "hotel",
      hub: "mira",
      name: "proj-{slug}",
      briefing: "Hotel draft briefing",
      params: { slug: { pattern: "^[a-z-]+$" } },
      inputs: {
        brief: {
          label: "Hotel brief",
          dest: "brief.md",
          required: true,
          placeholder: "paste the raw client brief",
        },
      },
      has_project: true,
    },
  };

  it("imports a project recipe, fills params + recipe inputs, and launches from its content", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "workgroup_pick_recipe") return HOTEL_RECIPE;
      if (cmd === "workgroup_launch_recipe") return { workgroup_id: "wg-9" };
      return null;
    });

    const onCreated = vi.fn();
    render(
      <CreateWorkgroupModal
        open
        profiles={[{ name: "mira", counts: { peers: 1 } }]}
        connectionId="casa"
        onCreated={onCreated}
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Import recipe…" }));

    const slug = await screen.findByPlaceholderText("^[a-z-]+$");
    fireEvent.change(slug, { target: { value: "casa-bahia" } });
    expect(screen.getByText("HUB — FROM RECIPE")).toBeTruthy();
    expect(screen.getByDisplayValue("Hotel draft briefing")).toBeTruthy();

    expect(screen.getByRole("button", { name: "Launch" }).disabled).toBe(true);
    fireEvent.change(screen.getByPlaceholderText("paste the raw client brief"), {
      target: { value: "Boutique hotel, 12 rooms, casabahia.es" },
    });
    expect(screen.getByRole("button", { name: "Launch" }).disabled).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Launch" }));

    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("workgroup_launch_recipe", {
        profile: "mira",
        yaml: "hub: mira\nname: proj-{slug}\n",
        recipeId: "hotel",
        params: { slug: "casa-bahia" },
        briefing: "Hotel draft briefing",
        inputs: { brief: "Boutique hotel, 12 rooms, casabahia.es" },
        connectionId: "casa",
      });
    });
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("wg-9", "mira"));
  });

  it("Launch stays disabled until every declared param is filled", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "workgroup_pick_recipe") {
        return {
          yaml: "hub: mira\nname: n\n",
          recipe_id: "two",
          meta: {
            id: "two",
            hub: "mira",
            name: "n",
            params: { slug: { pattern: "^[a-z-]+$" }, tier: {} },
            inputs: {},
          },
        };
      }
      return null;
    });
    render(
      <CreateWorkgroupModal
        open
        profiles={[{ name: "mira", counts: { peers: 1 } }]}
        connectionId="casa"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Import recipe…" }));
    const slug = await screen.findByPlaceholderText("^[a-z-]+$");
    expect(screen.queryByRole("textbox", { name: /brief/i })).toBeNull();

    fireEvent.change(slug, { target: { value: "casa-bahia" } });
    expect(screen.getByRole("button", { name: "Launch" }).disabled).toBe(true);

    fireEvent.change(screen.getByPlaceholderText("value"), { target: { value: "pro" } });
    expect(screen.getByRole("button", { name: "Launch" }).disabled).toBe(false);
  });

  it("keeps manual form state when the profiles list refreshes in the background", () => {
    invoke.mockImplementation(async () => null);
    const { rerender } = render(
      <CreateWorkgroupModal
        open
        profiles={[{ name: "mira", counts: { peers: 1 } }]}
        connectionId="casa"
      />,
    );

    fireEvent.change(screen.getByPlaceholderText("team-alpha · roadmap · customers"), {
      target: { value: "Launch" },
    });
    fireEvent.click(screen.getByText("@peer-1"));
    expect(screen.getByRole("button", { name: "Create" }).disabled).toBe(false);

    rerender(
      <CreateWorkgroupModal
        open
        profiles={[{ name: "mira", counts: { peers: 1 } }]}
        connectionId="casa"
      />,
    );

    expect(screen.getByDisplayValue("Launch")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Create" }).disabled).toBe(false);
  });

  it("keeps an imported recipe when the profiles list refreshes in the background", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "workgroup_pick_recipe") return HOTEL_RECIPE;
      return null;
    });
    const { rerender } = render(
      <CreateWorkgroupModal
        open
        profiles={[{ name: "mira", counts: { peers: 1 } }]}
        connectionId="casa"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Import recipe…" }));
    await screen.findByText("HUB — FROM RECIPE");

    rerender(
      <CreateWorkgroupModal
        open
        profiles={[{ name: "mira", counts: { peers: 1 } }]}
        connectionId="casa"
      />,
    );

    expect(screen.getByText("HUB — FROM RECIPE")).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Import recipe…" })).toBeNull();
  });

  it("sends recipe input values verbatim (no trimming)", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "workgroup_pick_recipe") return HOTEL_RECIPE;
      if (cmd === "workgroup_launch_recipe") return { workgroup_id: "wg-9" };
      return null;
    });
    render(
      <CreateWorkgroupModal
        open
        profiles={[{ name: "mira", counts: { peers: 1 } }]}
        connectionId="casa"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Import recipe…" }));
    const slug = await screen.findByPlaceholderText("^[a-z-]+$");
    fireEvent.change(slug, { target: { value: "casa-bahia" } });
    const raw = "  leading + trailing \n";
    fireEvent.change(screen.getByPlaceholderText("paste the raw client brief"), {
      target: { value: raw },
    });
    fireEvent.click(screen.getByRole("button", { name: "Launch" }));

    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith(
        "workgroup_launch_recipe",
        expect.objectContaining({ inputs: { brief: raw } }),
      );
    });
  });

  it("an optional recipe input left empty does not block Launch and is omitted", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "workgroup_pick_recipe") {
        return {
          yaml: "hub: mira\nname: n\n",
          recipe_id: "opt",
          meta: {
            id: "opt",
            hub: "mira",
            name: "n",
            params: {},
            inputs: { notes: { label: "Notes", dest: "notes.md", required: false, placeholder: "optional notes" } },
            has_project: true,
          },
        };
      }
      if (cmd === "workgroup_launch_recipe") return { workgroup_id: "wg-x" };
      return null;
    });
    render(
      <CreateWorkgroupModal
        open
        profiles={[{ name: "mira", counts: { peers: 1 } }]}
        connectionId="casa"
      />,
    );

    fireEvent.click(screen.getByRole("button", { name: "Import recipe…" }));
    await screen.findByText("HUB — FROM RECIPE");
    expect(screen.getByRole("button", { name: "Launch" }).disabled).toBe(false);

    fireEvent.click(screen.getByRole("button", { name: "Launch" }));
    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith(
        "workgroup_launch_recipe",
        expect.objectContaining({ inputs: {} }),
      );
    });
  });
});

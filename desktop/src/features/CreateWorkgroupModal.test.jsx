import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
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
        connectionId: "casa",
      });
    });
  });

  it("offers no pipeline field on the manual path", () => {
    invoke.mockImplementation(async () => null);
    render(
      <CreateWorkgroupModal
        open
        profiles={[{ name: "mira", counts: { peers: 1 } }]}
        connectionId="casa"
      />,
    );

    expect(screen.queryByText(/pipeline/i)).toBeNull();
    expect(screen.queryByPlaceholderText("intake, content, build, qa")).toBeNull();
  });

  it("offers saved hub recipes and launches one by id without YAML", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "workgroup_saved_recipes") {
        return {
          recipes: [{
            id: "hotel",
            hub: "mira",
            name: "proj-{slug}",
            briefing: "Saved briefing",
            params: { slug: { pattern: "^[a-z-]+$" } },
            inputs: {},
            pipelines: {},
          }],
        };
      }
      if (cmd === "workgroup_launch_recipe") {
        return { workgroup_id: "wg-saved", queued: true, queue_position: 3 };
      }
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

    fireEvent.click(await screen.findByText("hotel"));
    fireEvent.change(screen.getByPlaceholderText("^[a-z-]+$"), {
      target: { value: "casa-bahia" },
    });
    expect(screen.getByRole("button", { name: "Import recipe…" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Launch" }));

    await waitFor(() => {
      expect(invoke).toHaveBeenCalledWith("workgroup_launch_recipe", {
        profile: "mira",
        yaml: null,
        recipeId: "hotel",
        params: { slug: "casa-bahia" },
        briefing: "Saved briefing",
        inputs: {},
        connectionId: "casa",
      });
    });
    expect(onCreated).toHaveBeenCalledWith("wg-saved", "mira");
    expect(notifyMock).toHaveBeenCalledWith({
      message: "Queued from recipe hotel · position 3",
      variant: "success",
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
    expect(screen.getByRole("button", { name: "Import recipe…" })).toBeInTheDocument();
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
    await screen.findByRole("button", { name: "Launch" });

    rerender(
      <CreateWorkgroupModal
        open
        profiles={[{ name: "mira", counts: { peers: 1 } }]}
        connectionId="casa"
      />,
    );

    expect(screen.getByRole("button", { name: "Launch" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Import recipe…" })).toBeInTheDocument();
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

  it("a recipe preview lists every pipeline in declared order and marks the launch one", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "workgroup_pick_recipe") {
        return {
          yaml: "hub: mira\nname: n\n",
          recipe_id: "hotel",
          meta: {
            id: "hotel",
            hub: "mira",
            name: "n",
            params: {},
            inputs: {},
            pipelines: { setup: ["setup", "enrich"], "media-update": ["media-update", "media-qa"] },
            launch_pipeline: "setup",
            pipeline_mode: true,
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

    expect(document.querySelector(".anim-dialog").style.width).toBe("var(--modal-md)");

    fireEvent.click(screen.getByRole("button", { name: "Import recipe…" }));
    await screen.findByText("PIPELINES");
    expect(document.querySelector(".anim-dialog").style.width).toBe("var(--modal-lg)");

    const phases = screen.getAllByText(/^#[a-z0-9-]+$/).map((el) => el.textContent);
    expect(phases).toEqual(["#setup", "#enrich", "#media-update", "#media-qa"]);
    expect(screen.getAllByText("2 phases")).toHaveLength(2);
    expect(screen.getAllByText("launch")).toHaveLength(1);
    expect(
      within(screen.getByText("setup").parentElement).getByText("launch"),
    ).toBeInTheDocument();
    expect(screen.getByText("media-update")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Launch" })).toBeInTheDocument();

    fireEvent.click(screen.getByRole("button", { name: /hotel/ }));
    expect(screen.getByRole("button", { name: "Import recipe…" })).toBeInTheDocument();
    expect(screen.queryByText("PIPELINES")).toBeNull();
    expect(document.querySelector(".anim-dialog").style.width).toBe("var(--modal-md)");
  });

  it("a launchless recipe previews as idle and creates instead of launching", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "workgroup_pick_recipe") {
        return {
          yaml: "hub: mira\nname: n\n",
          recipe_id: "idle",
          meta: {
            id: "idle",
            hub: "mira",
            name: "n",
            params: {},
            inputs: {},
            pipelines: { "media-update": ["media-update", "media-qa"] },
            launch_pipeline: null,
            pipeline_mode: true,
          },
        };
      }
      if (cmd === "workgroup_launch_recipe") return { workgroup_id: "wg-idle" };
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
    await screen.findByText("PIPELINES");
    expect(
      screen.getByText("No launch pipeline · created idle, every chain awaits a trigger"),
    ).toBeInTheDocument();
    expect(screen.getByText("#media-update")).toBeInTheDocument();
    expect(screen.getByText("#media-qa")).toBeInTheDocument();
    expect(screen.queryByText("launch")).toBeNull();
    expect(screen.queryByRole("button", { name: "Launch" })).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Create idle workgroup" }));
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("wg-idle", "mira"));
    expect(notifyMock).toHaveBeenCalledWith(
      expect.objectContaining({
        message: expect.stringContaining("Created idle from recipe idle"),
      }),
    );
  });

  it("a recipe with no pipelines launches and never claims to be idle", async () => {
    invoke.mockImplementation(async (cmd) => {
      if (cmd === "workgroup_pick_recipe") {
        return {
          yaml: "hub: mira\nname: n\n",
          recipe_id: "chat",
          meta: {
            id: "chat",
            hub: "mira",
            name: "n",
            params: {},
            inputs: {},
            pipelines: {},
            launch_pipeline: null,
            task: "@scout discuss the plan",
          },
        };
      }
      if (cmd === "workgroup_launch_recipe") return { workgroup_id: "wg-chat" };
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
    await screen.findByRole("button", { name: "Launch" });
    expect(screen.queryByText("PIPELINES")).toBeNull();

    fireEvent.click(screen.getByRole("button", { name: "Launch" }));
    await waitFor(() => expect(onCreated).toHaveBeenCalledWith("wg-chat", "mira"));
    expect(notifyMock).toHaveBeenCalledWith(
      expect.objectContaining({
        message: expect.stringContaining("Launched from recipe chat"),
      }),
    );
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
    await screen.findByRole("button", { name: "Launch" });
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

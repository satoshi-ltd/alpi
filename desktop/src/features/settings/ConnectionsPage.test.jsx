import { fireEvent, render, screen, waitFor } from "@testing-library/react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import ConnectionsPage from "./ConnectionsPage.jsx";
import styles from "./ConnectionsPage.module.css";

const invoke = vi.fn();
vi.mock("@tauri-apps/api/core", () => ({ invoke: (...args) => invoke(...args) }));
vi.mock("../../primitives/Notification.jsx", () => ({
  useNotify: () => vi.fn(),
}));

const summary = {
  totals: { paired: 1, connected: 1, sessions: 4, cost_14d: 0.42 },
  connections: [{
    id: "conn_javi",
    label: "Javi",
    status: "active",
    role: "member",
    profile_scope: ["atlas"],
    last_seen: Math.floor(Date.now() / 1000),
    sessions: 4,
    cost_14d: 0.42,
    usage_days: [{ iso: "2026-07-14", tokIn: 100, tokOut: 20, cost: 0.42 }],
    devices: [{ id: "dev_phone", name: "iPhone", client: "mobile", app_version: "0.2", last_seen: Math.floor(Date.now() / 1000) }],
  }],
};

describe("ConnectionsPage", () => {
  beforeEach(() => {
    invoke.mockReset();
    invoke.mockImplementation((command) => command === "connections_summary" ? Promise.resolve(summary) : Promise.resolve({ ok: true }));
  });

  it("renders the aggregate table and expands usage and devices", async () => {
    const { container } = render(<ConnectionsPage profiles={[{ name: "atlas" }]} activeConnection={{ id: "local" }} />);

    expect(await screen.findByText("Javi")).toBeInTheDocument();
    expect(container.querySelector(".ds-chat-header")).toBeInTheDocument();
    expect(screen.queryByText("pairing endpoint")).toBeNull();
    expect(screen.getByText("4", { selector: "strong" })).toBeInTheDocument();
    expect(screen.getByText("SESSIONS")).toBeInTheDocument();
    fireEvent.click(screen.getByText("Javi"));

    expect(await screen.findByText("iPhone")).toBeInTheDocument();
    expect(screen.getByText("14-day total $0.42 · 100 in / 20 out")).toBeInTheDocument();
  });

  it("shows pairing name and port only inside the local host detail", async () => {
    invoke.mockImplementation((command) => command === "connections_summary" ? Promise.resolve({
      ...summary,
      connections: [{
        id: "host",
        label: "Host",
        status: "active",
        role: "admin",
        last_seen: Math.floor(Date.now() / 1000),
        sessions: 2,
        cost_14d: 0.1,
        usage_days: [],
        devices: [],
      }],
    }) : Promise.resolve({ ok: true }));
    const profiles = [{ name: "default", advertise_host: "" }];
    const { rerender } = render(
      <ConnectionsPage profiles={profiles} activeConnection={{ id: "local", kind: "local" }} />,
    );

    fireEvent.click(await screen.findByText("Local host", { selector: "strong" }));
    expect(await screen.findByText("pairing name")).toBeInTheDocument();
    expect(screen.getByText("pairing port")).toBeInTheDocument();

    rerender(
      <ConnectionsPage profiles={profiles} activeConnection={{ id: "remote", kind: "remote", role: "admin" }} />,
    );
    await waitFor(() => expect(screen.queryByText("pairing name")).toBeNull());
    expect(screen.queryByText("pairing port")).toBeNull();
  });

  it("adds another device to the existing connection", async () => {
    invoke.mockImplementation((command) => {
      if (command === "connections_summary") return Promise.resolve(summary);
      if (command === "connections_add_device") return Promise.resolve({
        label: "Javi", pairing_name: "Atlas daemon", host: "100.64.0.1", port: 49200, token: "token",
      });
      return Promise.resolve({ ok: true });
    });
    render(<ConnectionsPage profiles={[]} activeConnection={{ id: "local" }} />);
    fireEvent.click(await screen.findByText("Javi"));
    fireEvent.click(screen.getByText("Add device"));

    await waitFor(() => expect(invoke).toHaveBeenCalledWith("connections_add_device", {
      targetId: "conn_javi", connectionId: "local",
    }));
    expect(await screen.findByText("Pair a device with Javi")).toBeInTheDocument();
    expect(screen.getByText(/alpi:\/\/device/).textContent).toContain("name=Atlas+daemon");
  });

  it("confirms before revoking one device", async () => {
    render(<ConnectionsPage profiles={[]} activeConnection={{ id: "local" }} />);
    fireEvent.click(await screen.findByText("Javi"));
    fireEvent.click(screen.getByText("Revoke"));

    expect(screen.getByText("Revoke iPhone?")).toBeInTheDocument();
    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(invoke).not.toHaveBeenCalledWith("connections_revoke_device", expect.anything());
    fireEvent.click(screen.getByText("Revoke device"));

    await waitFor(() => expect(invoke).toHaveBeenCalledWith("connections_revoke_device", {
      targetId: "conn_javi",
      deviceId: "dev_phone",
      connectionId: "local",
    }));
  });

  it("updates a connection from selected profiles to all profiles", async () => {
    render(<ConnectionsPage profiles={[{ name: "atlas" }]} activeConnection={{ id: "local" }} />);
    await screen.findByText("Javi");
    expect(screen.queryByRole("checkbox", { name: "All profiles" })).toBeNull();
    fireEvent.click(screen.getByRole("button", { name: "Edit connection" }));
    fireEvent.click(screen.getByRole("checkbox", { name: "All profiles" }));
    fireEvent.click(screen.getByText("Save changes"));

    await waitFor(() => expect(invoke).toHaveBeenCalledWith("connections_update", {
      targetId: "conn_javi",
      label: "Javi",
      role: "member",
      profiles: [],
      connectionId: "local",
    }));
  });

  it("keeps row actions outside the expanded panel and dims other rows", async () => {
    invoke.mockImplementation((command) => command === "connections_summary" ? Promise.resolve({
      ...summary,
      connections: [
        ...summary.connections,
        { ...summary.connections[0], id: "conn_other", label: "Other" },
      ],
    }) : Promise.resolve({ ok: true }));
    render(<ConnectionsPage profiles={[]} activeConnection={{ id: "local" }} />);

    await screen.findByText("Javi");
    expect(screen.getAllByRole("button", { name: "Edit connection" })).toHaveLength(2);
    fireEvent.click(screen.getByText("Javi"));

    expect(screen.getByText("Other").closest(`.${styles.group}`)).toHaveClass(styles.mutedGroup);
    expect(screen.getByText("Javi").closest(`.${styles.group}`)).toHaveClass(styles.activeGroup);
  });

  it("marks only disabled connections and tones down their row", async () => {
    invoke.mockImplementation((command) => command === "connections_summary" ? Promise.resolve({
      ...summary,
      connections: [{ ...summary.connections[0], status: "disabled" }],
    }) : Promise.resolve({ ok: true }));
    render(<ConnectionsPage profiles={[]} activeConnection={{ id: "local" }} />);

    const disabled = await screen.findByText("disabled");
    expect(disabled).toBeInTheDocument();
    expect(screen.getByText("Javi").closest(`.${styles.row}`)).toHaveClass(styles.disabledRow);
    expect(screen.queryByText("active")).toBeNull();
  });

  it("sorts by activity and searches connection and device metadata", async () => {
    invoke.mockImplementation((command) => command === "connections_summary" ? Promise.resolve({
      ...summary,
      connections: [
        { ...summary.connections[0], last_seen: 10 },
        {
          ...summary.connections[0],
          id: "conn_recent",
          label: "Recent",
          last_seen: 20,
          devices: [{ ...summary.connections[0].devices[0], id: "dev_mac", name: "Studio Mac" }],
        },
      ],
    }) : Promise.resolve({ ok: true }));
    const { container } = render(<ConnectionsPage profiles={[]} activeConnection={{ id: "local" }} />);

    await screen.findByText("Recent");
    expect([...container.querySelectorAll(`.${styles.identity} strong`)].map((node) => node.textContent)).toEqual([
      "Recent",
      "Javi",
    ]);

    fireEvent.change(screen.getByRole("searchbox", { name: "Search connections" }), {
      target: { value: "Studio Mac" },
    });

    expect(screen.getByText("Recent")).toBeInTheDocument();
    expect(screen.queryByText("Javi")).toBeNull();
    expect(screen.getByText("1 of 2")).toBeInTheDocument();
  });

  it("confirms before disabling and enables directly", async () => {
    const disabledSummary = {
      ...summary,
      connections: [{ ...summary.connections[0], status: "disabled" }],
    };
    let currentSummary = summary;
    invoke.mockImplementation((command, args) => {
      if (command === "connections_summary") return Promise.resolve(currentSummary);
      if (command === "connections_set_status") {
        currentSummary = args.status === "disabled" ? disabledSummary : summary;
      }
      return Promise.resolve({ ok: true });
    });
    render(<ConnectionsPage profiles={[]} activeConnection={{ id: "local" }} />);

    fireEvent.click(await screen.findByRole("button", { name: "Disable connection" }));
    expect(screen.getByText("Disable Javi?")).toBeInTheDocument();
    expect(invoke).not.toHaveBeenCalledWith("connections_set_status", expect.anything());
    fireEvent.click(screen.getByText("Cancel"));
    expect(invoke).not.toHaveBeenCalledWith("connections_set_status", expect.anything());

    fireEvent.click(screen.getByRole("button", { name: "Disable connection" }));
    fireEvent.click(screen.getAllByRole("button", { name: "Disable connection" }).at(-1));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("connections_set_status", {
      targetId: "conn_javi",
      status: "disabled",
      connectionId: "local",
    }));

    await screen.findByText("disabled");
    fireEvent.click(screen.getByRole("button", { name: "Enable connection" }));
    await waitFor(() => expect(invoke).toHaveBeenCalledWith("connections_set_status", {
      targetId: "conn_javi",
      status: "active",
      connectionId: "local",
    }));
  });

  it("presents the internal default profile as alpi in the hero title", async () => {
    render(<ConnectionsPage profiles={[{ name: "default", accent: "#abc123" }]} activeConnection={{ id: "local" }} />);
    expect(await screen.findByText("alpi", { selector: "h1" })).toBeInTheDocument();
  });

  it("reuses the existing device pairing modal for a new connection", async () => {
    render(<ConnectionsPage profiles={[]} activeConnection={{ id: "local" }} />);

    fireEvent.click(await screen.findByText("New connection"));

    expect(screen.getByText("Pair a new device")).toBeInTheDocument();
    expect(screen.getByText("Grant admin access")).toBeInTheDocument();
    expect(screen.getByText("Generate pairing code")).toBeInTheDocument();
    expect(screen.queryByText("Create connection")).toBeNull();
  });
});

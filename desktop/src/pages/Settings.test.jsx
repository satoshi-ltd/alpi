import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Settings, { canOpenConnections } from "./Settings.jsx";

describe("Settings", () => {
  it("shows a progress bar while the selected target is waiting for remote summaries", () => {
    render(
      <Settings
        profiles={[]}
        workgroups={[]}
        target={{ kind: "profile", id: "doc" }}
        activeConnection={{ id: "remote", accent: "#57a" }}
        connectionSyncing
      />,
    );

    expect(screen.getByRole("progressbar", { name: "Fetching latest settings" })).toBeInTheDocument();
    expect(screen.getByText("Fetching latest settings…")).toBeInTheDocument();
  });

  it("does not open connection administration for a member credential", () => {
    render(
      <Settings
        profiles={[]}
        target={{ kind: "connections" }}
        activeConnection={{ id: "remote", kind: "remote", role: "member" }}
      />,
    );

    expect(screen.getByText("Admin access required")).toBeInTheDocument();
  });

  it("offers connection administration only from the default profile", () => {
    const admin = { kind: "remote", role: "admin" };

    expect(canOpenConnections(admin, "default")).toBe(true);
    expect(canOpenConnections(admin, "atlas")).toBe(false);
    expect(canOpenConnections({ kind: "remote", role: "member" }, "default")).toBe(false);
  });
});

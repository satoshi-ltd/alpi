import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import Settings from "./Settings.jsx";

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
});

import { describe, it, expect, vi } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";

import ChatHeader from "./ChatHeader.jsx";
import SettingsHero from "./SettingsHero.jsx";
import { SidebarContext } from "../lib/sidebar.js";

function withSidebar(open, toggle, node) {
  return render(<SidebarContext.Provider value={{ open, toggle }}>{node}</SidebarContext.Provider>);
}

describe("headers with a hidden sidebar", () => {
  it("chat header offers the only way back to the roster when the sidebar is hidden", () => {
    const toggle = vi.fn();
    withSidebar(false, toggle, <ChatHeader kind="profile" id="doc" accent="#3d7ea6" />);
    fireEvent.click(screen.getByRole("button", { name: "Show sidebar" }));
    expect(toggle).toHaveBeenCalledTimes(1);
  });

  it("settings hero does the same", () => {
    const toggle = vi.fn();
    withSidebar(false, toggle, <SettingsHero kind="profile" id="doc" accent="#3d7ea6" />);
    fireEvent.click(screen.getByRole("button", { name: "Show sidebar" }));
    expect(toggle).toHaveBeenCalledTimes(1);
  });

  it("stays out of the way while the sidebar is visible", () => {
    withSidebar(true, () => {}, <ChatHeader kind="profile" id="doc" accent="#3d7ea6" />);
    expect(screen.queryByRole("button", { name: "Show sidebar" })).toBeNull();
  });
});

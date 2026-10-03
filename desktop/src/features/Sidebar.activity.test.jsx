import { describe, it, expect, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { readFileSync } from "node:fs";
import { join } from "node:path";
import { ICON_ROLES } from "../../../common/iconRoles.mjs";

globalThis.ResizeObserver ??= class { observe() {} unobserve() {} disconnect() {} };
window.matchMedia ??= () => ({
  matches: false,
  addEventListener() {},
  removeEventListener() {},
  addListener() {},
  removeListener() {},
});

vi.mock("../lib/updater.js", () => ({
  describeUpdaterError: () => "",
  quitForUpdate: vi.fn(),
  applyPendingUpdate: vi.fn(),
  checkForUpdates: vi.fn(),
  subscribeUpdater: vi.fn(() => () => {}),
}));

import Sidebar from "./Sidebar.jsx";

const TS = Math.floor(Date.now() / 1000) - 300;

const BASE = {
  profiles: [
    { name: "alpi", model: "a/b", latest_session: { updated_at: TS } },
    { name: "builder", model: "a/b", latest_session: { updated_at: TS } },
    { name: "doc", model: "a/b", latest_session: { updated_at: TS } },
    { name: "abby", model: "a/b", latest_session: { updated_at: TS } },
  ],
  workgroups: [{ profile: "alpi", id: "crew", name: "launch-crew", mtime: TS }],
  view: { kind: "landing" },
  hostConnections: { active_id: "local", connections: [] },
};

const rosterState = {
  profiles: { alpi: "working", builder: "needs-you", doc: "failed" },
  workgroups: { "alpi/crew": { state: "working", phasesDone: 2, phasesTotal: 4, phase: "analyze" } },
};

describe("Sidebar agent states", () => {
  it("shows needs you, failed and working chips and leaves idle rows alone", () => {
    render(<Sidebar {...BASE} rosterState={rosterState} />);
    expect(screen.getByRole("button", { name: "builder, needs you" })).toHaveTextContent("needs you");
    expect(screen.getByRole("button", { name: "doc, failed" })).toHaveTextContent("failed");
    const alpi = screen.getByRole("button", { name: "alpi, working" });
    expect(alpi.querySelector("polygon[class*='cell']")).not.toBeNull();
    expect(alpi.querySelector("[data-state='working'] span")).toBeNull();
    const abby = screen.getByText("abby").closest("button");
    expect(abby.querySelector("[data-state]")).toBeNull();
    expect(abby.querySelector(".sb-ts")).not.toBeNull();
  });

  it("shows phases done over total on a running workgroup", () => {
    render(<Sidebar {...BASE} rosterState={rosterState} />);
    expect(screen.getByLabelText("phase 2 of 4")).toHaveTextContent("2/4");
  });

  it("renders the old timestamps when the daemon has no activity verb", () => {
    render(<Sidebar {...BASE} rosterState={null} />);
    expect(screen.queryByText("needs you")).toBeNull();
    expect(screen.queryByText("2/4")).toBeNull();
  });

  it("offers the Activity button with a needs-you badge only when wired", () => {
    const onOpenActivity = vi.fn();
    const { rerender } = render(<Sidebar {...BASE} onOpenActivity={onOpenActivity} activityNeedsYou={2} />);
    fireEvent.click(screen.getByRole("button", { name: "Activity · 2 need you · ⌘J" }));
    expect(onOpenActivity).toHaveBeenCalledTimes(1);
    rerender(<Sidebar {...BASE} onOpenActivity={null} />);
    expect(screen.queryByRole("button", { name: /^Activity/ })).toBeNull();
  });
});

describe("Sidebar footer fit", () => {
  const read = (rel) => readFileSync(join(import.meta.dirname, rel), "utf8");
  const mountFooter = () => {
    render(<Sidebar {...BASE} onOpenNotifications={() => {}} onOpenActivity={() => {}} onOpenSettings={() => {}} />);
    const settings = screen.getByRole("button", { name: "Settings" });
    return { settings, footer: settings.closest("div[class*='footer']") };
  };

  it("keeps all five items in order, with the Settings label visible", () => {
    const { footer } = mountFooter();
    const buttons = [...footer.querySelectorAll("button")].map((b) => b.getAttribute("aria-label") ?? b.textContent);
    expect(buttons[0]).toBe("Settings");
    expect(buttons[1]).toMatch(/^Notifications/);
    expect(buttons[2]).toMatch(/^Activity/);
    expect(buttons[3]).toMatch(/^Theme/);
    expect(buttons[4]).toMatch(/^v?\d|^v/);
    expect(footer.textContent).toContain("Settings");
  });

  it("draws Settings with its label and bell, activity and theme as 22 px sm icon buttons", () => {
    const { settings } = mountFooter();
    const four = [settings, ...[/^Notifications/, /^Activity/, /^Theme/].map((name) => screen.getByRole("button", { name }))];
    for (const btn of four) {
      expect(btn.className).toMatch(/_sm_|\bsm\b/);
      expect(btn.querySelector("svg").getAttribute("width")).toBe("14");
    }
    expect(read("Sidebar.module.css")).toMatch(/\.footer :global\(\.ds-tip\) \.footerIcon \{\s*width: var\(--ctrl-xs\);/);
  });

  it("keeps the ink colour but not the tight padding on the settings-mode Command button", () => {
    render(<Sidebar {...BASE} view={{ kind: "settings" }} onOpenPalette={() => {}} />);
    const command = screen.getByText("Command…").closest("button");
    expect(command.className).toMatch(/footerButton/);
    expect(command.className).not.toMatch(/footerTight/);
    const css = read("Sidebar.module.css");
    expect(css).toMatch(/\.footerButton \{[^}]*color: var\(--ink\)/);
    expect(css).toMatch(/\.footer :global\(\.ds-tip\) \.footerTight \{\s*padding: 0 var\(--space-1\) 0 var\(--space-4\);/);
    expect(css).not.toMatch(/\.ds-tip\) \.footerButton/);
  });

  it("draws settings, notifications and Activity from the shared role map and never lets the version clip", () => {
    const { settings } = mountFooter();
    const glyph = (btn) => btn.querySelector("svg").getAttribute("data-icon");
    expect(glyph(settings)).toBe(ICON_ROLES.settings);
    expect(glyph(screen.getByRole("button", { name: /^Notifications/ }))).toBe(ICON_ROLES.notifications);
    expect(glyph(screen.getByRole("button", { name: /^Activity/ }))).toBe(ICON_ROLES.activity);
    const version = read("VersionButton.module.css");
    expect(version).toMatch(/\.root \{[^}]*flex-shrink: 0/);
    expect(version).toMatch(/\.trigger \{[^}]*font-size: var\(--text-meta\)[^}]*padding: 2px 4px[^}]*color: var\(--ink-3\)/);
  });
});

describe("Sidebar footer badges", () => {
  const read = (rel) => readFileSync(join(import.meta.dirname, rel), "utf8");

  it("draws the unread and needs-you counts with one danger badge, pinned to the glyph", () => {
    render(
      <Sidebar
        {...BASE}
        onOpenNotifications={() => {}}
        notificationsUnread={3}
        onOpenActivity={() => {}}
        activityNeedsYou={2}
        onOpenSettings={() => {}}
      />,
    );
    const badges = [/^Notifications · 3 unread/, /^Activity · 2 need you/].map((name) => {
      const btn = screen.getByRole("button", { name });
      const svg = btn.querySelector("svg");
      const wrap = svg.parentElement;
      const badge = wrap.querySelector("span[aria-hidden]");
      expect(badge).not.toBeNull();
      expect([...wrap.children].filter((el) => el !== badge)).toEqual([svg]);
      return badge;
    });
    expect(badges[0].textContent).toBe("3");
    expect(badges[1].textContent).toBe("2");
    expect(badges[0].className).toBe(badges[1].className);
  });

  it("caps both counts at 9+ and keeps the exact number in the label", () => {
    render(
      <Sidebar
        {...BASE}
        onOpenNotifications={() => {}}
        notificationsUnread={12}
        onOpenActivity={() => {}}
        activityNeedsYou={250}
        onOpenSettings={() => {}}
      />,
    );
    const bell = screen.getByRole("button", { name: /^Notifications · 12 unread/ });
    const activity = screen.getByRole("button", { name: /^Activity · 250 need you/ });
    expect(bell.querySelector("span[aria-hidden]").textContent).toBe("9+");
    expect(activity.querySelector("span[aria-hidden]").textContent).toBe("9+");
  });

  it("pins the badge's right edge 4 px past the glyph so it never reaches the next icon, with no warning variant", () => {
    const css = read("Sidebar.module.css");
    expect(css).not.toMatch(/needsBadge/);
    expect(css).toMatch(/\.bellWrap \{\s*position: relative;\s*display: inline-flex;\s*\}/);
    const badge = css.match(/\.bellBadge \{([^}]+)\}/)[1];
    expect(badge).toMatch(/background: var\(--c-danger\)/);
    expect(badge).toMatch(/top: calc\(var\(--space-6\) \/ -2 - var\(--space-1\) \/ 2\);\s*right: calc\(var\(--space-1\) \* -1\);/);
    expect(badge).not.toMatch(/left:|transform:/);
  });
});

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
import { ThemeField } from "./settings/fields/ThemeField.jsx";
import { getTheme, setTheme } from "../lib/theme.js";

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

  it("offers the Activity button with a needs-you dot only when wired", () => {
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
    expect(buttons[3]).toMatch(/^Theme: /);
    expect(buttons[4]).toMatch(/^v?\d|^v/);
    expect(buttons).toHaveLength(5);
    expect(footer.textContent).toContain("Settings");
  });

  it("draws Settings with its label and bell and activity as sm icon buttons with 24 px targets", () => {
    const { settings } = mountFooter();
    const four = [settings, ...[/^Notifications/, /^Activity/, /^Theme/].map((name) => screen.getByRole("button", { name }))];
    for (const btn of four) {
      expect(btn.className).toMatch(/_sm_|\bsm\b/);
      expect(btn.querySelector("svg").getAttribute("width")).toBe("14");
    }
    expect(read("Sidebar.module.css")).toMatch(/\.footer :global\(\.ds-tip\) \.footerIcon \{\s*width: var\(--ctl-24\);/);
  });

  it("keeps one footer variant in settings mode, with the theme button and no palette button", () => {
    render(<Sidebar {...BASE} view={{ kind: "settings" }} onOpenSettings={() => {}} onOpenNotifications={() => {}} onOpenActivity={() => {}} />);
    const settings = screen.getByRole("button", { name: "Settings" });
    expect(settings).toHaveAttribute("aria-current", "page");
    expect(settings.textContent).toBe("");
    expect(screen.queryByText("Command…")).toBeNull();
    expect(screen.getByRole("button", { name: /^Theme/ })).toBeInTheDocument();
    const css = read("Sidebar.module.css");
    expect(css).toMatch(/\.footerButton \{[^}]*color: var\(--ink\)/);
    expect(css).not.toMatch(/footerSettings/);
  });

  it("draws settings, notifications and Activity from the shared role map and never lets the version clip", () => {
    const { settings } = mountFooter();
    const glyph = (btn) => btn.querySelector("svg").getAttribute("data-icon");
    expect(glyph(settings)).toBe(ICON_ROLES.settings);
    expect(glyph(screen.getByRole("button", { name: /^Notifications/ }))).toBe(ICON_ROLES.notifications);
    expect(glyph(screen.getByRole("button", { name: /^Activity/ }))).toBe(ICON_ROLES.activity);
    const version = read("VersionButton.module.css");
    expect(version).toMatch(/\.root \{[^}]*flex-shrink: 0/);
    expect(version).toMatch(/\.trigger \{[^}]*font-size: var\(--text-meta\)[^}]*padding: 0 calc\(\(var\(--ctl-24\) - var\(--icon-sm\)\) \/ 2\) 0 0[^}]*color: var\(--ink-3\)/);
  });
});

describe("Sidebar footer width", () => {
  const css = readFileSync(join(import.meta.dirname, "Sidebar.module.css"), "utf8");

  it("fits the 248 px column: tight gaps, no spacer element, the version pushed right by its own margin", () => {
    expect(css).toMatch(/\.footer \{[^}]*padding: var\(--sp-12\) calc\(var\(--sp-12\) \+ var\(--space-tight\)\)[^}]*gap: var\(--sp-4\)/);
    expect(css).toMatch(/\.footer > :last-child \{\s*flex: 1 1 0;/);
    expect(css).not.toMatch(/footerSpacer/);
  });

  it("draws Settings as an icon only, with its name and tooltip kept", () => {
    expect(css).not.toMatch(/footerTight|footerLabel/);
    render(<Sidebar {...BASE} onOpenSettings={() => {}} />);
    const settings = screen.getByRole("button", { name: "Settings" });
    expect(settings.textContent).toBe("");
    expect(settings.className).toMatch(/footerIcon/);
  });

  it("insets Settings and the version by the same 19 px of ink", () => {
    const version = readFileSync(join(import.meta.dirname, "VersionButton.module.css"), "utf8");
    expect(css).toMatch(/\.footerIcon \{\s*width: var\(--ctl-24\);\s*height: var\(--ctl-24\);/);
    expect(version.match(/\.trigger \{([^}]+)\}/)[1]).toMatch(/padding: 0 calc\(\(var\(--ctl-24\) - var\(--icon-sm\)\) \/ 2\) 0 0;/);
  });

  it("keeps the right padding at least 12 px so the version clears the edge", () => {
    expect(css.match(/\.footer \{([^}]+)\}/)[1]).toMatch(/padding: var\(--sp-12\) calc\(var\(--sp-12\) \+ var\(--space-tight\)\);/);
  });
});

describe("Sidebar footer badges", () => {
  const read = (rel) => readFileSync(join(import.meta.dirname, rel), "utf8");

  it("draws unread and needs-you as the same bare dot, pinned to the glyph", () => {
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
    const [dot, activityDot] = [/^Notifications · 3 unread/, /^Activity · 2 need you/].map((name) => {
      const btn = screen.getByRole("button", { name });
      const svg = btn.querySelector("svg");
      const wrap = svg.parentElement;
      const mark = wrap.querySelector("span[aria-hidden]");
      expect(mark).not.toBeNull();
      expect([...wrap.children].filter((el) => el !== mark)).toEqual([svg]);
      return mark;
    });
    expect(dot.textContent).toBe("");
    expect(dot.children).toHaveLength(0);
    expect(dot.getAttribute("aria-hidden")).toBe("true");
    expect(dot.className).toMatch(/bellDot/);
    expect(activityDot.textContent).toBe("");
    expect(activityDot.children).toHaveLength(0);
    expect(activityDot.getAttribute("aria-hidden")).toBe("true");
    expect(activityDot.className).toBe(dot.className);
  });

  it("shows no dot at zero unread or zero needs-you", () => {
    render(<Sidebar {...BASE} onOpenNotifications={() => {}} notificationsUnread={0} onOpenActivity={() => {}} activityNeedsYou={0} onOpenSettings={() => {}} />);
    const btn = screen.getByRole("button", { name: /^Notifications · / });
    expect(btn.querySelector("span[aria-hidden]")).toBeNull();
    expect(btn.getAttribute("aria-label")).not.toMatch(/unread/);
    const activity = screen.getByRole("button", { name: /^Activity · / });
    expect(activity.querySelector("span[aria-hidden]")).toBeNull();
    expect(activity.getAttribute("aria-label")).not.toMatch(/need you/);
  });

  it("keeps the exact count in both labels and draws no digits", () => {
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
    expect(bell.querySelector("span[aria-hidden]").textContent).toBe("");
    expect(activity.querySelector("span[aria-hidden]").textContent).toBe("");
  });

  it("anchors the dot on the glyph's top-right corner with dot tokens, flat", () => {
    const css = read("Sidebar.module.css");
    expect(css).not.toMatch(/needsBadge/);
    expect(css).toMatch(/\.bellWrap \{\s*position: relative;\s*display: inline-flex;\s*\}/);
    const dot = css.match(/\.bellDot \{([^}]+)\}/)[1];
    expect(dot).toMatch(/background: var\(--c-danger\)/);
    expect(dot).toMatch(/width: var\(--dot-md\);\s*height: var\(--dot-md\);/);
    expect(dot).toMatch(/top: 0;\s*right: 0;/);
    expect(dot).toMatch(/pointer-events: none/);
    expect(dot).not.toMatch(/box-shadow|border:|gradient|left:/);
    expect(css).not.toMatch(/bellBadge/);
  });

  it("draws every status in one sans style and never lets a visible status truncate its label", () => {
    const row = read("../primitives/SidebarRow.module.css");
    expect(row).toMatch(/\.stateWord \{[^}]*margin-left: auto;[^}]*font-family: var\(--font-sans\)/);
    expect(row).toMatch(/\.label\.labelKeep \{\s*flex: 0 0 auto;/);
    expect(read("../primitives/SidebarRow.jsx")).toMatch(/STATE_WORD\[state\] \? styles\.labelKeep/);
    expect(read("Sidebar.module.css")).toMatch(/:global\(\.ds-sb-row\):has\(\.stateChip\) :global\(\.sb-name\) \{\s*flex-shrink: 0;/);
  });
});

describe("Sidebar theme button", () => {
  const mount = () => render(<Sidebar {...BASE} onOpenSettings={() => {}} />);

  it("labels each preference, cycles system to light to dark and applies it", () => {
    setTheme("system");
    mount();
    fireEvent.click(screen.getByRole("button", { name: "Theme: System" }));
    expect(getTheme()).toBe("light");
    expect(document.documentElement.getAttribute("data-mode")).toBe("light");
    const light = screen.getByRole("button", { name: "Theme: Light" });
    expect(light.querySelector("svg").getAttribute("data-icon")).toBe("sun");
    fireEvent.click(light);
    expect(getTheme()).toBe("dark");
    expect(document.documentElement.getAttribute("data-mode")).toBe("dark");
    const dark = screen.getByRole("button", { name: "Theme: Dark" });
    expect(dark.querySelector("svg").getAttribute("data-icon")).toBe("moon");
    fireEvent.click(dark);
    expect(getTheme()).toBe("system");
    expect(document.documentElement.hasAttribute("data-mode")).toBe(false);
    expect(screen.getByRole("button", { name: "Theme: System" }).querySelector("svg").getAttribute("data-icon")).toBe("sun-moon");
  });

  it("stays in sync with the settings theme field", () => {
    setTheme("system");
    mount();
    render(<ThemeField />);
    fireEvent.click(screen.getByRole("button", { name: "Dark" }));
    expect(screen.getByRole("button", { name: "Theme: Dark" })).toBeInTheDocument();
    fireEvent.click(screen.getByRole("button", { name: "Theme: Dark" }));
    expect(screen.getByRole("button", { name: "System" })).toHaveAttribute("aria-pressed", "true");
  });
});

// @vitest-environment node
import { existsSync, readFileSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";
import config from "../../vite.config.js";

const ROOT = join(import.meta.dirname, "..", "..");
const read = (rel) => readFileSync(join(ROOT, rel), "utf8");
const capabilities = Object.fromEntries(
  readdirSync(join(ROOT, "src-tauri", "capabilities"))
    .filter((f) => f.endsWith(".json"))
    .map((f) => [f, JSON.parse(read(`src-tauri/capabilities/${f}`))]),
);
const COMMANDS = ["tray_announce_state", "tray_state", "resize_tray", "hide_tray", "show_main", "open_settings", "open_notifications", "restart_to_update", "quit_app", "start_alpi"];

describe("the tray entry", () => {
  it("is a second Vite page next to the main one", async () => {
    const { build } = await config({});
    expect(Object.keys(build.rollupOptions.input).sort()).toEqual(["main", "tray"]);
    expect(build.rollupOptions.input.tray.endsWith("tray.html")).toBe(true);
    expect(build.rollupOptions.input.main.endsWith("index.html")).toBe(true);
  });

  it("has a page that mounts the tray tree and nothing of the main app", () => {
    expect(existsSync(join(ROOT, "tray.html"))).toBe(true);
    expect(read("tray.html")).toContain('src="/src/tray/main.jsx"');
    const entry = read("src/tray/main.jsx");
    expect(entry).toContain("TrayApp");
    expect(entry).not.toMatch(/["']\.{1,2}\/App\.jsx|bootstrap|NotificationProvider/);
  });
});

describe("the tray capability", () => {
  const tray = capabilities["tray.json"];

  it("covers the tray window alone and only listens to events", () => {
    expect(tray.windows).toEqual(["tray"]);
    expect(tray.permissions).toEqual(["core:event:allow-listen", "core:event:allow-unlisten"]);
  });

  it("is not part of the main window's grant, and the main window's is not the tray's", () => {
    for (const [file, cap] of Object.entries(capabilities)) {
      if (file !== "tray.json") expect(cap.windows).not.toContain("tray");
    }
    expect(capabilities["default.json"].windows).toEqual(["main"]);
  });

  it("grants no window, webview, shell, fs or opener power", () => {
    expect(tray.permissions.every((p) => p.startsWith("core:event:"))).toBe(true);
  });
});

describe("the tray window", () => {
  const popover = read("src-tauri/src/tray_popover.rs");
  const lib = read("src-tauri/src/lib.rs");

  it("is created hidden, undecorated, fixed, on top and out of the taskbar", () => {
    for (const call of ['"tray.html"', ".transparent(true)", ".decorations(false)", ".resizable(false)", ".visible(false)", ".always_on_top(true)", ".skip_taskbar(true)"]) {
      expect(popover).toContain(call);
    }
  });

  it("registers every command the popover calls", () => {
    for (const name of COMMANDS) {
      expect(popover).toMatch(new RegExp(`pub (async )?fn ${name}\\b`));
      expect(lib).toContain(`tray_popover::${name}`);
    }
  });

  it("keeps the window-state plugin from restoring the popover as a visible window", () => {
    expect(lib).toMatch(/with_denylist\(&\[tray_popover::LABEL\]\)/);
  });

  it("needs the private macOS API on both sides, which tauri-build checks", () => {
    expect(read("src-tauri/Cargo.toml")).toMatch(/tauri = \{[^}]*"macos-private-api"/);
    expect(JSON.parse(read("src-tauri/tauri.conf.json")).app.macOSPrivateApi).toBe(true);
  });

  it("shows the native menu on a left click only where the tray sends no click event", () => {
    expect(read("src-tauri/src/tray.rs")).toContain('.show_menu_on_left_click(cfg!(target_os = "linux"))');
  });

  it("leaves the main window's focus handler to the main window", () => {
    expect(lib).toMatch(/if window\.label\(\) == tray_popover::LABEL \{\s*tray_popover::on_window_event\(window, event\);\s*return;/);
  });
});

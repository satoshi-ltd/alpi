import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const read = (file) => readFileSync(join(import.meta.dirname, "..", file), "utf8");
const settingsSources = [
  "features/settings/ProfileDetail.jsx",
  "features/settings/WorkgroupDetail.jsx",
  "features/settings/fields/McpField.jsx",
  "features/settings/fields/devices.jsx",
  "features/settings/fields/EmailCell.jsx",
  "features/settings/fields/PeersField.jsx",
  "primitives/PeerPopover.jsx",
];

describe("settings rows", () => {
  const css = read("primitives/SettingsLayout.module.css");

  it("pitches rows at 56 with the label and its description left and the control right, parted by space, never a rule", () => {
    expect(css).toMatch(/\.fieldRow \{[^}]*min-height: 56px;/);
    expect(css).toMatch(/\.fieldLabel \{[^}]*font-size: var\(--text-ui\);[^}]*font-weight: var\(--fw-medium\);/);
    expect(css).toMatch(/\.fieldHelper \{[^}]*font-family: var\(--font-sans\);[^}]*font-size: var\(--text-small\);[^}]*color: var\(--ink-3\);/);
    expect(css).toMatch(/\.fieldControl \{[^}]*justify-content: flex-end;/);
    expect(css).not.toMatch(/border(-bottom|-top)?:[^;]*var\(--line/);
    expect(css).not.toMatch(/inset 0 \.5px 0/);
  });

  it("leaves in-row ghost actions without a ring", () => {
    expect(css).not.toMatch(/--ring-ctrl|data-variant="ghost"\][^{]*\{[^}]*box-shadow/);
  });

  it("tags every button with its variant", () => {
    expect(read("primitives/Button.jsx")).toMatch(/data-variant=\{variant\}/);
  });

  it("writes section titles in sentence case", () => {
    expect(read("features/settings/ProfileDetail.jsx")).toMatch(/title="MCP servers"/);
    expect(read("features/settings/ProfileDetail.jsx")).toMatch(/title="Danger zone"/);
    expect(read("features/settings/ProfileDetail.jsx")).not.toMatch(/Danger Zone|MCP Servers/);
  });

  it("adds with an icon and a verb, never a literal plus", () => {
    for (const file of settingsSources) expect(read(file)).not.toMatch(/>\s*\+ Add|"\+ Add/);
    expect(read("features/settings/fields/McpField.jsx")).toMatch(/icon=\{<PlusIcon \/>\}[^\n]*>Add MCP/);
  });
});

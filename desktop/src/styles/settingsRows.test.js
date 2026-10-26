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

  it("pitches rows at 40 with a hairline between them", () => {
    expect(css).toMatch(/\.fieldRow \{[^}]*min-height: var\(--ctl-40\);[^}]*border-bottom: \.5px solid var\(--line\)/);
    expect(css).toMatch(/\.sectionBody > \.fieldRow:last-child \{\s*border-bottom: 0;/);
  });

  it("rings in-row text actions so their box edge is the value column edge", () => {
    expect(css).toMatch(/\.fieldControl > button\[data-variant="ghost"\][^{]*\{[^}]*box-shadow: var\(--ring-ctrl\)/);
    expect(css).toMatch(/\.fieldControl > button\[data-variant="danger-ghost"\]/);
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

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const read = (file) => readFileSync(join(import.meta.dirname, "..", file), "utf8");
const rule = (css, selector) => css.match(new RegExp(`(?:^|\\n)${selector.replace(/[.\[\]="()]/g, "\\$&")}\\s*\\{([^{}]*)\\}`))?.[1] ?? "";

describe("message actions", () => {
  const ds = read("styles/design-system.css");

  it("reveals actions on focus within as well as hover, and at rest when marked", () => {
    expect(ds).toMatch(/\.msg-row:hover \.msg-actions,\s*\.msg-row:focus-within \.msg-actions,\s*\.msg-actions\[data-rest\]\s*\{\s*opacity:\s*1;/);
  });
});

describe("sidebar selection and muted rows", () => {
  const ds = read("styles/design-system.css");

  it("marks the selected row with a 3 px bar and a visible fill", () => {
    expect(ds).toMatch(/\.ds-sb-row\[data-sel\]:hover, \.sb-row\[data-sel\]:hover \{\s*background: var\(--selected\);\s*box-shadow: inset 3px 0 0 var\(--row-accent, var\(--accent\)\);/);
  });

  it("never fades a row with opacity", () => {
    expect(ds).not.toMatch(/\.(?:ds-)?sb-row\[data-(?:state|muted)[^{]*\{[^}]*opacity/);
    expect(read("primitives/SidebarRow.jsx")).not.toMatch(/opacity/);
  });

  it("keeps muted names on the secondary ink at full opacity", () => {
    expect(ds).toMatch(/\.ds-sb-row\[data-state="paused"\] \.sb-name,[^{]*\{\s*font-weight: var\(--fw-regular\);\s*color: var\(--ink-3\);/);
  });
});

describe("hit areas", () => {
  const sidebar = read("features/Sidebar.module.css");

  it("gives the footer icon buttons a 28 px target", () => {
    expect(rule(sidebar, ".footer :global(.ds-tip) .footerIcon")).toMatch(/width:\s*var\(--ctrl-sm\);\s*height:\s*var\(--ctrl-sm\)/);
  });

  it.each([".sectionAdd", ".pinButton", ".searchClose"])("gives %s at least 24 px", (selector) => {
    expect(rule(sidebar, selector)).toMatch(/width:\s*var\(--space-9\);\s*height:\s*var\(--space-9\)/);
  });

  it("keeps the section plus glyph at 12 px", () => {
    expect(rule(sidebar, ".sectionAdd :global(.ds-icon)")).toMatch(/width:\s*12px/);
  });
});

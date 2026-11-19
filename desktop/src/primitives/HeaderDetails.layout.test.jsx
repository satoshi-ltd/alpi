import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

const css = readFileSync(join(import.meta.dirname, "ChatHeader.module.css"), "utf8");
const rule = (name) => css.match(new RegExp(`\\.${name}\\s*\\{([^}]*)\\}`))?.[1] ?? "";

describe("profile details popover layout", () => {
  it("starts at the small popover width and grows with its content up to a cap", () => {
    expect(rule("menu")).toMatch(/min-width:\s*var\(--pop-sm\)/);
    expect(rule("menu")).toMatch(/(^|;)\s*width:\s*max-content/m);
    expect(rule("menu")).toContain("max-width: min(calc(var(--pop-lg) * 1.4), calc(100vw - 2 * var(--sp-24)))");
  });

  it("keeps every label and value on one line, the label as the fixed side", () => {
    expect(rule("detailLabel")).toMatch(/white-space:\s*nowrap/);
    expect(rule("detailLabel")).toMatch(/flex-shrink:\s*0/);
    expect(rule("detailValue")).toMatch(/white-space:\s*nowrap/);
    expect(rule("detailValue")).toMatch(/flex:\s*1/);
    expect(rule("detailValue")).not.toMatch(/overflow:\s*hidden/);
    expect(rule("menu")).toMatch(/max-width:/);
  });

  it("cuts only the text of a long model or provider name, never the meters and their tips", () => {
    const own = readFileSync(join(import.meta.dirname, "HeaderDetails.module.css"), "utf8");
    const clip = own.match(/\.clip\s*\{([^}]*)\}/)?.[1] ?? "";
    expect(clip).toMatch(/text-overflow:\s*ellipsis/);
    expect(clip).toMatch(/min-width:\s*0/);
  });
});

describe("workgroup details status", () => {
  it("cuts a long status with an ellipsis instead of spilling over its label", async () => {
    const { render } = await import("@testing-library/react");
    const { WorkgroupDetails } = await import("./HeaderDetails.jsx");
    const status = "Working · Fetching a very long step name that keeps going · @someone";
    const { container } = render(<WorkgroupDetails hubName="hub" memberCount={2} status={status} />);
    const value = container.querySelector("[data-status]");
    expect(value.parentElement.className).toMatch(/clip/);
    expect(value.parentElement.getAttribute("title")).toBe(status);
  });
});

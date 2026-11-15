import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it, vi } from "vitest";
import { act, fireEvent, render, screen } from "@testing-library/react";
import { palettes } from "../../../common/tokens.mjs";
import { BrowseDetailHead, BrowseRow, FactTable } from "./BrowseModal.jsx";

const read = (rel) => readFileSync(join(import.meta.dirname, "..", rel), "utf8");
const css = read("primitives/BrowseModal.module.css");
const rule = (name) => (css.match(new RegExp(`\\n\\.${name}\\s*\\{([^}]*)\\}`)) || [])[1] ?? "";
const decl = (body, prop) => (body.match(new RegExp(`(?:^|;|\\s)${prop}:\\s*([^;]+);`)) || [])[1]?.trim();

function lum(hex) {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255).map((v) => (v <= 0.04045 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4));
  return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2];
}
const ratio = (a, b) => { const [hi, lo] = [lum(a), lum(b)].sort((x, y) => y - x); return (hi + 0.05) / (lo + 0.05); };
function over(rgba, ground) {
  const [r, g, b, a] = rgba.slice(rgba.indexOf("(") + 1, -1).split(",").map(Number);
  return `#${[r, g, b].map((c, i) => Math.round(c * a + parseInt(ground.slice(1 + i * 2, 3 + i * 2), 16) * (1 - a)).toString(16).padStart(2, "0")).join("")}`;
}

describe("one list row for the four profile panels", () => {
  it("sets the title at 15 medium ink with an ellipsis, line 2 at 14 clamped to two lines, one 12 tabular meta", () => {
    expect(decl(rule("row"), "padding")).toBe("var(--sp-8) var(--sp-12)");
    expect(decl(rule("row"), "border-radius")).toBe("var(--r-control)");
    const title = rule("rowTitle");
    expect(decl(title, "font-size")).toBe("var(--text-ui)");
    expect(decl(title, "font-weight")).toBe("var(--fw-medium)");
    expect(decl(title, "text-overflow")).toBe("ellipsis");
    expect(title).not.toMatch(/font-mono/);
    const sub = rule("rowSub");
    expect(decl(sub, "font-size")).toBe("var(--text-small)");
    expect(decl(sub, "-webkit-line-clamp")).toBe("2");
    const meta = rule("rowMeta");
    expect(decl(meta, "font-size")).toBe("var(--text-meta)");
    expect(decl(meta, "font-variant-numeric")).toBe("tabular-nums");
    expect(decl(rule("rowBar"), "height")).toBe("3px");
    expect(decl(rule("rowOff"), "color")).toBe("var(--ink-2)");
  });

  it("never fades, pills or dots a row", () => {
    expect(css).not.toMatch(/\.rowMuted|\.sizeTag/);
    for (const name of ["row", "rowTitle", "rowSub", "rowMeta", "rowOff"]) expect(rule(name)).not.toMatch(/opacity/);
    for (const file of ["features/MemoryModal.module.css", "features/SkillsModal.module.css", "features/ToolsModal.module.css", "features/ScheduleModal.module.css"]) {
      expect(read(file)).not.toMatch(/\.(fileRow|skillRow|toolRow|jobRow|rowId|toolName|jobTitle|sizeTag|kw)\b/);
    }
  });

  it("lifts line 2 and the meta to ink-2 on the selected row, where ink-3 fails 4.5:1", () => {
    expect(decl(rule("row"), "--row-sub")).toBe("var(--ink-3)");
    expect(css).toMatch(/\.rowActive,\s*\.rowActive:hover \{[^}]*--row-sub: var\(--ink-2\)/);
    expect(decl(rule("rowSub"), "color")).toBe("var(--row-sub)");
    expect(decl(rule("rowMeta"), "color")).toBe("var(--row-sub)");
    const light = palettes.light;
    expect(ratio(light.ink3, over(light.selected, light.bgSide))).toBeLessThan(4.5);
    for (const mode of ["light", "dark"]) {
      const p = palettes[mode];
      expect(ratio(p.ink2, over(p.selected, p.bgSide)), mode).toBeGreaterThanOrEqual(4.5);
    }
  });

  it("renders title, line 2, the meta and the meter as one option", () => {
    render(<ul><BrowseRow title="Learned" sub="what scout has learned" meta="64%" bar={{ pct: 64, over: false }} active onSelect={() => {}} /></ul>);
    const option = screen.getByRole("option", { selected: true });
    expect(option.querySelector("[class*=rowTitle]").textContent).toBe("Learned");
    expect(option.querySelector("[class*=rowSub]").textContent).toBe("what scout has learned");
    expect(option.querySelector("[class*=rowMeta]").textContent).toBe("64%");
    expect(option.querySelector("[class*=rowBar] > span").style.width).toBe("64%");
    expect(option.className).toMatch(/rowActive/);
  });

  it("lets a state word take the meta slot in danger and keeps an off title at ink-2", () => {
    render(<ul><BrowseRow title="digest" meta="failed" metaTone="danger" off onSelect={() => {}} /></ul>);
    const option = screen.getByRole("option");
    expect(option.querySelector("[class*=rowMeta]").getAttribute("data-tone")).toBe("danger");
    expect(option.querySelector("[class*=rowTitle]").className).toMatch(/rowOff/);
    expect(option.querySelector("[class*=rowSub]")).toBeNull();
  });
});

describe("one detail header", () => {
  it("titles at 20 semibold with a 14 ink-3 state word and the id in mono beside a copy button", async () => {
    expect(decl(rule("detailTitle"), "font-size")).toBe("var(--text-title)");
    expect(decl(rule("detailTitle"), "font-weight")).toBe("var(--fw-semibold)");
    expect(decl(rule("detailState"), "font-size")).toBe("var(--text-small)");
    expect(decl(rule("detailState"), "color")).toBe("var(--ink-3)");
    expect(decl(rule("detailId"), "font-family")).toBe("var(--font-mono)");
    const writeText = vi.fn().mockResolvedValue();
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    render(<BrowseDetailHead title="hotel-intake" state="active" id="research/hotel-intake" actions={<button type="button">Run now</button>} />);
    expect(screen.getByRole("heading", { name: "hotel-intake" })).toBeTruthy();
    expect(screen.getByText("active")).toBeTruthy();
    expect(screen.getByText("research/hotel-intake").className).toMatch(/detailId/);
    expect(screen.getByRole("button", { name: "Run now" })).toBeTruthy();
    await act(async () => { fireEvent.click(screen.getByRole("button", { name: "Copy research/hotel-intake" })); });
    expect(writeText).toHaveBeenCalledWith("research/hotel-intake");
  });

  it("marks a failing state in danger", () => {
    render(<BrowseDetailHead title="Daily digest" state="failed" stateTone="danger" id="bad1" />);
    expect(screen.getByText("failed").getAttribute("data-tone")).toBe("danger");
  });
});

describe("one facts table", () => {
  it("labels in sentence case at 14 ink-3 in the 84 px column, values at 14 ink-2, empty facts dropped", () => {
    expect(decl(rule("fact"), "grid-template-columns")).toBe("var(--def-col) 1fr");
    expect(css).toMatch(/\.fact dt \{[^}]*font-size: var\(--text-small\);[^}]*color: var\(--ink-3\)/);
    expect(css).toMatch(/\.fact dd \{[^}]*font-size: var\(--text-small\);[^}]*color: var\(--ink-2\)/);
    render(<FactTable rows={[{ label: "About", value: "x" }, { label: "Next", value: null }, { label: "Last run", value: "failed", tone: "danger" }]} />);
    expect([...document.querySelectorAll("dt")].map((d) => d.textContent)).toEqual(["About", "Last run"]);
    expect(document.querySelectorAll("dd")[1].getAttribute("data-tone")).toBe("danger");
  });
});

import { readFileSync } from "node:fs";
import { join } from "node:path";
import { act, cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { SHAPE_IDS, WORKGROUP_SHAPE } from "../../../common/shapes.mjs";
import { MARK_SIZES, SHAPES, TURN } from "../../../common/agentMarks.mjs";
import { WG_ALPHA, WG_CELLS, WG_DANGER, WG_STILLS } from "../../../common/workgroupMark.mjs";
import { ACCENT_HEXES } from "../../../common/accents.mjs";
import { contrastRatio, nameTone } from "../../../common/name.mjs";
import { markTone } from "../../../common/markTone.mjs";
import { palettes } from "../../../common/tokens.mjs";
import Fold from "./Fold.jsx";
import { trackedCount } from "../lib/gaze.js";

const draw = (props) => render(<Fold {...props} />).container.firstChild;
const body = (root) => root.querySelector("path[data-body]");
const eyes = (root) => root.querySelectorAll("path[data-eye]");
const turn = ([ry, rx, rz]) => `rotateY(${ry}deg) rotateX(${rx}deg) rotateZ(${rz}deg)`;
const FRONT = turn([0, 0, 0]);

function reduceMotion(matches) {
  window.matchMedia = vi.fn(() => ({ matches, addEventListener() {}, removeEventListener() {} }));
}

afterEach(() => {
  cleanup();
  delete window.matchMedia;
  vi.restoreAllMocks();
});

describe("Fold profile marks", () => {
  it("draws every shape by name, a legacy fold id as the shape it maps to, and round when the value is unknown", () => {
    for (const shape of SHAPE_IDS) {
      const root = draw({ shape, color: "#3899e2" });
      expect(root.dataset.shape).toBe(shape);
      expect(root.dataset.mark).toBe(shape);
      expect(body(root).getAttribute("d")).toBe(SHAPES[shape].d);
      expect(root.querySelector("polygon")).toBeNull();
      cleanup();
    }
    for (const shape of [undefined, null, "", "pencil", "shield", "rocket", "alpaca"]) {
      expect(draw({ shape, color: "#3899e2" }).dataset.mark, String(shape)).toBe("round");
      cleanup();
    }
  });

  it("fills the shape in the profile colour and draws two filled eyes over it in the theme's eye ink", () => {
    const root = draw({ shape: "heart", color: "#3899e2", size: 40 });
    expect(body(root).getAttribute("fill")).toBe("#3899e2");
    expect(root.querySelector("mask")).toBeNull();
    expect(body(root).hasAttribute("mask")).toBe(false);
    expect(eyes(root)).toHaveLength(2);
    for (const eye of eyes(root)) expect(eye.getAttribute("fill")).toBe("var(--mark-eye)");
    expect(body(root).compareDocumentPosition(eyes(root)[0]) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(root.getAttribute("aria-hidden")).toBe("true");
  });

  it("draws a pale accent's body a step deeper in light so the white eyes hold 3:1, and the stored accent in dark", () => {
    const root = draw({ shape: "heart", color: "#f36a8a", size: 40 });
    expect(body(root).getAttribute("fill")).toBe("var(--mark-body)");
    expect(root.style.getPropertyValue("--mark-light")).toBe("#ec6a88");
    expect(root.style.getPropertyValue("--mark-dark")).toBe("#f36a8a");
    for (const accent of ACCENT_HEXES) {
      const light = markTone(accent, "light");
      expect(contrastRatio(light, palettes.light.markEye), accent).toBeGreaterThanOrEqual(3);
      expect(contrastRatio(accent, palettes.dark.markEye), accent).toBeGreaterThanOrEqual(3);
    }
    const css = readFileSync(join(import.meta.dirname, "Fold.module.css"), "utf8");
    expect(css).toMatch(/\.toned \{\s*--mark-body: var\(--mark-light\);\s*\}/);
    expect(css).toContain(':global(:root:not([data-mode="light"])) .toned { --mark-body: var(--mark-dark); }');
    expect(css).toContain(':global([data-mode="dark"]) .toned { --mark-body: var(--mark-dark); }');
  });

  it("falls back to the neutral ink when a profile has no colour", () => {
    expect(body(draw({ shape: "arch" })).getAttribute("fill")).toBe("var(--c, var(--ink-3))");
  });

  it("draws the default profile's id as Twin in the brand ink, whatever colour it is given", () => {
    for (const color of ["#f0b447", undefined]) {
      const root = draw({ shape: "twin", color, size: 28 });
      expect(root.dataset.mark).toBe("alpi-twin");
      expect(body(root).getAttribute("fill")).toBe("var(--accent)");
      expect(body(root).getAttribute("d")).toBe(SHAPES["alpi-twin"].d);
      cleanup();
    }
    expect(draw({ shape: "twin", size: 20 }).dataset.mark).toBe("alpi-twin-small");
  });

  it("sizes the slot on the shared mark scale", () => {
    expect(draw({ shape: "bell" }).style.width).toBe(`${MARK_SIZES.row}px`);
    cleanup();
    expect(draw({ shape: "bell", size: "md" }).style.width).toBe(`${MARK_SIZES.header}px`);
    cleanup();
    expect(draw({ shape: "bell", size: "hero" }).style.height).toBe(`${MARK_SIZES.hero}px`);
    cleanup();
    const specimen = draw({ shape: "bell", size: 40 });
    expect(specimen.style.width).toBe("40px");
    expect(specimen.querySelector("svg").getAttribute("width")).toBe("40");
  });

  it("maps the legacy flags to states: pulse works, unfolded pauses, outlined needs", () => {
    expect(draw({ shape: "clover", pulse: true }).dataset.state).toBe("working");
    cleanup();
    expect(draw({ shape: "clover", unfolded: true, pulse: true }).dataset.state).toBe("paused");
    cleanup();
    expect(draw({ shape: "clover", outlined: true }).dataset.state).toBe("needs");
    cleanup();
    expect(draw({ shape: "clover", state: "needs", pulse: true }).dataset.state).toBe("needs");
  });

  it("draws paused as a dashed neutral outline with no fill, facing the viewer", () => {
    const root = draw({ shape: "squircle", color: "#3899e2", state: "paused", size: 40 });
    const outline = root.querySelector("svg > path, svg > g > path");
    expect(outline.getAttribute("fill")).toBe("none");
    expect(outline.getAttribute("stroke")).toBe("var(--ink-3)");
    expect(outline.getAttribute("stroke-dasharray")).toBeTruthy();
    expect(root.querySelector("mask")).toBeNull();
    expect(root.querySelector("animate")).toBeNull();
    expect(root.querySelector("svg").style.transform).toBe(FRONT);
  });

  it("fades an offline mark without eyes", () => {
    const root = draw({ shape: "squircle", color: "#3899e2", state: "offline", size: 40 });
    expect(body(root).getAttribute("opacity")).toBe("0.3");
    expect(eyes(root)).toHaveLength(0);
  });

  it("morphs the eyes through the state's sequence and turns the mark in 3D at live sizes", () => {
    const root = draw({ shape: "bean", color: "#3899e2", state: "working", size: 40 });
    expect(root.querySelectorAll("path[data-eye] animate[attributeName='d']")).toHaveLength(2);
    expect(root.querySelector("svg").getAttribute("class")).toBe("vt-a vt-turn-working");
    expect(document.querySelector("style[data-agent-marks]")).not.toBeNull();
  });

  it("keeps an idle row mark still, and an inline mark still in every state", () => {
    const row = draw({ shape: "bean", color: "#3899e2", state: "idle" });
    expect(row.querySelector("animate")).toBeNull();
    expect(row.querySelector("svg").getAttribute("class")).toBeNull();
    expect(row.querySelector("svg").style.transform).toBe(turn(TURN.still.idle.map((a) => a * TURN.smallTurn)));
    cleanup();
    const inline = draw({ shape: "bean", color: "#3899e2", state: "working", size: "inline" });
    expect(inline.querySelector("animate")).toBeNull();
    expect(inline.querySelector("[class]")).toBeNull();
  });

  it("holds the state's still pose and expression under reduced motion", () => {
    reduceMotion(true);
    const root = draw({ shape: "bean", color: "#3899e2", state: "working", size: 72 });
    expect(root.querySelector("animate")).toBeNull();
    expect(root.querySelector("[class*='am-'], [class*='vt-']")).toBeNull();
    expect(root.querySelector("svg").style.transform).toBe(turn(TURN.still.working));
    expect(eyes(root)).toHaveLength(2);
  });

  it("follows the mouse only when watching, and drops its listeners on unmount", () => {
    const add = vi.spyOn(window, "addEventListener");
    const remove = vi.spyOn(window, "removeEventListener");
    const { unmount } = render(<Fold shape="heart" color="#f36a8a" size={72} watch />);
    expect(add.mock.calls.filter(([type]) => type === "mousemove")).toHaveLength(1);
    unmount();
    expect(remove.mock.calls.filter(([type]) => type === "mousemove")).toHaveLength(1);
    add.mockClear();
    render(<Fold shape="heart" color="#f36a8a" size={72} />);
    expect(add.mock.calls.filter(([type]) => type === "mousemove")).toHaveLength(0);
  });

  it("follows the pointer through CSS variables on one shared listener, smoothly and without re-rendering", async () => {
    const add = vi.spyOn(window, "addEventListener");
    const frames = [];
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((fn) => frames.push(fn));
    const { container } = render(
      <>
        <Fold shape="heart" color="#f36a8a" size={72} watch />
        <Fold shape="clover" color="#3899e2" size={72} state="working" watch />
      </>,
    );
    expect(add.mock.calls.filter(([type]) => type === "mousemove")).toHaveLength(1);
    const [hero] = [...container.querySelectorAll("[data-shape] > span")];
    const svg = hero.querySelector("svg");
    window.dispatchEvent(new MouseEvent("mousemove", { clientX: 900, clientY: 0 }));
    let t = 0;
    const run = () => { const pending = frames.splice(0); pending.forEach((fn) => fn((t += 16))); };
    run();
    const first = Number(hero.style.getPropertyValue("--gx"));
    expect(first).toBeGreaterThan(0);
    for (let i = 0; i < 60; i += 1) run();
    const settled = Number(hero.style.getPropertyValue("--gx"));
    expect(settled).toBeGreaterThan(first);
    expect(settled).toBeLessThanOrEqual(1);
    expect(hero.querySelector("svg")).toBe(svg);
    expect(frames).toHaveLength(0);
  });

  it("never follows the pointer when paused, offline or below hero size", () => {
    const add = vi.spyOn(window, "addEventListener");
    const { container } = render(
      <>
        <Fold shape="heart" color="#f36a8a" size={72} state="paused" watch />
        <Fold shape="heart" color="#f36a8a" size={72} state="offline" watch />
        <Fold shape="heart" color="#f36a8a" size="md" state="working" watch />
        <Fold shape="heart" color="#f36a8a" state="working" watch />
        <Fold shape="heart" color="#f36a8a" size={14} watch />
      </>,
    );
    expect(add.mock.calls.filter(([type]) => type === "mousemove")).toHaveLength(0);
    expect(container.querySelector("[data-watch]")).toBeNull();
  });

  it("draws every mark still while the window is unfocused and comes back alive on focus", () => {
    const { container } = render(
      <>
        <Fold shape="heart" color="#f36a8a" size={72} state="working" watch />
        <Fold shape="bean" color="#3899e2" size="md" state="needs" />
        <Fold shape={WORKGROUP_SHAPE} color="#3899e2" size={72} state="running" />
      </>,
    );
    const alive = () => container.querySelectorAll("animate, .vt-a, .am-a, [data-live], [data-watch]").length;
    expect(alive()).toBeGreaterThan(0);
    expect(trackedCount()).toBe(1);
    act(() => { window.dispatchEvent(new Event("blur")); });
    expect(alive()).toBe(0);
    expect(trackedCount()).toBe(0);
    const [hero, header] = container.querySelectorAll("[data-shape]");
    expect(hero.dataset.state).toBe("working");
    expect(hero.querySelector("svg").style.transform).toBe(turn(TURN.still.working));
    expect(header.dataset.state).toBe("needs");
    act(() => { window.dispatchEvent(new Event("focus")); });
    expect(container.querySelector("[data-watch]")).not.toBeNull();
    expect(container.querySelectorAll("animate").length).toBeGreaterThan(0);
    expect(trackedCount()).toBe(1);
  });

  it("stops every mark while the document is hidden", () => {
    const { container } = render(<Fold shape="heart" color="#f36a8a" size={72} state="working" watch />);
    expect(container.querySelector("[data-live]")).not.toBeNull();
    Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "hidden" });
    act(() => { document.dispatchEvent(new Event("visibilitychange")); });
    expect(container.querySelector("animate, [data-live], [data-watch]")).toBeNull();
    Object.defineProperty(document, "visibilityState", { configurable: true, get: () => "visible" });
    act(() => { document.dispatchEvent(new Event("visibilitychange")); });
    expect(container.querySelector("[data-live]")).not.toBeNull();
  });

  it("never listens to the mouse under reduced motion", () => {
    reduceMotion(true);
    const add = vi.spyOn(window, "addEventListener");
    render(<Fold shape="heart" color="#f36a8a" size={72} watch />);
    expect(add.mock.calls.filter(([type]) => type === "mousemove")).toHaveLength(0);
  });

  it("subscribes to the reduced-motion query once, not on every render", () => {
    const listen = vi.fn();
    window.matchMedia = vi.fn(() => ({ matches: false, addEventListener: listen, removeEventListener() {} }));
    const { rerender } = render(<Fold shape="heart" color="#f36a8a" size={72} state="working" />);
    const subscribed = listen.mock.calls.length;
    for (const state of ["idle", "working", "done"]) rerender(<Fold shape="heart" color="#f36a8a" size={72} state={state} />);
    expect(listen.mock.calls.length).toBe(subscribed);
  });

  it("looks down when a text field already has focus as it starts watching, and stops once that field is gone", () => {
    const frames = [];
    vi.spyOn(window, "requestAnimationFrame").mockImplementation((fn) => frames.push(fn));
    let t = 0;
    const settle = () => { for (let i = 0; i < 80; i += 1) frames.splice(0).forEach((fn) => fn((t += 16))); };
    const field = document.createElement("textarea");
    document.body.appendChild(field);
    field.focus();
    const { container } = render(<Fold shape="heart" color="#f36a8a" size={72} watch />);
    const hero = container.querySelector("[data-shape] > span");
    settle();
    expect(Number(hero.style.getPropertyValue("--gy"))).toBeGreaterThan(0.9);
    field.remove();
    window.dispatchEvent(new MouseEvent("mousemove", { clientX: 0, clientY: 0 }));
    settle();
    expect(Number(hero.style.getPropertyValue("--gy"))).toBeLessThan(0.5);
  });

  it("carries no stylesheet of its own beyond the slot", () => {
    const css = readFileSync(join(import.meta.dirname, "Fold.module.css"), "utf8");
    expect(css).not.toMatch(/@keyframes|animation/);
  });
});

describe("Fold workgroup honeycomb", () => {
  const cells = (root) => [...root.querySelectorAll("[data-cell]")];
  const fills = (root) => cells(root).map((c) => (c.tagName === "g" ? c.querySelector("path") : c).getAttribute("fill"));

  const INK3 = "var(--ink-3)";
  const LIT = "var(--wg-lit)";
  const DANGER = `var(--c-danger, ${WG_DANGER})`;
  const strokes = (root) => cells(root).map((c) => (c.tagName === "g" ? c.querySelector("path") : c).getAttribute("stroke"));

  it("draws the three soft cells in neutral ink at rest, never in the hub colour, on the shared mark scale", () => {
    const row = draw({ shape: WORKGROUP_SHAPE, color: "#3899e2" });
    expect(row.dataset.shape).toBe(WORKGROUP_SHAPE);
    expect(row.dataset.mark).toBe("soft-honeycomb");
    expect(row.getAttribute("aria-hidden")).toBe("true");
    expect(cells(row).map((c) => c.dataset.cell)).toEqual(["left", "top", "right"]);
    expect(fills(row)).toEqual([INK3, INK3, INK3]);
    expect(row.style.width).toBe(`${MARK_SIZES.row}px`);
    expect(Object.values(WG_CELLS).some((set) => set.top === cells(row)[1].getAttribute("d"))).toBe(true);
    cleanup();
    expect(draw({ shape: WORKGROUP_SHAPE, size: "md" }).style.width).toBe(`${MARK_SIZES.header}px`);
  });

  it("keeps a done workgroup neutral", () => {
    const root = draw({ shape: WORKGROUP_SHAPE, color: "#3899e2", state: "done", size: 40 });
    expect(fills(root)).toEqual([INK3, INK3, INK3]);
    expect(root.innerHTML).not.toContain("#3899e2");
  });

  it("opens the gaps between cells at small sizes", () => {
    const inline = cells(draw({ shape: WORKGROUP_SHAPE, size: 14 }))[1].getAttribute("d");
    cleanup();
    const hero = cells(draw({ shape: WORKGROUP_SHAPE, size: 72 }))[1].getAttribute("d");
    expect(inline).not.toBe(hero);
  });

  it.each([[[0, 3], "left"], [[1, 3], "top"], [[2, 3], "right"], [[3, 4], "right"]])(
    "leans the cell of phase %j toward the viewer in the hub colour, and only that cell",
    (phase, lead) => {
      const root = draw({ shape: WORKGROUP_SHAPE, color: "#3899e2", state: "running", phase, size: 40 });
      expect(root.dataset.cell).toBe(lead);
      const current = root.querySelector("[data-lead]");
      expect(current.dataset.cell).toBe(lead);
      expect(current.getAttribute("fill")).toBe(LIT);
      expect(current.getAttribute("fill-opacity")).toBeNull();
      expect(current.getAttribute("class")).toBe("am-a am-wg-fill");
      expect(root.querySelector("svg").getAttribute("class")).toBe(`vt-a vt-wg-running-${lead}`);
      expect(root.innerHTML.split(LIT).length - 1).toBe(1);
    },
  );

  it("fills finished cells faint in neutral ink and outlines pending cells in neutral ink", () => {
    const root = draw({ shape: WORKGROUP_SHAPE, color: "#3899e2", state: "running", phase: [1, 3], size: 40 });
    const [left, , right] = cells(root);
    expect(left.getAttribute("fill")).toBe(INK3);
    expect(left.getAttribute("fill-opacity")).toBe(String(WG_ALPHA.faint));
    expect(right.getAttribute("fill")).toBe("none");
    expect(right.getAttribute("stroke")).toBe(INK3);
  });

  it("never takes an owner colour, even when one is passed", () => {
    const root = draw({ shape: WORKGROUP_SHAPE, color: "#3899e2", state: "running", phase: [0, 2], active: "#f36a8a", owner: "lingo", size: 40 });
    expect(root.querySelector("[data-lead]").getAttribute("fill")).toBe(LIT);
    expect(root.innerHTML).not.toContain("#f36a8a");
  });

  it("holds the lean still at row size, at the smaller angle", () => {
    const root = draw({ shape: WORKGROUP_SHAPE, color: "#3899e2", state: "running", phase: [2, 3] });
    expect(root.querySelector("svg").getAttribute("class")).toBeNull();
    expect(root.querySelector("[data-lead]").getAttribute("class")).toBeNull();
    expect(root.querySelector("svg").style.transform).toBe(turn(WG_STILLS["running-right"].map((a) => a * TURN.smallTurn)));
  });

  it("chases light around the cells in the hub colour while running without a known phase", () => {
    const root = draw({ shape: WORKGROUP_SHAPE, color: "#3899e2", pulse: true, size: 40 });
    expect(root.dataset.state).toBe("running");
    expect(cells(root).every((c) => c.getAttribute("class") === "am-a am-wg-chase")).toBe(true);
    expect(fills(root)).toEqual([LIT, LIT, LIT]);
    expect(cells(root).map((c) => c.getAttribute("fill-opacity"))).toEqual([String(WG_ALPHA.chase), null, String(WG_ALPHA.chase)]);
  });

  it("lifts the waiting cell in the hub colour when it needs you, the rest neutral", () => {
    const root = draw({ shape: WORKGROUP_SHAPE, color: "#3899e2", state: "needs", phase: [2, 3], size: 40 });
    const lead = root.querySelector("[data-lead]");
    expect(lead.dataset.cell).toBe("right");
    expect(lead.querySelector("g").getAttribute("class")).toBe("am-a am-wg-pop");
    expect(lead.querySelector("path").getAttribute("fill")).toBe(LIT);
    expect(fills(root)).toEqual([INK3, INK3, LIT]);
  });

  it("fills only the waiting cell in the hub colour at row size, with no pop, the rest neutral", () => {
    const root = draw({ shape: WORKGROUP_SHAPE, color: "#3899e2", state: "needs", phase: [2, 3], size: 20 });
    const lead = root.querySelector("[data-lead]");
    expect(lead.tagName.toLowerCase()).toBe("path");
    expect(lead.getAttribute("fill")).toBe(LIT);
    expect(root.querySelector(".am-wg-pop")).toBeNull();
    expect(fills(root)).toEqual([INK3, INK3, LIT]);
  });

  it("fills the failed cell in the danger colour, the rest faint neutral, and shivers at live sizes", () => {
    const root = draw({ shape: WORKGROUP_SHAPE, color: "#3899e2", state: "failed", size: 40 });
    const lead = root.querySelector("[data-lead]");
    expect(lead.dataset.cell).toBe("top");
    expect(lead.getAttribute("fill")).toBe(DANGER);
    expect(fills(root)).toEqual([INK3, DANGER, INK3]);
    expect(root.innerHTML).not.toContain("#3899e2");
    expect(root.querySelector(".am-wg-shiver")).not.toBeNull();
  });

  it("outlines queued cells in neutral ink", () => {
    const root = draw({ shape: WORKGROUP_SHAPE, color: "#3899e2", state: "queued" });
    expect(fills(root)).toEqual(["none", "none", "none"]);
    expect(strokes(root)).toEqual([INK3, INK3, INK3]);
  });

  it("unfolds into dashed neutral cells with no fill, facing the viewer, when paused", () => {
    const root = draw({ shape: WORKGROUP_SHAPE, color: "#3899e2", unfolded: true, pulse: true, size: 40 });
    expect(root.dataset.state).toBe("paused");
    for (const cell of cells(root)) {
      const path = cell.querySelector("path");
      expect(path.getAttribute("fill")).toBe("none");
      expect(path.getAttribute("stroke")).toBe(INK3);
      expect(path.getAttribute("stroke-dasharray")).toBeTruthy();
    }
    expect(root.querySelector("[class]")).toBeNull();
    expect(root.querySelector("svg").style.transform).toBe(FRONT);
  });

  it("draws an outlined workgroup as paused, with no tinted look left, and fades offline cells in neutral ink", () => {
    const outlined = draw({ shape: WORKGROUP_SHAPE, color: "#3899e2", outlined: true });
    expect(outlined.dataset.state).toBe("paused");
    const path = cells(outlined)[0].querySelector("path");
    expect(path.getAttribute("fill")).toBe("none");
    expect(path.getAttribute("fill-opacity")).toBeNull();
    expect(WG_ALPHA.disabled).toBeUndefined();
    cleanup();
    const offline = draw({ shape: WORKGROUP_SHAPE, color: "#3899e2", state: "offline" });
    expect(fills(offline)).toEqual([INK3, INK3, INK3]);
    expect(cells(offline).every((c) => c.getAttribute("fill-opacity") === String(WG_ALPHA.offline))).toBe(true);
  });

  it("faces the viewer, still, under reduced motion", () => {
    reduceMotion(true);
    const root = draw({ shape: WORKGROUP_SHAPE, color: "#3899e2", state: "running", phase: [1, 3], size: 72 });
    expect(root.querySelector("[class]")).toBeNull();
    expect(root.querySelector("svg").style.transform).toBe(FRONT);
    expect(root.querySelector("[data-lead]").getAttribute("fill")).toBe(LIT);
  });

  it("pops the waiting cell above row size, at header size too", () => {
    const header = draw({ shape: WORKGROUP_SHAPE, color: "#3899e2", state: "needs", phase: [1, 3], size: MARK_SIZES.header, still: true });
    expect(header.querySelector("[data-lead] g").getAttribute("transform")).toMatch(/^translate\(.+\) scale\(/);
    cleanup();
    const row = draw({ shape: WORKGROUP_SHAPE, color: "#3899e2", state: "needs", phase: [1, 3], size: MARK_SIZES.row });
    expect(row.querySelector("[data-lead]").tagName).toBe("path");
  });

  it("tones the lit cell per theme like a name, so a pale hub still reads", () => {
    const root = draw({ shape: WORKGROUP_SHAPE, color: "#f0b447", state: "running", phase: [1, 3], size: 40 });
    expect(root.style.getPropertyValue("--wg-lit-light")).toBe(nameTone("#f0b447", palettes.light.bgPane));
    expect(root.style.getPropertyValue("--wg-lit-dark")).toBe(nameTone("#f0b447", palettes.dark.bgPane));
    const css = readFileSync(join(import.meta.dirname, "Fold.module.css"), "utf8");
    expect(css).toMatch(/\.lit \{\s*--wg-lit: var\(--wg-lit-light\);\s*\}/);
    expect(css).toContain(':global(:root:not([data-mode="light"])) .lit { --wg-lit: var(--wg-lit-dark); }');
    expect(css).toContain(':global([data-mode="dark"]) .lit { --wg-lit: var(--wg-lit-dark); }');
  });

  it.each(ACCENT_HEXES)("lights %s at 3:1 or more on every ground of both themes", (accent) => {
    for (const state of ["running", "needs"]) {
      const root = draw({ shape: WORKGROUP_SHAPE, color: accent, state, phase: [1, 3], size: 40 });
      for (const mode of ["light", "dark"]) {
        const tone = root.style.getPropertyValue(`--wg-lit-${mode}`);
        for (const ground of ["bgPane", "bgSide", "bg"]) {
          expect(contrastRatio(tone, palettes[mode][ground]), `${state} ${mode} ${ground}`).toBeGreaterThanOrEqual(3);
        }
      }
      cleanup();
    }
  });

  it("keeps the brand ink when the hub colour is unknown", () => {
    const root = draw({ shape: WORKGROUP_SHAPE, state: "running", phase: [1, 3], size: 40 });
    expect(root.querySelector("[data-lead]").getAttribute("fill")).toBe("var(--accent)");
    expect(root.style.getPropertyValue("--wg-lit-light")).toBe("");
  });

  it("ships its keyframes with the marks' motion sheet", () => {
    draw({ shape: WORKGROUP_SHAPE, state: "running", phase: [1, 3], size: 40 });
    const css = document.querySelector("style[data-agent-marks]").textContent;
    for (const name of ["am-wg-fill", "am-wg-chase", "am-wg-pop", "am-wg-shiver", "vt-wg-idle", "vt-wg-running-top", "vt-wg-failed-left"]) {
      expect(css).toContain(`@keyframes ${name}{`);
    }
  });
});

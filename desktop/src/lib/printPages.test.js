import { afterEach, describe, expect, it, vi } from "vitest";
import { BODY_HEIGHT, PAGE_CSS, PAGE_SLACK, PAGE_WIDTH, articleUnits, measureBlocks, paginate, renderPrintPages, splitWords } from "./printPages.js";
import { exportArticle } from "../../../common/messageExport.mjs";
import { FONT_WAIT_MS, PRINT_ROOT_CLASS, clearPrintSheet, mountPrintSheet, printMessage } from "./messageExport.js";

const NOON = new Date(2026, 9, 25, 12).getTime() / 1000;
const CHART = '```chart\n{"type": "bar", "title": "Chats", "x": ["Mon", "Tue"], "series": [{"name": "Chats", "values": [3, 5]}]}\n```';
const ROWS = Array.from({ length: 12 }, (_, i) => `| Topic ${i + 1} | ${i + 1} |`).join("\n");
const CODE = Array.from({ length: 20 }, (_, i) => `line ${i + 1}`).join("\n");
const MESSAGE = {
  title: "Weekly review report",
  profile: "sentinel",
  server: "casa",
  at: NOON,
  body: `Opening paragraph.\n\n${CHART}\n\n## Topics\n\n| Topic | Chats |\n| --- | --- |\n${ROWS}\n\n\`\`\`\n${CODE}\n\`\`\`\n\n3. third\n4. fourth\n\nClosing paragraph.`,
};

const PART = 100;
const ATOMIC = { H1: 60, H2: 40, H3: 30, P: 100, FIGURE: 300, BLOCKQUOTE: 80 };
const partsIn = (el) => el.querySelectorAll("li, tbody > tr, .pp-line");

function stubRect(el) {
  if (el.classList.contains("pp-word")) return { top: 0, height: 10 };
  if (el.tagName === "TH") return { top: 0, height: 20, width: el.cellIndex ? 272 : 400 };
  if (el.classList.contains("pp-unit")) {
    const parts = partsIn(el).length;
    return { top: 0, height: parts ? 20 + parts * PART : ATOMIC[el.firstElementChild.tagName] };
  }
  const siblings = [...el.parentElement.children];
  return { top: siblings.indexOf(el) * PART, height: PART };
}

const ids = (pages) => pages.map((p) => p.map((it) => (it.from === undefined ? it.block : `${it.block}:${it.from}-${it.to}`)));

afterEach(() => {
  clearPrintSheet();
  for (const node of document.querySelectorAll(`.${PRINT_ROOT_CLASS}`)) node.remove();
});

describe("paginate", () => {
  it("packs blocks in order and opens a page when the next one does not fit", () => {
    expect(ids(paginate([{ height: 400 }, { height: 400 }, { height: 300 }, { height: 600 }], 1000))).toEqual([[0, 1], [2, 3]]);
  });

  it("never splits an atomic block such as a chart or a paragraph", () => {
    const pages = paginate([{ height: 700 }, { height: 400 }], 1000);
    expect(ids(pages)).toEqual([[0], [1]]);
    expect(pages[1][0].scale).toBeUndefined();
  });

  it("gives a block taller than a page that cannot split a page of its own, scaled to fit", () => {
    const pages = paginate([{ height: 100 }, { height: 2000 }, { height: 100 }], 1000);
    expect(ids(pages)).toEqual([[0], [1], [2]]);
    expect(pages[1][0].scale).toBe(0.5);
  });

  it("splits an over-tall code block by line, each piece carrying its chrome", () => {
    const code = { height: 20 + 10 * 148, chrome: 20, parts: Array(10).fill(148), keep: true };
    expect(ids(paginate([{ height: 300 }, code], 1000))).toEqual([[0, "1:0-4"], ["1:4-10"]]);
  });

  it("moves a code block that fits a page whole instead of splitting it", () => {
    const code = { height: 420, chrome: 20, parts: [100, 100, 100, 100], keep: true };
    expect(ids(paginate([{ height: 700 }, code], 1000))).toEqual([[0], ["1:0-4"]]);
  });

  it("splits a table at a row boundary in the room left on the page", () => {
    const table = { height: 400, chrome: 40, parts: [90, 90, 90, 90] };
    expect(ids(paginate([{ height: 700 }, table], 1000))).toEqual([[0, "1:0-2"], ["1:2-4"]]);
  });

  it("puts a single row taller than a page on its own page, scaled, and keeps the other rows whole", () => {
    const table = { height: 1640, chrome: 40, parts: [100, 1400, 100] };
    const pages = paginate([table], 1000);
    expect(ids(pages)).toEqual([["0:0-1"], ["0:1-2"], ["0:2-3"]]);
    expect(pages[1][0].scale).toBeCloseTo(1000 / 1440);
  });

  it("opens a new page rather than leave room for not even one row", () => {
    const table = { height: 1240, chrome: 40, parts: Array(12).fill(100) };
    expect(ids(paginate([{ height: 900 }, table], 1000))).toEqual([[0], ["1:0-9"], ["1:9-12"]]);
  });

  it("keeps a heading with the first piece of what follows it", () => {
    expect(ids(paginate([{ height: 850 }, { height: 40, keepWithNext: true }, { height: 200 }], 1000))).toEqual([[0], [1, 2]]);
    const list = { height: 520, chrome: 20, parts: [100, 100, 100, 100, 100] };
    expect(ids(paginate([{ height: 800 }, { height: 40, keepWithNext: true }, list], 1000))).toEqual([[0, 1, "2:0-1"], ["2:1-5"]]);
  });

  it("never leaves a heading at the foot of a page away from what follows it", () => {
    const code = { height: 980, chrome: 20, parts: Array(10).fill(96), keep: true };
    expect(ids(paginate([{ height: 500 }, { height: 40, keepWithNext: true }, code], 1000))).toEqual([[0], [1, "2:0-9"], ["2:9-10"]]);
    expect(ids(paginate([{ height: 500 }, { height: 40, keepWithNext: true }, { height: 30, keepWithNext: true }, { height: 600 }], 1000))).toEqual([[0], [1, 2, 3]]);
    expect(ids(paginate([{ height: 500 }, { height: 40, keepWithNext: true }, { height: 3000 }], 1000))).toEqual([[0, 1], [2]]);
  });

  it("keeps a whole chain of headings together with a block that has to split", () => {
    const blocks = [{ height: 100 }, { height: 40, keepWithNext: true }, { height: 30, keepWithNext: true }, { height: 960, chrome: 0, parts: [480, 480], keep: true }];
    expect(ids(paginate(blocks, 1000))).toEqual([[0], [1, 2, "3:0-1"], ["3:1-2"]]);
  });

  it("returns one empty page for an empty document", () => {
    expect(paginate([], 1000)).toEqual([[]]);
  });

  it("places every part exactly once and never overfills a page", () => {
    let seed = 7;
    const rand = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
    const blocks = Array.from({ length: 60 }, () => {
      if (rand() < 0.5) return { height: Math.round(rand() * 400) + 10, keepWithNext: rand() < 0.2 };
      const parts = Array.from({ length: Math.round(rand() * 20) + 2 }, () => Math.round(rand() * 120) + 10);
      return { height: 30 + parts.reduce((a, b) => a + b, 0), chrome: 30, parts, keep: rand() < 0.5 };
    });
    const pages = paginate(blocks, 1000);
    const seen = blocks.map((b) => (b.parts ? Array(b.parts.length).fill(0) : [0]));
    for (const page of pages) {
      let used = 0;
      for (const { block, from, to, scale } of page) {
        const b = blocks[block];
        if (from === undefined) {
          seen[block][0] += 1;
          used += scale ? 1000 : b.height;
        } else {
          for (let k = from; k < to; k += 1) seen[block][k] += 1;
          used += scale ? 1000 : to - from === b.parts.length ? b.height : b.chrome + b.parts.slice(from, to).reduce((a, c) => a + c, 0);
        }
      }
      expect(used).toBeLessThanOrEqual(1000);
    }
    expect(seen.flat().every((n) => n === 1)).toBe(true);
    expect(pages.flat().map((it) => it.block)).toEqual([...pages.flat().map((it) => it.block)].sort((a, b) => a - b));
  });
});

describe("measured print pages", () => {
  const article = () => {
    const t = document.createElement("template");
    t.innerHTML = exportArticle(MESSAGE);
    return t.content.firstElementChild;
  };

  it("cuts the article into blocks without the meta line or the end footer", () => {
    const units = articleUnits(article());
    expect(units.map((u) => u.node.tagName)).toEqual(["H1", "P", "FIGURE", "H2", "TABLE", "PRE", "OL", "P"]);
    expect(units.map((u) => u.split)).toEqual(["text", "text", null, null, "table", "code", "list", "text"]);
    expect(units[3].keepWithNext).toBe(true);
    expect(units[5].lines).toHaveLength(20);
  });

  it("measures parts from the distance between their tops and the rest as chrome", () => {
    const host = document.createElement("div");
    const blocks = measureBlocks(articleUnits(article()), host, stubRect);
    expect(blocks[2]).toEqual({ height: 300, keepWithNext: false });
    expect(blocks[4]).toEqual({ height: 1220, keepWithNext: false, parts: Array(12).fill(100), chrome: 20, keep: false });
    expect(blocks[5].keep).toBe(true);
    expect(blocks[5].parts).toHaveLength(20);
  });

  it("gives every page the running header and a numbered footer, and loses no row, line or item", () => {
    const shell = renderPrintPages(MESSAGE, document.createElement("div"), stubRect);
    const pages = [...shell.querySelectorAll(".pp-page")];
    expect(pages.length).toBeGreaterThan(2);
    pages.forEach((page, i) => {
      expect(page.querySelector(".pp-head svg")).not.toBeNull();
      expect(page.querySelector(".pp-head").textContent).toBe("alpi· @sentinel · casaWeekly review report");
      expect(page.querySelector(".pp-foot .pp-sign").textContent).toMatch(/^@sentinel · /);
      expect(page.querySelector(".pp-number").textContent).toBe(`${i + 1} / ${pages.length}`);
      const used = [...page.querySelectorAll(".pp-body > .pp-unit")].reduce((sum, u) => sum + stubRect(u).height, 0);
      expect(used).toBeLessThanOrEqual(BODY_HEIGHT - PAGE_SLACK);
    });
    expect(shell.querySelectorAll("tbody > tr")).toHaveLength(12);
    expect(shell.querySelectorAll(".pp-line")).toHaveLength(20);
    expect(shell.querySelectorAll(".pp-line")[19].textContent).toBe("line 20");
    expect(shell.querySelectorAll("table").length).toBeGreaterThan(1);
    for (const table of shell.querySelectorAll("table")) expect(table.querySelector("thead th").textContent).toBe("Topic");
    expect([...shell.querySelectorAll("li")].map((li) => li.getAttribute("value"))).toEqual(["3", "4"]);
    expect(shell.querySelector(".ax-head, .ax-foot, .ax-sheet")).toBeNull();
  });

  it("still prints one numbered page for an empty message", () => {
    const shell = renderPrintPages({ profile: "pulse" }, document.createElement("div"), stubRect);
    expect(shell.querySelectorAll(".pp-page")).toHaveLength(1);
    expect(shell.querySelector(".pp-number").textContent).toBe("1 / 1");
    expect(shell.querySelector(".pp-head").textContent).toBe("alpi· @pulse");
  });

  it("mounts the measured pages in the print root and drops the measuring probe", () => {
    const before = document.body.children.length;
    mountPrintSheet(MESSAGE, "#3fb37a", { rectOf: stubRect });
    const root = document.querySelector(`.${PRINT_ROOT_CLASS}`);
    expect(document.body.children.length).toBe(before + 1);
    expect(root.querySelector("article.alpi-export > .pp-page")).not.toBeNull();
    expect(root.querySelectorAll(".pp-page").length).toBeGreaterThan(2);
    expect(root.querySelector(".ax-foot")).toBeNull();
    expect(root.querySelector("style").textContent).toContain(".pp-page");
  });

  it("leaves a safety margin at the foot of every page", () => {
    const rect = (el) => {
      if (el.classList.contains("pp-word")) return { top: 0, height: 10 };
      return { top: 0, height: el.firstElementChild?.tagName === "H1" ? 66 : 100 };
    };
    const body = Array.from({ length: 8 }, (_, i) => `Paragraph ${i + 1}.`).join("\n\n");
    const shell = renderPrintPages({ title: "Fill", profile: "pulse", body }, document.createElement("div"), rect);
    expect(66 + 8 * 100).toBeLessThanOrEqual(BODY_HEIGHT);
    expect(shell.querySelectorAll(".pp-page")).toHaveLength(2);
  });

  it("splits a paragraph taller than a page at its line boxes instead of shrinking it", () => {
    const words = Array.from({ length: 600 }, (_, i) => `w${i}`);
    const index = new Map();
    const line = (w) => {
      if (!index.has(w.textContent)) [...w.parentElement.children].forEach((x, k) => index.set(x.textContent, k));
      return Math.floor(index.get(w.textContent) / 5);
    };
    const rect = (el) => {
      if (el.classList.contains("pp-word")) return { top: line(el) * 20, height: 15 };
      if (el.classList.contains("pp-unit")) {
        const lines = new Set([...el.querySelectorAll(".pp-word")].map(line));
        return { top: 0, height: lines.size * 20 + 8 };
      }
      return { top: 0, height: 0 };
    };
    const shell = renderPrintPages({ title: "Long", profile: "pulse", body: `A **bold** start ${words.join(" ")}` }, document.createElement("div"), rect);
    const pages = [...shell.querySelectorAll(".pp-page")];
    expect(pages.length).toBeGreaterThanOrEqual(3);
    expect(shell.querySelector(".pp-scaled")).toBeNull();
    const text = [...shell.querySelectorAll(".pp-body p")].map((p) => p.textContent).join("");
    expect(text).toBe(`A bold start ${words.join(" ")}`);
    expect(shell.querySelector(".pp-body p strong").textContent).toBe("bold");
    for (const page of pages) {
      const used = [...page.querySelectorAll(".pp-body > .pp-unit")].reduce((sum, u) => sum + rect(u).height, 0);
      expect(used).toBeLessThanOrEqual(BODY_HEIGHT - PAGE_SLACK);
    }
  });

  it("prints every piece of a split table with the full table's column widths", () => {
    const shell = renderPrintPages(MESSAGE, document.createElement("div"), stubRect);
    const tables = [...shell.querySelectorAll("table")];
    expect(tables.length).toBeGreaterThan(1);
    for (const table of tables) {
      expect(table.style.tableLayout).toBe("fixed");
      expect([...table.querySelectorAll("colgroup > col")].map((c) => c.style.width)).toEqual(["400px", "272px"]);
    }
  });

  it("wraps long words and keeps pages portrait", () => {
    expect(PAGE_CSS).toContain("@page { size: portrait; }");
    expect(PAGE_CSS).toContain(".alpi-export, .alpi-export th, .alpi-export td { overflow-wrap: anywhere; }");
    expect(PAGE_CSS).toMatch(/\.pp-line \{[^}]*overflow-wrap: anywhere/);
  });

  it("lays the probe out under the same wrap rules as the printed page", () => {
    const wrapSelectors = [...PAGE_CSS.matchAll(/([^{}]+)\{[^}]*overflow-wrap: anywhere/g)].flatMap((m) => m[1].split(",").map((x) => x.trim()));
    const wraps = (node) => wrapSelectors.some((sel) => node.closest(sel));
    const probed = [];
    mountPrintSheet(MESSAGE, null, {
      rectOf: (node) => {
        if (node.matches("p, td, .pp-word, .pp-line")) probed.push(node);
        if (node.classList.contains("pp-unit")) expect(node.closest("[style*='width']").style.width).toBe(`${PAGE_WIDTH}px`);
        return stubRect(node);
      },
    });
    expect(probed.length).toBeGreaterThan(10);
    expect(probed.every(wraps)).toBe(true);
    const printed = [...document.querySelectorAll(`.${PRINT_ROOT_CLASS} .pp-body :is(p, td, .pp-word, .pp-line)`)];
    expect(printed.length).toBeGreaterThan(10);
    expect(printed.every(wraps)).toBe(true);
  });

  it("leaves no print root or probe behind when measuring throws", () => {
    document.title = "alpi";
    const before = document.body.children.length;
    expect(() => mountPrintSheet(MESSAGE, null, { rectOf: () => { throw new Error("layout"); } })).toThrow("layout");
    expect(document.body.children.length).toBe(before);
    expect(document.querySelector(`.${PRINT_ROOT_CLASS}`)).toBeNull();
    expect(document.title).toBe("alpi");
  });

  it("waits for the fonts before measuring", async () => {
    let ready;
    Object.defineProperty(document, "fonts", { configurable: true, value: { ready: new Promise((r) => { ready = r; }) } });
    window.print = vi.fn(async () => {});
    try {
      const done = printMessage(MESSAGE);
      await Promise.resolve();
      expect(document.querySelector(`.${PRINT_ROOT_CLASS}`)).toBeNull();
      ready();
      await done;
      expect(window.print).toHaveBeenCalledTimes(1);
      expect(document.querySelector(`.${PRINT_ROOT_CLASS}`)).not.toBeNull();
    } finally {
      delete document.fonts;
    }
  });

  it("breaks text without spaces into words, CJK included, and falls back to spaces", () => {
    const cjk = "今日は良い天気です。明日も晴れるでしょう。";
    const words = splitWords(cjk);
    expect(words.length).toBeGreaterThan(4);
    expect(words.join("")).toBe(cjk);
    expect(splitWords("a b  c", { segment: () => [{ segment: "a" }, { segment: " " }, { segment: "b" }, { segment: "  " }, { segment: "c" }] })).toEqual(["a ", "b  ", "c"]);
    expect(splitWords(" lead word ", null)).toEqual([" ", "lead ", "word "]);
    const t = document.createElement("template");
    t.innerHTML = exportArticle({ profile: "pulse", body: cjk });
    const [unit] = articleUnits(t.content.firstElementChild);
    expect(unit.tokens.length).toBe(words.length);
  });

  it("prints after at most the font wait when the fonts never settle", async () => {
    vi.useFakeTimers();
    Object.defineProperty(document, "fonts", { configurable: true, value: { ready: new Promise(() => {}) } });
    window.print = vi.fn(async () => {});
    try {
      const done = printMessage(MESSAGE);
      await Promise.resolve();
      expect(document.querySelector(`.${PRINT_ROOT_CLASS}`)).toBeNull();
      expect(document.body.querySelector(":scope > div > .alpi-export")).not.toBeNull();
      await vi.advanceTimersByTimeAsync(FONT_WAIT_MS);
      await done;
      expect(window.print).toHaveBeenCalledTimes(1);
      expect(document.querySelectorAll(".alpi-export").length).toBe(1);
    } finally {
      delete document.fonts;
      vi.useRealTimers();
    }
  });

  it("escapes message text in the running header", () => {
    const shell = renderPrintPages({ ...MESSAGE, title: "<img src=x onerror=alert(1)>", profile: "<b>x</b>" }, document.createElement("div"), stubRect);
    expect(shell.querySelector("img")).toBeNull();
    expect(shell.querySelector(".pp-title").textContent).toBe("<img src=x onerror=alert(1)>");
  });
});

import { describe, it, expect } from "vitest";
import { CHART_CASES, FORMAT_CASES } from "../../../common/chartSpec.fixtures.mjs";
import { chartLayout, chartLegend, chartSvg, describeChart, formatValue, isHorizontal, niceScale, parseChart } from "../../../common/chartSpec.mjs";
import { parseNotificationBody } from "../../../common/notificationBody.mjs";
import { renderMarkdown } from "./markdown.js";

const sortKeys = (o) => (Array.isArray(o) ? o.map(sortKeys) : o && typeof o === "object"
  ? Object.fromEntries(Object.keys(o).sort().map((k) => [k, sortKeys(o[k])])) : o);

const LINE = { type: "line", title: "Chats per day", x: ["Oct 4", "Oct 5", "Oct 6", "Oct 7"], series: [{ name: "This week", values: [2161, 1987, null, 1743] }, { name: "Last week", values: [2050, 2102, 1968, 1888] }] };
const TOPICS = { type: "bar", x: ["Booking and availability", "Spa"], series: [{ values: [744, 401] }] };

describe("parseChart", () => {
  it.each(CHART_CASES.map(([src, out]) => [src.slice(0, 40), src, out]))("matches the daemon on %s", (_, src, out) => {
    const got = parseChart(src);
    expect(got ? sortKeys(got) : null).toEqual(out ? sortKeys(JSON.parse(out)) : null);
  });
});

describe("chart layout", () => {
  it("rounds the axis to readable steps", () => {
    expect(niceScale([1694, 2161]).ticks).toEqual([1600, 1800, 2000, 2200]);
    expect(niceScale([3, 19], true).ticks).toEqual([0, 5, 10, 15, 20]);
  });

  it("turns bars sideways for long labels or many bars, never a line", () => {
    expect(isHorizontal(parseChart(TOPICS))).toBe(true);
    expect(isHorizontal(parseChart({ ...TOPICS, x: ["Mon", "Tue"] }))).toBe(false);
    expect(isHorizontal(parseChart({ type: "bar", x: "abcdefghi".split(""), series: [{ values: [1, 2, 3, 4, 5, 6, 7, 8, 9] }] }))).toBe(true);
    expect(isHorizontal(parseChart(LINE))).toBe(false);
    expect(isHorizontal(parseChart({ ...TOPICS, series: [{ values: [744, -401] }] }))).toBe(false);
  });

  it("breaks a line at a null and marks the last value of the first series", () => {
    const { items } = chartLayout(parseChart(LINE));
    const first = items.filter((it) => it.series === 0 && (it.k === "line" || it.k === "dot"));
    expect(first.map((it) => it.k)).toEqual(["line", "dot", "dot"]);
    expect(first[0].points).toHaveLength(2);
    expect(items.find((it) => it.k === "value").text).toBe("1,743");
  });

  it("fits row labels to the longest name, clipping only past 45% of the width", () => {
    const names = { type: "bar", x: ["DeepSeek V4 Flash 0731", "Claude Opus 5.5"], series: [{ values: [3, 1] }] };
    expect(chartLayout(parseChart(names)).items.find((it) => it.k === "label").text).toBe("DeepSeek V4 Flash 0731");
    const long = { ...names, x: ["A very long topic name that keeps going and going", "Spa"] };
    expect(chartLayout(parseChart(long), { width: 300 }).items.find((it) => it.k === "label").text.endsWith("…")).toBe(true);
    expect(chartLayout(parseChart(long), { width: 560, compact: true }).items.find((it) => it.k === "label").text).toBe(long.x[0]);
  });

  it("sizes wide labels by their cells, not their characters", () => {
    const spec = parseChart({ type: "bar", x: ["日本語のラベルです", "abc"], series: [{ values: [3, 1] }] });
    const label = chartLayout(spec).items.find((it) => it.k === "label");
    const bar = chartLayout(spec).items.find((it) => it.k === "bar");
    expect(bar.x).toBeGreaterThanOrEqual(18 * 6.2);
    expect(label.text).toBe("日本語のラベルです");
  });

  it("writes a value at the end of every bar of every series", () => {
    const spec = parseChart({ type: "bar", unit: "$/M tokens", x: ["Claude Opus 5.5", "DeepSeek V4.1 Flash"], series: [{ name: "Input", values: [4, 0.044] }, { name: "Output", values: [20, 0.62] }] });
    const { items } = chartLayout(spec);
    expect(items.filter((it) => it.k === "value").map((it) => it.text)).toEqual(["4", "20", "0.044", "0.62"]);
    for (const value of items.filter((it) => it.k === "value")) {
      const bar = items.find((it) => it.k === "bar" && Math.abs(it.y + it.h / 2 + 3.5 - value.y) < 0.01);
      expect(value.x).toBeCloseTo(bar.x + bar.w + 6);
    }
  });

  it("puts a long unit once beside the title instead of on every value", () => {
    const spec = parseChart({ type: "bar", title: "Prices", unit: "$/M tokens", x: ["a", "b"], series: [{ values: [1, 2] }] });
    expect(chartSvg(spec)).toContain('<figcaption class="ch-title">Prices · $/M tokens</figcaption>');
    expect(chartSvg(spec)).not.toContain(">1 $/M tokens<");
    expect(chartSvg(spec)).toContain('aria-label="Bar chart, Prices. 2 categories. a 1 $/M tokens, b 2 $/M tokens."');
    const rows = parseChart({ type: "bar", unit: "$", x: ["Claude Opus 5.5", "GPT-6 Luna"], series: [{ values: [20, 0.5] }] });
    expect(chartSvg(rows)).toContain(">$20<");
    expect(chartSvg(parseChart({ ...spec, title: "Bookings per day", unit: "bookings" }))).toContain('<figcaption class="ch-title">Bookings per day</figcaption>');
    expect(chartSvg(parseChart({ ...spec, title: "Response time", unit: "s" }))).toContain('<figcaption class="ch-title">Response time · s</figcaption>');
  });

  it("shows a legend only with two series, the comparison of a line dashed", () => {
    expect(chartLegend(parseChart(TOPICS))).toEqual([]);
    expect(chartLegend(parseChart(LINE))).toEqual([{ name: "This week", series: 0, dashed: false }, { name: "Last week", series: 1, dashed: true }]);
  });

  it("reads the chart aloud from its data", () => {
    expect(describeChart(parseChart(LINE))).toBe("Line chart, Chats per day. 4 points from Oct 4 to Oct 7. This week: from 2,161 to 1,743; Last week: from 2,050 to 1,888.");
    expect(describeChart(parseChart(TOPICS))).toBe("Bar chart. 2 categories. Booking and availability 744, Spa 401.");
  });

  it.each(FORMAT_CASES)("labels %s %s as %s, like the daemon", (value, unit, text) => {
    expect(formatValue(value, unit)).toBe(text);
  });

  it("never loops on values too close for the float step", () => {
    const spec = parseChart({ type: "line", x: ["a", "b"], series: [{ values: [100000000000000000, 100000000000000016] }] });
    const started = Date.now();
    expect(chartSvg(spec)).toContain("<svg");
    expect(Date.now() - started).toBeLessThan(500);
    expect(niceScale([1696000000000000000, 1696000000000000300]).ticks.length).toBeLessThanOrEqual(11);
  });

  it("thins crowded column ticks instead of cutting labels", () => {
    const spec = parseChart({ type: "bar", x: ["Oct 4", "Oct 5", "Oct 6", "Oct 7", "Oct 8", "Oct 9", "Oct 10", "Oct 11"], series: [{ values: [1, 2, 3, 4, 5, 6, 7, 8] }] });
    const ticks = chartLayout(spec, { width: 240, compact: true }).items.filter((it) => it.k === "tick" && it.anchor === "middle").map((it) => it.text);
    expect(ticks).toEqual(["Oct 4", "Oct 6", "Oct 8", "Oct 10"]);
  });

  it("labels every column of a short chart above it, below it when negative, and stacks with their total", () => {
    const delta = chartLayout(parseChart({ type: "bar", unit: "%", x: ["es", "de"], series: [{ values: [4.2, -6.5] }] }));
    const bars = delta.items.filter((it) => it.k === "bar");
    const values = delta.items.filter((it) => it.k === "value");
    expect(values.map((it) => it.text)).toEqual(["4.2%", "-6.5%"]);
    expect(values[0].y).toBeLessThan(bars[0].y);
    expect(values[1].y).toBeGreaterThan(bars[1].y + bars[1].h);
    const stack = chartLayout(parseChart({ type: "bar", stacked: true, x: ["Mon", "Tue"], series: [{ values: [1420, 1310] }, { values: [741, 677] }] }));
    expect(stack.items.filter((it) => it.k === "value").map((it) => it.text)).toEqual(["2,161", "1,987"]);
    const crowded = chartLayout(parseChart({ type: "bar", x: "abcdefghijklm".split(""), series: [{ values: [-1, ...Array(12).fill(5)] }] }));
    expect(crowded.items.some((it) => it.k === "value")).toBe(false);
  });

  it("keeps a short unit on the axis ticks", () => {
    const ticks = chartLayout(parseChart({ type: "bar", unit: "%", x: ["a", "b"], series: [{ values: [5, -10] }] })).items.filter((it) => it.k === "tick" && it.anchor === "end");
    expect(ticks.map((it) => it.text)).toContain("-10%");
  });

  it("keeps the unit off the axis so ticks fit their gutter", () => {
    const spec = parseChart({ type: "bar", unit: "requests", x: ["a", "b"], series: [{ values: [1200000, 3000000] }] });
    const ticks = chartLayout(spec).items.filter((it) => it.k === "tick" && it.anchor === "end").map((it) => it.text);
    expect(ticks.every((t) => !t.includes("requests"))).toBe(true);
    expect(ticks).toContain("3M");
  });

  it("escapes text that reaches the SVG", () => {
    const svg = chartSvg(parseChart({ type: "bar", title: "<b>x</b>", x: ["<i>"], series: [{ values: [1] }] }));
    expect(svg).not.toContain("<b>");
    expect(svg).toContain("&lt;i&gt;");
  });
});

describe("chart blocks in Markdown and notification bodies", () => {
  it("draws a valid block as a themed SVG figure with its description", () => {
    const html = renderMarkdown(`Trend.\n\n\`\`\`chart\n${JSON.stringify(LINE)}\n\`\`\``);
    expect(html).toContain('<figure class="md-chart">');
    expect(html).toContain("<svg");
    expect(html).toContain('class="ch-line ch-s1 ch-dashed"');
    expect(html).toContain('aria-label="Line chart, Chats per day.');
    expect(html).not.toContain("md-code");
  });

  it("draws only the slots it wrote itself, never one copied into the text", () => {
    const block = `\`\`\`chart\n${JSON.stringify(TOPICS)}\n\`\`\``;
    const first = renderMarkdown(`${block}\n\nfirst`);
    const nonce = first.match(/md-chart-slot">([^:<]+):/);
    expect(nonce).toBeNull();
    const forged = renderMarkdown(`${block}\n\n<div class="md-chart-slot">0</div>\n\n<div class="md-chart-slot">:0</div>\n\nsecond`);
    expect(forged.match(/<figure class="md-chart">/g)).toHaveLength(1);
  });

  it("never lets raw HTML in the Markdown draw SVG", () => {
    const html = renderMarkdown('<svg><rect width="99999" height="99999" class="bar s0"/></svg>\n\n<table width="99999"><tr><td>a</td></tr></table>');
    expect(html).not.toContain("<svg");
    expect(html).not.toContain("<rect");
    expect(html).not.toContain('width="99999"');
    expect(html).not.toContain("md-chart\"");
  });

  it("leaves a broken block as code", () => {
    const html = renderMarkdown("```chart\n{\"type\": \"pie\"}\n```");
    expect(html).toContain("md-code");
    expect(html).not.toContain("<svg");
  });

  it("parses a chart block in a notification body and keeps a broken one as code", () => {
    expect(parseNotificationBody(`\`\`\`chart\n${JSON.stringify(TOPICS)}\n\`\`\``)[0]).toMatchObject({ kind: "chart", spec: { type: "bar" } });
    expect(parseNotificationBody("```chart\n{bad}\n```")[0]).toEqual({ kind: "code", text: "{bad}" });
  });
});

describe("chart classes", () => {
  it("never reuse a class the global stylesheet already styles", async () => {
    const { readFileSync } = await import("node:fs");
    const { join } = await import("node:path");
    const css = readFileSync(join(import.meta.dirname, "..", "styles", "design-system.css"), "utf8");
    const svg = chartSvg(parseChart({ type: "line", title: "t", x: ["a", "b", "c"], series: [{ name: "x", values: [1, null, 3] }, { name: "y", values: [2, 2, 2] }] }))
      + chartSvg(parseChart({ type: "bar", stacked: true, x: ["Long label one", "b"], series: [{ name: "x", values: [1, 2] }, { name: "y", values: [2, 1] }] }));
    const classes = new Set([...svg.matchAll(/class="([^"]+)"/g)].flatMap((m) => m[1].split(" ")));
    for (const name of classes) {
      expect(name.startsWith("ch-")).toBe(true);
      const unscoped = new RegExp(`(^|[\\s,}])\\.${name}\\b`, "m");
      expect(css.replace(/\.md-chart[^,{]*/g, "")).not.toMatch(unscoped);
    }
  });
});

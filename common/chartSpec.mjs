// Mirrors alpi/charts.py parse_chart; chartSpec.fixtures.mjs holds the corpus both test against.
export const CHART_TYPES = ["line", "bar"];
export const MAX_SERIES = 4;
export const MAX_POINTS = { line: 60, bar: 24 };
export const MAX_TEXT = 80;
const HORIZONTAL_LABEL = 8;
const HORIZONTAL_COUNT = 8;

const MIN_WIDTH = 160;
const SPACE = /[ \t\n\r\f\v\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+/g;
const isText = (value) => typeof value === "string" || (typeof value === "number" && Number.isFinite(value));
const squash = (value) => String(value).replace(SPACE, " ").replace(/^ | $/g, "");
const clean = (value) => squash(Array.from(squash(value)).slice(0, MAX_TEXT).join(""));

export function parseChart(source) {
  let raw;
  try {
    raw = typeof source === "string" ? JSON.parse(source) : source;
  } catch {
    return null;
  }
  if (!raw || typeof raw !== "object" || Array.isArray(raw)) return null;
  if (!CHART_TYPES.includes(raw.type)) return null;
  if (!Array.isArray(raw.x) || !raw.x.length || raw.x.length > MAX_POINTS[raw.type] || !raw.x.every(isText)) return null;
  if (raw.type === "line" && raw.x.length < 2) return null;
  if (!Array.isArray(raw.series) || !raw.series.length || raw.series.length > MAX_SERIES) return null;
  const series = [];
  for (const s of raw.series) {
    if (!s || typeof s !== "object" || !Array.isArray(s.values) || s.values.length !== raw.x.length) return null;
    if (!s.values.every((v) => v === null || (typeof v === "number" && Number.isFinite(v)))) return null;
    if (s.values.every((v) => v === null)) return null;
    if (raw.stacked === true && raw.type === "bar" && s.values.some((v) => v !== null && v < 0)) return null;
    series.push({ name: isText(s.name) ? clean(s.name) : "", values: s.values.slice() });
  }
  if (raw.stacked === true && raw.type === "bar" && raw.x.some((_, i) => !Number.isFinite(series.reduce((sum, s) => sum + (s.values[i] ?? 0), 0)))) return null;
  return {
    type: raw.type,
    stacked: raw.type === "bar" && raw.stacked === true && series.length > 1,
    title: isText(raw.title) ? clean(raw.title) : "",
    unit: isText(raw.unit) ? clean(raw.unit) : "",
    x: raw.x.map(clean),
    series,
  };
}

export function isHorizontal(spec) {
  if (spec.type !== "bar" || spec.series.some((s) => s.values.some((v) => v !== null && v < 0))) return false;
  return spec.x.length > HORIZONTAL_COUNT || spec.x.some((label) => Array.from(label).length > HORIZONTAL_LABEL);
}

function niceStep(span) {
  const raw = span / 4;
  const power = 10 ** Math.floor(Math.log10(raw));
  const unit = raw / power;
  return (unit <= 1 ? 1 : unit <= 2 ? 2 : unit <= 2.5 ? 2.5 : unit <= 5 ? 5 : 10) * power;
}

export function niceScale(values, zero = false) {
  const nums = values.filter((v) => v !== null);
  let lo = Math.min(...nums, ...(zero ? [0] : []));
  let hi = Math.max(...nums, ...(zero ? [0] : []));
  if (lo === hi) {
    lo = lo === 0 ? 0 : lo - Math.abs(lo) * 0.1;
    hi = hi === 0 ? 1 : hi + Math.abs(hi) * 0.1;
  }
  const step = niceStep(hi - lo);
  if (!(step > 0) || lo + step === lo || !Number.isFinite(hi - lo)) return { lo, hi, ticks: [lo, hi] };
  lo = Math.floor(lo / step) * step;
  hi = Math.ceil(hi / step) * step;
  const count = Math.min(Math.round((hi - lo) / step), 10);
  const ticks = [];
  for (let k = 0; k <= count; k += 1) ticks.push(Number((lo + k * step).toPrecision(12)));
  return { lo, hi, ticks };
}

const SUFFIXES = [[1e9, "B"], [1e6, "M"], [1e4, "k"]];

function number(value) {
  const abs = Math.abs(value);
  if (abs === 0) return "0";
  if (abs >= 1e15 || abs < 1e-6) return value.toExponential(1);
  const big = SUFFIXES.find(([at]) => abs >= at);
  if (big) return `${(value / (big[0] === 1e4 ? 1e3 : big[0])).toLocaleString("en-US", { maximumFractionDigits: 1 })}${big[1]}`;
  if (abs < 1) return value.toLocaleString("en-US", { maximumSignificantDigits: 2 });
  return value.toLocaleString("en-US", { maximumFractionDigits: abs >= 100 ? 0 : abs >= 10 ? 1 : 2 });
}

export function inlineUnit(unit) {
  return unit === "%" || /^[$€£¥]$/.test(unit) ? unit : "";
}

export function chartCaption(spec) {
  const escaped = spec.unit.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const said = new RegExp(`(^|[^\\p{L}\\p{N}])${escaped}($|[^\\p{L}\\p{N}])`, "iu").test(spec.title);
  const aside = spec.unit && !inlineUnit(spec.unit) && !said ? spec.unit : "";
  return [spec.title, aside].filter(Boolean).join(" · ");
}

export function formatValue(value, unit = "") {
  if (value === null || value === undefined || !Number.isFinite(value)) return "—";
  const text = number(value === 0 ? 0 : value);
  if (!unit) return text;
  return unit === "%" ? `${text}%` : /^[$€£¥]$/.test(unit) ? `${unit}${text}` : `${text} ${unit}`;
}

export function describeChart(spec) {
  const kind = spec.type === "line" ? "Line chart" : spec.stacked ? "Stacked bar chart" : "Bar chart";
  const head = [kind, spec.title].filter(Boolean).join(", ");
  const n = spec.x.length;
  const span = spec.type === "line" ? `${n} points from ${spec.x[0]} to ${spec.x[n - 1]}` : `${n} ${n === 1 ? "category" : "categories"}`;
  const parts = spec.series.map((s) => {
    const vals = s.values.filter((v) => v !== null);
    const name = s.name ? `${s.name}: ` : "";
    return spec.type === "line"
      ? `${name}from ${formatValue(vals[0], spec.unit)} to ${formatValue(vals[vals.length - 1], spec.unit)}`
      : `${name}${spec.x.map((label, i) => `${label} ${formatValue(s.values[i], spec.unit)}`).join(", ")}`;
  });
  return `${head}. ${span}. ${parts.join("; ")}.`;
}

function lineLayout(spec, width, height, compact) {
  const { lo, hi, ticks } = niceScale(spec.series.flatMap((s) => s.values));
  const left = 44;
  const right = 46;
  const top = 6;
  const bottom = 18;
  const xOf = (i) => left + (i * (width - left - right)) / (spec.x.length - 1);
  const yOf = (v) => top + ((hi - v) * (height - top - bottom)) / (hi - lo);
  const items = [];
  for (const t of ticks) {
    items.push({ k: "grid", x1: left, x2: width - right, y: yOf(t) });
    items.push({ k: "tick", x: left - 6, y: yOf(t) + 3, anchor: "end", text: formatValue(t, inlineUnit(spec.unit)) });
  }
  const last = spec.x.length - 1;
  const marks = compact || last < 4 ? [0, last] : [0, Math.floor(last / 2), last];
  for (const i of marks) items.push({ k: "tick", x: xOf(i), y: height - 4, anchor: i === 0 ? "start" : i === last ? "end" : "middle", text: spec.x[i] });
  spec.series.forEach((s, n) => {
    let run = [];
    const flush = () => {
      if (run.length > 1) items.push({ k: "line", series: n, points: run });
      else if (run.length === 1) items.push({ k: "dot", series: n, cx: run[0][0], cy: run[0][1], r: 2 });
      run = [];
    };
    s.values.forEach((v, i) => (v === null ? flush() : run.push([xOf(i), yOf(v)])));
    flush();
  });
  const first = spec.series[0].values;
  const end = first.length - 1 - [...first].reverse().findIndex((v) => v !== null);
  items.push({ k: "dot", series: 0, cx: xOf(end), cy: yOf(first[end]), r: 3 });
  items.push({ k: "value", x: xOf(end) + 6, y: yOf(first[end]) + 3, anchor: "start", text: formatValue(first[end], inlineUnit(spec.unit)) });
  return items;
}

const MAX_LABELLED_COLUMNS = 12;

function columnLayout(spec, width, height) {
  const unit = inlineUnit(spec.unit);
  const totals = spec.x.map((_, i) => spec.series.reduce((sum, s) => sum + (s.values[i] ?? 0), 0));
  const labelled = spec.x.length <= MAX_LABELLED_COLUMNS;
  const { lo, hi, ticks } = niceScale(spec.stacked ? totals : spec.series.flatMap((s) => s.values), true);
  const left = 44;
  const right = 8;
  const top = labelled ? 16 : 6;
  const bottom = 18 + (labelled && lo < 0 ? 12 : 0);
  const band = (width - left - right) / spec.x.length;
  const yOf = (v) => top + ((hi - v) * (height - top - bottom)) / (hi - lo);
  const items = [];
  for (const t of ticks) {
    items.push({ k: "grid", x1: left, x2: width - right, y: yOf(t) });
    items.push({ k: "tick", x: left - 6, y: yOf(t) + 3, anchor: "end", text: formatValue(t, unit) });
  }
  const widest = Math.max(...spec.x.map(cells)) * 6 + 6;
  const every = Math.max(1, Math.ceil(widest / band));
  const valueAt = (text, cx, room, value, edge) => {
    if (!labelled || textWidth(text) > room + 6) return;
    items.push({ k: "value", x: cx, y: value < 0 ? edge + 11 : edge - 4, anchor: "middle", text });
  };
  spec.x.forEach((label, i) => {
    const x = left + i * band;
    if (i % every === 0) items.push({ k: "tick", x: x + band / 2, y: height - 4, anchor: "middle", text: label });
    if (spec.stacked) {
      let base = 0;
      spec.series.forEach((s, n) => {
        const v = s.values[i] ?? 0;
        if (v > 0) items.push({ k: "bar", series: n, x: x + band * 0.2, y: yOf(base + v), w: band * 0.6, h: yOf(base) - yOf(base + v) });
        base += v;
      });
      valueAt(formatValue(totals[i], unit), x + band / 2, band * 0.6, totals[i], yOf(totals[i]));
    } else {
      const w = (band * 0.6) / spec.series.length;
      spec.series.forEach((s, n) => {
        const v = s.values[i];
        if (v === null) return;
        const y0 = yOf(Math.max(0, lo));
        const bar = { k: "bar", series: n, x: x + band * 0.2 + n * w, y: Math.min(yOf(v), y0), w: Math.max(w - 1, 1), h: Math.abs(y0 - yOf(v)) };
        items.push(bar);
        valueAt(formatValue(v, unit), bar.x + bar.w / 2, bar.w, v, v < 0 ? bar.y + bar.h : bar.y);
      });
    }
  });
  return items;
}

const CHAR = 6.2;
const WIDE = /[\u1100-\u115f\u2e80-\ua4cf\uac00-\ud7a3\uf900-\ufaff\ufe30-\ufe4f\uff00-\uff60\uffe0-\uffe6\u{20000}-\u{3fffd}]/u;
const cells = (text) => Array.from(text).reduce((sum, ch) => sum + (WIDE.test(ch) ? 2 : 1), 0);
const textWidth = (text) => cells(text) * CHAR;

function clip(text, room) {
  const fits = Math.max(Math.floor(room / CHAR), 2);
  if (cells(text) <= fits) return text;
  let out = "";
  for (const ch of Array.from(text)) {
    if (cells(out + ch) > fits - 1) break;
    out += ch;
  }
  return `${out}…`;
}

function rowLayout(spec, width, compact) {
  const unit = inlineUnit(spec.unit);
  const thick = 9;
  const gap = 5;
  const bars = spec.stacked ? 1 : spec.series.length;
  const totals = spec.x.map((_, i) => spec.series.reduce((sum, s) => sum + Math.max(s.values[i] ?? 0, 0), 0));
  const shown = spec.stacked ? totals : spec.series.flatMap((s) => s.values.filter((v) => v !== null));
  const valueRoom = Math.max(...shown.map((v) => textWidth(formatValue(v, unit)))) + 8;
  const labelWidth = compact ? 0 : Math.min(Math.max(...spec.x.map(textWidth)) + 10, width * 0.45);
  const labelLine = compact ? 16 : 0;
  const block = bars * thick + (bars - 1) * gap;
  const row = labelLine + Math.max(block, compact ? 0 : 14) + 10;
  const track = Math.max(width - labelWidth - valueRoom, 40);
  const top = Math.max(...shown, 0);
  const scale = (v) => (top > 0 ? (track * v) / top : 0);
  const items = [];
  spec.x.forEach((label, i) => {
    const y = i * row;
    const barTop = y + labelLine + (compact ? 0 : Math.max((14 - block) / 2, 0));
    items.push({ k: "label", x: 0, y: compact ? y + 11 : barTop + block / 2 + 4, anchor: "start", text: clip(label, (compact ? width : labelWidth) - 10) });
    if (spec.stacked) {
      let base = labelWidth;
      spec.series.forEach((s, n) => {
        const v = Math.max(s.values[i] ?? 0, 0);
        if (v > 0) items.push({ k: "bar", series: n, x: base, y: barTop, w: scale(v), h: thick });
        base += scale(v);
      });
      items.push({ k: "value", x: base + 6, y: barTop + thick / 2 + 3.5, anchor: "start", text: formatValue(totals[i], unit) });
      return;
    }
    spec.series.forEach((s, n) => {
      const v = s.values[i];
      if (v === null) return;
      const w = Math.max(scale(Math.max(v, 0)), 1);
      const at = barTop + n * (thick + gap);
      items.push({ k: "bar", series: n, x: labelWidth, y: at, w, h: thick });
      items.push({ k: "value", x: labelWidth + w + 6, y: at + thick / 2 + 3.5, anchor: "start", text: formatValue(v, unit) });
    });
  });
  return { items, height: spec.x.length * row };
}

export function chartLayout(spec, { width: asked = 560, height = 170, compact = false } = {}) {
  const width = Math.max(asked, MIN_WIDTH);
  if (isHorizontal(spec)) {
    const rows = rowLayout(spec, width, compact);
    return { width, height: rows.height, items: rows.items };
  }
  const items = spec.type === "line" ? lineLayout(spec, width, height, compact) : columnLayout(spec, width, height);
  return { width, height, items };
}

export function chartLegend(spec) {
  if (spec.series.length < 2) return [];
  return spec.series.map((s, n) => ({ name: s.name || `Series ${n + 1}`, series: n, dashed: spec.type === "line" && n > 0 }));
}

const escapeXml = (text) => String(text).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");
const r1 = (n) => Math.round(n * 10) / 10;

export function chartSvg(spec, options = {}) {
  const { width, height, items } = chartLayout(spec, options);
  const parts = items.map((it) => {
    const s = `ch-s${it.series ?? 0}`;
    if (it.k === "grid") return `<line class="ch-grid" x1="${r1(it.x1)}" x2="${r1(it.x2)}" y1="${r1(it.y)}" y2="${r1(it.y)}"/>`;
    if (it.k === "line") return `<polyline class="ch-line ${s}${it.series > 0 ? " ch-dashed" : ""}" points="${it.points.map(([x, y]) => `${r1(x)},${r1(y)}`).join(" ")}"/>`;
    if (it.k === "dot") return `<circle class="ch-dot ${s}" cx="${r1(it.cx)}" cy="${r1(it.cy)}" r="${it.r}"/>`;
    if (it.k === "bar") return `<rect class="ch-bar ${s}" x="${r1(it.x)}" y="${r1(it.y)}" width="${r1(it.w)}" height="${r1(Math.max(it.h, 0))}"/>`;
    return `<text class="ch-${it.k}" x="${r1(it.x)}" y="${r1(it.y)}" text-anchor="${it.anchor}">${escapeXml(it.text)}</text>`;
  });
  const legend = chartLegend(spec).map((l) => `<span class="ch-key"><i class="ch-swatch ch-s${l.series}${l.dashed ? " ch-dashed" : ""}"></i>${escapeXml(l.name)}</span>`).join("");
  const caption = chartCaption(spec);
  const title = caption ? `<figcaption class="ch-title">${escapeXml(caption)}</figcaption>` : "";
  const svg = `<svg viewBox="0 0 ${width} ${height}" width="${width}" height="${height}" role="img" aria-label="${escapeXml(describeChart(spec))}">${parts.join("")}</svg>`;
  return `${title}${svg}${legend ? `<div class="ch-legend">${legend}</div>` : ""}`;
}


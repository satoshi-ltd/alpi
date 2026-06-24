import { describe, it, expect } from "vitest";
import { inlineSegments, parseNotificationBody } from "./notificationBody.js";

describe("parseNotificationBody — labels & paragraphs", () => {
  it("treats a whole-line bold as a standalone label and strips ** and trailing colon", () => {
    expect(parseNotificationBody("**Veredicto**")).toEqual([{ kind: "label", label: "Veredicto" }]);
    expect(parseNotificationBody("**Veredicto:**")).toEqual([{ kind: "label", label: "Veredicto" }]);
  });

  it("splits an inline label+body into eyebrow + paragraph (colon in or out)", () => {
    expect(parseNotificationBody("**Veredicto:** Día normal."))
      .toEqual([{ kind: "labelBody", label: "Veredicto", body: "Día normal." }]);
    expect(parseNotificationBody("**Veredicto**: Día normal."))
      .toEqual([{ kind: "labelBody", label: "Veredicto", body: "Día normal." }]);
  });

  it("does NOT promote a long bold lead-in to a label (>32 chars or >5 words → paragraph)", () => {
    const long = "**This lead-in is definitely far too long to be a label:** rest";
    expect(parseNotificationBody(long)).toEqual([{ kind: "p", text: long }]);
    expect(parseNotificationBody("**one two three four five six:** rest"))
      .toEqual([{ kind: "p", text: "**one two three four five six:** rest" }]);
  });

  it("does not treat **bold** at line start as a list", () => {
    expect(parseNotificationBody("**bold** word")[0].kind).toBe("p");
  });

  it("defaults to a paragraph and drops blank lines", () => {
    expect(parseNotificationBody("Just a sentence.")).toEqual([{ kind: "p", text: "Just a sentence." }]);
    expect(parseNotificationBody("a\n\n\nb")).toEqual([
      { kind: "p", text: "a" },
      { kind: "p", text: "b" },
    ]);
  });

  it("returns nothing for empty input", () => {
    expect(parseNotificationBody("")).toEqual([]);
    expect(parseNotificationBody(null)).toEqual([]);
  });
});

describe("parseNotificationBody — fallbacks", () => {
  it("maps #/## to a heading and ###+ to the eyebrow (subheading)", () => {
    expect(parseNotificationBody("## Anomalías")).toEqual([{ kind: "heading", text: "Anomalías" }]);
    expect(parseNotificationBody("# Top")).toEqual([{ kind: "heading", text: "Top" }]);
    expect(parseNotificationBody("### Sub")).toEqual([{ kind: "label", label: "Sub" }]);
  });

  it("drops horizontal rules", () => {
    expect(parseNotificationBody("a\n---\nb")).toEqual([
      { kind: "p", text: "a" },
      { kind: "p", text: "b" },
    ]);
  });

  it("renders a blockquote as an italic paragraph and merges consecutive lines", () => {
    expect(parseNotificationBody("> first\n> second")).toEqual([{ kind: "quote", text: "first second" }]);
  });
});

describe("parseNotificationBody — lists", () => {
  it("groups consecutive unordered items into one list with normalized markers", () => {
    expect(parseNotificationBody("- a\n• b\n* c")).toEqual([{
      kind: "list", ordered: false,
      items: [{ marker: "•", text: "a" }, { marker: "•", text: "b" }, { marker: "•", text: "c" }],
    }]);
  });

  it("groups ordered items and keeps the number marker", () => {
    expect(parseNotificationBody("1. a\n2. b")).toEqual([{
      kind: "list", ordered: true,
      items: [{ marker: "1.", text: "a" }, { marker: "2.", text: "b" }],
    }]);
  });

  it("keeps an emoji as the marker", () => {
    expect(parseNotificationBody("⚠️ anomaly\n🔴 down")).toEqual([{
      kind: "list", ordered: false,
      items: [{ marker: "⚠️", text: "anomaly" }, { marker: "🔴", text: "down" }],
    }]);
  });

  it("splits ordered and unordered runs into separate lists", () => {
    const out = parseNotificationBody("- a\n1. b");
    expect(out.map((b) => [b.kind, b.ordered])).toEqual([["list", false], ["list", true]]);
  });
});

describe("parseNotificationBody — code blocks", () => {
  it("captures a fenced block verbatim", () => {
    expect(parseNotificationBody("```\nline 1\n  line 2\n```"))
      .toEqual([{ kind: "code", text: "line 1\n  line 2" }]);
  });

  it("keeps content around a fence as separate blocks", () => {
    const out = parseNotificationBody("before\n```\ncode\n```\nafter");
    expect(out.map((b) => b.kind)).toEqual(["p", "code", "p"]);
  });
});

describe("parseNotificationBody — tables", () => {
  it("parses a GFM table into headers + rows", () => {
    expect(parseNotificationBody("| Canal | Vol |\n| --- | --- |\n| Jaime | 94 |\n| Emperador | 69 |")).toEqual([{
      kind: "table",
      headers: ["Canal", "Vol"],
      rows: [["Jaime", "94"], ["Emperador", "69"]],
    }]);
  });

  it("treats a pipe line without a separator as a paragraph", () => {
    expect(parseNotificationBody("a | b | c")[0].kind).toBe("p");
  });
});

describe("inlineSegments", () => {
  it("extracts code, bold and italic, leaving everything else literal", () => {
    expect(inlineSegments("a **b** *i* `c` d")).toEqual([
      { t: "text", v: "a " },
      { t: "bold", v: "b" },
      { t: "text", v: " " },
      { t: "italic", v: "i" },
      { t: "text", v: " " },
      { t: "code", v: "c" },
      { t: "text", v: " d" },
    ]);
  });

  it("does not mistake bold (**) for italic (*)", () => {
    expect(inlineSegments("**bold**")).toEqual([{ t: "bold", v: "bold" }]);
  });

  it("returns a single text segment when there is no markup", () => {
    expect(inlineSegments("plain text")).toEqual([{ t: "text", v: "plain text" }]);
  });
});

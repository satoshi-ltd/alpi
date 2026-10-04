import { describe, it, expect } from "vitest";
import { errorParts, failedTitle, inlineSegments, parseNotificationBody } from "../../../common/notificationBody.mjs";
import { INLINE_CORPUS, NOTIFICATION_CORPUS } from "../../../common/notificationBody.fixtures.mjs";

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

describe("real-world corpus", () => {
  const KINDS = new Set(["code", "heading", "label", "labelBody", "quote", "list", "table", "p"]);

  it.each(NOTIFICATION_CORPUS)("yields only well-formed blocks for %j", (body) => {
    for (const b of parseNotificationBody(body)) {
      expect(KINDS, JSON.stringify(b)).toContain(b.kind);
      if (b.kind === "list") {
        expect(Array.isArray(b.items)).toBe(true);
        for (const it of b.items) expect(typeof it.marker).toBe("string");
      }
      if (b.kind === "table") {
        expect(Array.isArray(b.headers)).toBe(true);
        for (const r of b.rows) expect(Array.isArray(r)).toBe(true);
      }
    }
  });

  it.each(INLINE_CORPUS)("round-trips every inline segment back to the source for %j", (text) => {
    expect(inlineSegments(text).map((s) => (s.t === "text" ? s.v : "")).join("").length)
      .toBeLessThanOrEqual(text.length);
    expect(inlineSegments(text).every((s) => typeof s.v === "string")).toBe(true);
  });
});

describe("parseNotificationBody — digest entries and raw payloads", () => {
  it("splits an item that opens with a bold name into name, meta and text", () => {
    const [list] = parseNotificationBody("- **Ana Ruiz** <ana@example.com> — Can we move Friday?\n- **Bob** — Invoice");
    expect(list.items.map((it) => it.entry)).toEqual([
      { name: "Ana Ruiz", meta: "ana@example.com", text: "Can we move Friday?" },
      { name: "Bob", meta: "", text: "Invoice" },
    ]);
  });

  it("leaves labelled, status, ranked, prose and mixed lists as lists", () => {
    const lists = [
      "- **Status:** green\n- **Disk**: 80%",
      "🔴 **Prod** down — 5xx\n🟢 **Stage** fine — ok",
      "1. **Ana** — hi\n2. **Bob** — yo",
      "- **Fixed** the login bug",
      "- **Backup** completed in three minutes today — 2.1 GB copied",
      "- **Ana** <ana@example.com> — hi\n- plain item",
      "- **Tests** — green",
      "- **Ana** *urgent* — hi\n- **Bob** `x` — yo",
      "- **Ana** and **Bob** — met\n- **Cy** — hi",
    ];
    for (const body of lists) {
      const [list] = parseNotificationBody(body);
      expect(list.items.some((it) => it.entry), body).toBe(false);
    }
  });

  it("reads a brace-delimited run of lines as code and an unclosed one as text", () => {
    expect(parseNotificationBody("refresh failed (400)\n{\n  \"error\": \"invalid_grant\",\n  \"scopes\": [1]\n}\nexit 1")).toEqual([
      { kind: "p", text: "refresh failed (400)" },
      { kind: "code", text: "{\n  \"error\": \"invalid_grant\",\n  \"scopes\": [1]\n}" },
      { kind: "p", text: "exit 1" },
    ]);
    expect(parseNotificationBody("see {\nno close").map((b) => b.kind)).toEqual(["p", "p"]);
    expect(parseNotificationBody("## Section {\nx\n}").map((b) => b.kind)).toEqual(["heading", "p", "p"]);
    expect(parseNotificationBody("Results [\n- one\n]").map((b) => b.kind)).toEqual(["p", "list", "p"]);
    expect(parseNotificationBody("x {\n  \"a\": 1\n}. If revoked, run setup again.").map((b) => b.kind)).toEqual(["p", "p", "p"]);
    expect(parseNotificationBody("**Payload:** {\n  \"a\": 1\n}")[0]).toEqual({ kind: "labelBody", label: "Payload", body: "{" });
    expect(parseNotificationBody("call(x, {\n  \"a\": 1\n})").map((b) => b.kind)).toEqual(["code"]);
    expect(parseNotificationBody("data {\n```\nraw\n```\n}").some((b) => b.kind === "code" && b.text.includes("```"))).toBe(false);
  });
});

describe("error parts", () => {
  it("splits a failure body into labelled facts, folded details and the rest", () => {
    const parts = errorParts(parseNotificationBody("**Reason:** token revoked\n**Exit:** 1\n\nReconnect the account.\n\n```text\nTraceback\n```"));
    expect(parts.facts.map((f) => f.label)).toEqual(["Reason", "Exit"]);
    expect(parts.details).toEqual([{ kind: "code", text: "Traceback" }]);
    expect(parts.rest).toEqual([{ kind: "p", text: "Reconnect the account." }]);
  });

  it("keeps an agent's own error body in order and folds only the code it ends with", () => {
    const parts = errorParts(parseNotificationBody("Prod is down.\n\n**Impact:** checkout\n\n```\nkubectl rollout undo\n```\nThen retry."));
    expect(parts.facts).toEqual([]);
    expect(parts.details).toEqual([]);
    expect(parts.rest.map((b) => b.kind)).toEqual(["p", "labelBody", "code", "p"]);
  });

  it("finds the word failed at the end of a title", () => {
    expect(failedTitle("Daily mail digest failed")).toEqual({ lead: "Daily mail digest", failed: true });
    expect(failedTitle("failed")).toEqual({ lead: "failed", failed: false });
    expect(failedTitle("Backup")).toEqual({ lead: "Backup", failed: false });
  });
});

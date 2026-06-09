import { describe, expect, it } from "vitest";
import {
  assistantWithProducedImages,
  compactProducedTool,
  nonImageProduced,
  stripProducedImageMarkdown,
} from "./producedAttachments.js";

const img = { kind: "image", name: "hero.jpg", path: "/p/out/hero.jpg" };
const pdf = { kind: "pdf", name: "r.pdf", path: "/p/out/r.pdf" };

describe("producedAttachments", () => {
  it("strips the markdown, the Path: line, and a bare path for a produced file", () => {
    const text = 'Saved here:\n\n![h](/p/out/hero.jpg "generated")\n\nPath: `/p/out/hero.jpg`';
    const out = stripProducedImageMarkdown(text, [img]);
    expect(out).not.toContain("![");
    expect(out).not.toContain("Path:");
    expect(out).not.toContain("/p/out/hero.jpg");
    expect(out).toContain("Saved here:");
  });

  it("strips a redundant Path line for a non-image produced file too", () => {
    const out = stripProducedImageMarkdown("Done.\n\nPath: /p/out/r.pdf", [pdf]);
    expect(out).not.toContain("/p/out/r.pdf");
    expect(out).toContain("Done.");
  });

  it("only strips standalone Path: lines — prose before an inline Path: survives", () => {
    const out = stripProducedImageMarkdown("Saved successfully. Path: /p/out/r.pdf", [pdf]);
    expect(out).toContain("Saved successfully.");
  });

  it("re-emits image markdown from the structured attachment (model text dropped)", () => {
    const body = assistantWithProducedImages("done ![x](/p/out/hero.jpg)", [img]);
    expect(body).toContain("![](/p/out/hero.jpg)");  // empty alt → caption is just the filename
    expect(body.match(/!\[/g)).toHaveLength(1); // not doubled
  });

  it("non-image attachments are kept for chips; images are not", () => {
    expect(nonImageProduced([img, pdf])).toEqual([pdf]);
  });

  it("compacts a tool result that produced an attachment", () => {
    const t = { name: "skill", output: '{"out": "/p/out/hero.jpg", "cost_usd": 0.04}' };
    expect(compactProducedTool(t, [img]).output).toBe("Generated · hero.jpg");
    expect(compactProducedTool({ output: "plain" }, [img]).output).toBe("plain");
  });
});

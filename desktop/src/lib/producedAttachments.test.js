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
  it("strips a produced image's markdown but leaves prose + other links", () => {
    const text = 'Here:\n\n![h](/p/out/hero.jpg "generated")\n\nPath: `/p/out/hero.jpg`';
    const out = stripProducedImageMarkdown(text, [img]);
    expect(out).not.toContain("![");
    expect(out).toContain("Path:");
  });

  it("re-emits image markdown from the structured attachment (model text dropped)", () => {
    const body = assistantWithProducedImages("done ![x](/p/out/hero.jpg)", [img]);
    expect(body).toContain("![hero.jpg](/p/out/hero.jpg)");
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

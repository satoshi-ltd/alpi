import { describe, it, expect } from "vitest";
import { renderMarkdown } from "./markdown.js";

describe("renderMarkdown tables", () => {
  it("renders a GFM table instead of stripping it to text", () => {
    const md = "| Día | RHR |\n| --- | --- |\n| Lun | 50 |";
    const html = renderMarkdown(md);
    expect(html).toContain('<div class="md-table">');
    expect(html).toContain("<table>");
    expect(html).toContain("<th>Día</th>");
    expect(html).toContain("<td>50</td>");
  });

  it("preserves column alignment", () => {
    const md = "| a | b |\n| :-- | --: |\n| 1 | 2 |";
    const html = renderMarkdown(md);
    expect(html).toContain('align="left"');
    expect(html).toContain('align="right"');
  });
});

describe("renderMarkdown code blocks", () => {
  it("wraps fenced code with a language header", () => {
    const html = renderMarkdown("```python\nprint('hi')\n```");
    expect(html).toContain('<div class="md-code">');
    expect(html).toContain('<span class="md-code-lang">python</span>');
    expect(html).toContain("md-code-copy");
    expect(html).toContain("print(");
  });

  it("labels a bare fence as text and escapes its content", () => {
    const html = renderMarkdown("```\n<b>x</b>\n```");
    expect(html).toContain(">text</span>");
    expect(html).toContain("&lt;b&gt;x&lt;/b&gt;");
  });

  it("keeps inline code as plain <code>", () => {
    const html = renderMarkdown("use `RMSSD` here");
    expect(html).toContain("<code>RMSSD</code>");
    expect(html).not.toContain("md-code");
  });
});

describe("renderMarkdown sanitization", () => {
  it("strips scripts and event handlers", () => {
    const html = renderMarkdown("<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>");
    expect(html).not.toContain("<script");
    expect(html).not.toContain("onerror");
  });
});

describe("renderMarkdown images", () => {
  it("renders a local image as a figure with data-src and a filename caption", () => {
    const html = renderMarkdown("![a serene room](/tmp/room-muse.png)");
    expect(html).toContain('<figure class="md-figure">');
    expect(html).toContain('data-src="/tmp/room-muse.png"');
    expect(html).toContain('alt="a serene room"');
    expect(html).not.toMatch(/\ssrc=/);
    expect(html).toContain('<figcaption class="md-figcaption">');
    expect(html).toContain("room-muse.png · a serene room");
    expect(html).toContain('class="md-figdl"');
    expect(html).not.toContain("data-dl");
  });

  it("uses the markdown title as the caption note when present", () => {
    const html = renderMarkdown('![alt](/tmp/recovery-7d.png "generado de COROS")');
    expect(html).toContain("recovery-7d.png · generado de COROS");
  });

  it("drops remote and protocol-relative image srcs (no figure, no img)", () => {
    for (const md of [
      "![x](https://evil.test/t.png)",
      "![x](//evil.test/t.png)",
      "![x](data:image/png;base64,AAAA)",
    ]) {
      const html = renderMarkdown(md);
      expect(html).not.toContain("<img");
      expect(html).not.toContain("md-figure");
    }
  });

  it("drops relative paths and non-image extensions", () => {
    expect(renderMarkdown("![x](room.png)")).not.toContain("<img");
    expect(renderMarkdown("![x](/tmp/notes.txt)")).not.toContain("<img");
  });

  it("does not inline svg (logos are linked, not rendered)", () => {
    expect(renderMarkdown("![logo](/tmp/logo.svg)")).not.toContain("md-figure");
  });
});


describe("code block copy affordance", () => {
  it("fenced code renders a copy button inside the header", async () => {
    const { renderMarkdown } = await import("./markdown.js");
    const html = renderMarkdown("```js\nconst a = 1;\n```");
    expect(html).toContain('class="md-code-copy"');
    expect(html).toContain('type="button"');
  });
});

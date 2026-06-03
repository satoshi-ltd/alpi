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
    expect(html).not.toContain("md-code-copy");
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
